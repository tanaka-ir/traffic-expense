import os
from expenses.line_push import push_text, push_image
from expenses.utils import save_upload

import time
import requests

from datetime import datetime, date
from pathlib import Path
from .image_utils import normalize_to_jpeg
import calendar

from flask import (
    render_template, request, redirect, url_for, flash, current_app, send_from_directory
)
from werkzeug.utils import secure_filename

from . import bp
from app import db
from .models import Expense, ExpenseReceipt, User
from flask_login import login_required, current_user
from expenses.utils import admin_required
from sqlalchemy.orm import joinedload
from sqlalchemy import func, case
from uuid import uuid4

def ensure_url_ready(url: str, tries: int = 10, wait: float = 0.25) -> bool:
    """
    公開URLが 200 を返すまで HEAD をリトライ。
    可能なら内部URL(http://127.0.0.1:8000/files/...)で先に確認してから、
    元の外部URLでも確認する。HEADが405なら軽いGETでフォールバック。
    """
    # /files/<filename> が含まれていれば内部URLを組み立てる
    internal_url = None
    try:
        fname = url.rsplit("/files/", 1)[1]
        internal_url = f"http://127.0.0.1:8000/files/{fname}"
    except Exception:
        pass

    last_err = None
    for i in range(tries):
        # 1) 内部URL優先（証明書やDNSを挟まないため安定）
        if internal_url:
            try:
                r = requests.head(internal_url, timeout=2, allow_redirects=True)
                if r.status_code == 200:
                    return True
                if r.status_code == 405:
                    g = requests.get(internal_url, stream=True, timeout=4)
                    ok = (g.status_code == 200)
                    g.close()
                    if ok:
                        return True
            except Exception as e:
                last_err = e

        # 2) 外部URL（=呼び出し元で渡ってきたURL）
        try:
            r2 = requests.head(url, timeout=3, allow_redirects=True)
            if r2.status_code == 200:
                return True
            if r2.status_code == 405:
                g2 = requests.get(url, stream=True, timeout=4)
                ok2 = (g2.status_code == 200)
                g2.close()
                if ok2:
                    return True
        except Exception as e2:
            last_err = e2

        # 逓増スリープ（0.25, 0.5, 0.75, ... 秒）
        time.sleep(wait * (i + 1))

    current_app.logger.warning("ensure_url_ready timeout for %s (last_err=%s)", url, last_err)
    return False

@bp.route("/submit", methods=["GET", "POST"])
@login_required
def submit():
    # 画像URLを組み立てるためのベース（.env の BASE_URL を優先）
    BASE_URL = os.getenv("BASE_URL", request.url_root.rstrip("/"))

    if request.method == "POST":
        ua = request.headers.get("User-Agent", "-")
        cl = request.headers.get("Content-Length", "-")
        current_app.logger.info(f"upload_start ua={ua} content_length={cl}")
        dates        = request.form.getlist("date[]")
        departures   = request.form.getlist("departure[]")
        destinations = request.form.getlist("destination[]")
        amounts      = request.form.getlist("amount[]")
        memos        = request.form.getlist("memo[]")
        transports   = request.form.getlist("transport[]")


        #--96行目から107行目までは仮で入れている--
        current_app.logger.info(
            "UPLOAD req content_type=%s content_length=%s",
            request.content_type, request.content_length
        )
        # 受信したファイルキー一覧（何というnameで届いたか）
        current_app.logger.info("UPLOAD files.keys=%s", list(request.files.keys()))

        # 各行 index ごとの受信数（サーバが探しているキー名で何件あるか）
        for i in range(len(departures)):
            current_app.logger.info("UPLOAD files[receipt%d[]] count=%s",
                                    i, len(request.files.getlist(f"receipt{i}[]")))
        #--ここまであとで消す--

        # 各行（区間）ごとのファイル配列
        files_dict = {
            idx: request.files.getlist(f"receipt{idx}[]")
            for idx in range(len(departures))
        }

        added_cnt = 0
        for idx, (dpt, dst, dt, amt, memo, trn) in enumerate(
            zip(departures, destinations, dates, amounts, memos, transports)
        ):
            # 必須チェック
            if not (dt and dpt and dst and amt):
                continue

            # 申請レコードを作成
            expense = Expense(
                date=datetime.strptime(dt, "%Y-%m-%d").date(),
                departure=dpt,
                destination=dst,
                amount=int(amt),
                transport=trn,
                memo=memo or None,
                status="pending",
                user_id=current_user.id,
            )
            db.session.add(expense)
            db.session.flush()  # expense.id を得る
            added_cnt += 1

            # 1枚目に添える注記テキストを作成
            try:
                date_str = datetime.strptime(dt, "%Y-%m-%d").date().isoformat()
            except ValueError:
                date_str = dt
            # ── まずテキストだけ送信 ──────────────────────────
            note = f"{date_str}  {dpt}→{dst}  ¥{int(amt):,}"
            if memo:
                note += f"\nメモ: {memo}"

            header = (
                f"{current_user.username}（{'管理者' if current_user.role == 'admin' else 'ユーザー'}）からの申請です。\n"
                f"{note}\n↓↓↓↓"
            )
            push_text(header)          # ← ★ テキストのみ 1 通目

            # 領収書 1〜5 枚を保存 & LINE へ送信
            files = [f for f in files_dict.get(idx, []) if f and getattr(f, "filename", "")][:5]
            for f in files:
                ext = f.filename.rsplit(".", 1)[-1].lower()
                if ext not in current_app.config["ALLOWED_EXTENSIONS"]:
                    flash(f"拡張子 {ext} は許可されていません", "warning")
                    continue

                # ① サーバーに保存（uuid で一意化）
                filename = save_upload(f)

                # === ここから追加：保存直後ログ＆正規化（PDF は除外） ===
                # 物理パスを解決（UPLOAD_FOLDER が相対なら app.root_path を基準に解決）
                try:
                    up = current_app.config["UPLOAD_FOLDER"]
                    upload_dir = Path(up) if Path(up).is_absolute() else Path(current_app.root_path) / up
                    save_path = (upload_dir / filename).resolve()
                except Exception as e:
                    current_app.logger.exception(f"upload_dir_resolve_failed filename={filename} err={e}")
                    continue  # ディレクトリ特定に失敗したらこのファイルはスキップ

                # 保存直後のログ
                try:
                    current_app.logger.info(f"upload_saved path={save_path} size={save_path.stat().st_size}B ext={ext}")
                except Exception:
                    current_app.logger.info(f"upload_saved path={save_path} ext={ext}")

                # 画像なら JPEG 正規化（HEIC/HEIF/WEBP/PNG/JPEG → JPEG）
                if ext != "pdf":
                    try:
                        new_path = normalize_to_jpeg(save_path, long_edge=2000, quality=85)

                        # 変換でファイル名が変わる場合があるため差し替え
                        if new_path != save_path:
                            # 元ファイルが .jpg 以外なら掃除（失敗は警告止まり）
                            try:
                                if save_path.exists() and save_path.suffix.lower() != ".jpg":
                                    save_path.unlink(missing_ok=True)
                            except Exception as ce:
                                current_app.logger.warning(f"cleanup_failed path={save_path} err={ce}")

                            save_path = new_path
                            filename = new_path.name   # ← この後の URL/DB はこの新ファイル名を使う
                            ext = "jpg"

                        # 正規化後のログ
                        try:
                            current_app.logger.info(f"upload_normalized path={save_path} size={save_path.stat().st_size}B")
                        except Exception:
                            current_app.logger.info(f"upload_normalized path={save_path}")
                    except Exception as ne:
                        # 正規化失敗は致命にしない（原本のまま続行）
                        current_app.logger.exception(f"normalize_failed path={save_path} err={ne}")
                # === 追加ここまで ===

                # ② 公開 URL 作成（必ず HTTPS の BASE_URL）
                image_url = f"{BASE_URL}/files/{filename}"
                current_app.logger.info("prepared image_url -> %s", image_url)

                # ②.5 公開URLの準備ができているかHEADで確認（軽くリトライ）
                if not ensure_url_ready(image_url):
                    current_app.logger.warning("image_url not ready -> %s (skip push)", image_url)
                    continue  # この画像の送信はスキップ（必要なら再送キュー化も検討）

                # ③ LINE へ送信（画像のみ）
                try:
                    push_image(image_url)          # ← 常に画像だけ送る
                except Exception as e:
                    current_app.logger.exception("LINE送信に失敗: %s (url=%s)", e, image_url)

                # ④ DB: file_path にはローカル保存のファイル名を記録
                receipt = ExpenseReceipt(
                    expense_id=expense.id,
                    file_path=filename,
                )
                db.session.add(receipt)

        if added_cnt:
            db.session.commit()
            flash(f"{added_cnt} 区間を登録しました", "success")
            return redirect(url_for("expenses.list_expenses"))
        else:
            flash("入力が空です。少なくとも 1 区間は必須項目を入力してください。", "warning")

    return render_template("submit.html")



@bp.route("/list")
@login_required
def list_expenses():
    month_param = request.args.get("month")
    user_param  = request.args.get("user")
    status_filter = request.view_args.get("status_filter")

    query = Expense.query
    if current_user.role != "admin":
        query = query.filter_by(user_id=current_user.id)
    else:
        if user_param and user_param != "all":
            target = User.query.filter_by(username=user_param).first()
            if target:
                query = query.filter_by(user_id=target.id)

    if status_filter:
        query = query.filter_by(status=status_filter)

    if month_param:
        y, m = map(int, month_param.split("-"))
        start = date(y, m, 1)
        end   = date(y, m, calendar.monthrange(y, m)[1])
        effective_date = case(
            (Expense.carried_forward,
             func.date(Expense.date, '+1 month')),
            else_=Expense.date
        )
        query = query.filter(effective_date.between(start, end))

    expenses = (
        query.options(joinedload(Expense.receipts))
             .order_by(Expense.date.desc())
             .all()
    )

    total = sum(e.amount for e in expenses)
    tax_rate   = 0.10
    net_total  = int(total / (1 + tax_rate))
    tax_amount = total - net_total

    users = []
    if current_user.role == "admin":
        users = User.query.order_by(User.username).all()

    return render_template(
        "list.html",
        expenses=expenses,
        total=total,
        net_total=net_total,
        tax_amount=tax_amount,
        month_selected=month_param or "",
        user_selected=user_param or "all",
        users=users,
        status_filter=status_filter,
        show_user_col=(
            current_user.role == "admin" and (user_param in [None, "", "all"])
        )
    )


@bp.route("/files/<path:filename>", methods=["GET", "HEAD"])
def view_receipt(filename):
    # 認証不要（LINEが直接取りに来るため）
    receipts_dir = current_app.config["UPLOAD_FOLDER"]  # 例: "instance/receipts"
    return send_from_directory(str(receipts_dir), filename, as_attachment=False, max_age=3600)


@bp.route("/pending")
@login_required
def list_pending():
    request.view_args["status_filter"] = "pending"
    return list_expenses()


@bp.route("/approve/<int:eid>", methods=["POST"])
@admin_required
def approve(eid):
    exp = Expense.query.get_or_404(eid)
    exp.status = "approved"
    db.session.commit()
    flash("承認しました", "success")
    return redirect(url_for('expenses.list_expenses'))


@bp.route("/reject/<int:eid>", methods=["POST"])
@admin_required
def reject(eid):
    exp = Expense.query.get_or_404(eid)
    exp.status = "rejected"
    db.session.commit()
    flash("却下しました", "danger")
    return redirect(url_for('expenses.list_expenses'))


@bp.route("/cancel/<int:eid>", methods=["POST"])
@login_required
def cancel(eid):
    exp = Expense.query.get_or_404(eid)
    if exp.user_id == current_user.id and exp.status == "pending":
        exp.status = "canceled"
        db.session.commit()
        flash("取り消しました", "secondary")
    return redirect(url_for("expenses.list_expenses"))


@bp.route("/delete/<int:eid>", methods=["POST"])
@login_required
def delete_expense(eid):
    exp = Expense.query.get_or_404(eid)
    if current_user.role != "admin" and exp.user_id != current_user.id:
        flash("削除権限がありません", "warning")
        return redirect(url_for("expenses.list_expenses"))
    db.session.delete(exp)
    db.session.commit()
    flash("レコードを削除しました", "secondary")
    return redirect(url_for("expenses.list_expenses"))


@bp.route("/carry/<int:eid>", methods=["POST"])
@admin_required
def carry_forward(eid):
    e = Expense.query.get_or_404(eid)
    e.carried_forward = True
    db.session.commit()
    flash("翌月に振り替えました", "info")
    return redirect(url_for("expenses.list_expenses"))


@bp.route("/uncarry/<int:eid>", methods=["POST"])
@admin_required
def undo_carry(eid):
    e = Expense.query.get_or_404(eid)
    e.carried_forward = False
    db.session.commit()
    flash("前月に戻しました", "secondary")
    return redirect(url_for("expenses.list_expenses"))


@bp.route("/check/<int:eid>", methods=["POST"])
@admin_required
def final_check(eid):
    e = Expense.query.get_or_404(eid)
    e.final_checked = True
    db.session.commit()
    flash("最終確認しました ✅", "info")
    return redirect(url_for("expenses.list_expenses", **request.args))


@bp.route("/uncheck/<int:eid>", methods=["POST"])
@admin_required
def undo_final_check(eid):
    e = Expense.query.get_or_404(eid)
    e.final_checked = False
    db.session.commit()
    flash("最終確認を解除しました", "secondary")
    return redirect(url_for("expenses.list_expenses", **request.args))
