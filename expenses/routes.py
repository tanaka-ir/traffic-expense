from expenses.drive import drive_upload

from datetime import datetime
from pathlib import Path
import os

from flask import render_template, request, redirect, url_for, flash, current_app
from flask import send_from_directory
from werkzeug.utils import secure_filename

from . import bp
from app import db
from .models import Expense, User

from flask_login import login_required, current_user
from expenses.utils import admin_required

from sqlalchemy import func, case, text #手打ち追加
from datetime import date
import calendar

from uuid import uuid4
from .models import Expense, ExpenseReceipt   # ★Receipt を追加

from flask import request

@bp.route("/submit", methods=["GET", "POST"])
@login_required
def submit():
    if request.method == "POST":
        # 1️⃣ 各 input の値をリストで取得
        dates        = request.form.getlist("date[]")
        departures   = request.form.getlist("departure[]")
        destinations = request.form.getlist("destination[]")
        amounts      = request.form.getlist("amount[]")
        memos        = request.form.getlist("memo[]")
        transports   = request.form.getlist("transport[]")
        files_dict = {
            idx: request.files.getlist(f"receipt{idx}[]")
            for idx in range(len(departures))
        }

        added_cnt = 0
        for idx, (dpt, dst, dt, amt, memo, trn) in enumerate(
            zip(departures, destinations, dates, amounts, memos, transports)
        ):
            # 2️⃣ 必須 4 項目のどれかが空ならスキップ
            if not (dt and dpt and dst and amt):
                continue

            # ① まず Expense を作成して flush
            expense = Expense(
                date=datetime.strptime(dt, "%Y-%m-%d").date(),
                departure=dpt,
                destination=dst,
                amount=int(amt),
                transport=trn, #ここを要確認
                memo=memo or None,
                status="pending",
                user_id=current_user.id
            )
            db.session.add(expense)
            db.session.flush()        # expense.id が使えるようになる

            added_cnt += 1            # ★区間数をカウント

            # ② 領収書（最大 5 枚）
            for f in files_dict.get(idx, [])[:5]:
                if not f or not f.filename:
                    continue
                ext = f.filename.rsplit(".", 1)[-1].lower()
                if ext not in current_app.config["ALLOWED_EXTENSIONS"]:
                    flash(f"拡張子 {ext} は許可されていません", "warning")
                    continue

                filename   = secure_filename(f"{dt}_{idx}_{uuid4().hex[:6]}.{ext}")
                upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
                upload_dir.mkdir(parents=True, exist_ok=True)
                save_to = upload_dir / filename
                f.save(save_to)                         # ローカル保存
                drive_link = drive_upload(save_to, filename)

                receipt = ExpenseReceipt(
                    expense_id=expense.id,              # ← flush 済なので OK
                    file_path=drive_link
                )
                db.session.add(receipt)

        # 5️⃣ コミット & フィードバック
        if added_cnt:
            db.session.commit()
            flash(f"{added_cnt} 区間を登録しました", "success")
            return redirect(url_for("expenses.list_expenses"))
        else:
            flash("入力が空です。少なくとも 1 区間は必須項目を入力してください。", "warning")

    # GET のとき
    return render_template("submit.html")

@bp.route("/list")
@login_required
def list_expenses():
    month_param = request.args.get("month")      # 例: "2025-06"
    user_param  = request.args.get("user")       # 例: "伊藤"  または "all"/None

    # ① ★ここで status_filter を受け取る
    status_filter = request.view_args.get("status_filter")   # None / 'pending'

    query = Expense.query

    # ---- 権限制御 ---------------------------------------------------
    if current_user.role != "admin":
        # 申請者は常に自分のレコードだけ
        query = query.filter_by(user_id=current_user.id)
    else:
        # 承認者はドロップダウンで選んだユーザーに絞る
        if user_param and user_param != "all":
            target = User.query.filter_by(username=user_param).first()
            if target:
                query = query.filter_by(user_id=target.id)

    # ② ★ステータスで絞り込み（承認待ちタブ用）
    if status_filter:
        query = query.filter_by(status=status_filter)

    # ---- 月フィルタ -------------------------------------------------
    if month_param:
        y, m = map(int, month_param.split("-"))
        start = date(y, m, 1)
        end   = date(y, m, calendar.monthrange(y, m)[1])

        # carried_forward が true なら日付+1ヶ月で評価
        effective_date = case(
            (Expense.carried_forward,
             func.date(Expense.date, '+1 month')),   # SQLite 式
            else_=Expense.date
        )
        query = query.filter(effective_date.between(start, end))

    expenses = query.order_by(Expense.date.desc()).all()
    total = sum(e.amount for e in expenses)
    # ★ 追加（10 % 内税計算）
    tax_rate   = 0.10
    net_total  = int(total / (1 + tax_rate))   # 税抜額（端数切り捨て）
    tax_amount = total - net_total             # 消費税額

    # 承認者用にユーザー一覧を渡す
    users = []
    if current_user.role == "admin":
        users = User.query.order_by(User.username).all()

    return render_template(
    "list.html",
    expenses=expenses,
    total=total,
    net_total=net_total,        # ← 追加
    tax_amount=tax_amount,      # ← 追加
    month_selected=month_param or "",
    user_selected=user_param or "all",
    users=users,
    status_filter=status_filter,
    show_user_col = (
        current_user.role == "admin" and (user_param in [None, "", "all"])
        )
    )


@bp.route("/receipts/<path:filename>")
def view_receipt(filename):
    """アップロード済み領収書をブラウザで開く"""
    receipts_dir = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(str(receipts_dir), filename)

@bp.route("/approve/<int:eid>", methods=["POST"])
@admin_required
def approve(eid):
    exp = Expense.query.get_or_404(eid)
    exp.status = "approved"           # ← always overwrite
    db.session.commit()
    flash("承認しました", "success")
    return redirect(url_for('expenses.list_expenses'))

@bp.route("/reject/<int:eid>", methods=["POST"])
@admin_required
def reject(eid):
    exp = Expense.query.get_or_404(eid)
    exp.status = "rejected"           # ← always overwrite
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
    """
    レコードを物理削除。
    - 承認者(admin) は全件削除可能
    - 申請者(user) は自分のレコードだけ削除可能
    """
    exp = Expense.query.get_or_404(eid)

    # 権限制御
    if current_user.role != "admin" and exp.user_id != current_user.id:
        flash("削除権限がありません", "warning")
        return redirect(url_for("expenses.list_expenses"))

    db.session.delete(exp)
    db.session.commit()
    flash("レコードを削除しました", "secondary")
    return redirect(url_for("expenses.list_expenses"))

@bp.route("/pending")
@login_required
def list_pending():
    """
    承認待ち(pending) だけを抽出して /list と同じテンプレートで表示
    - 承認者(admin): 全員分の pending
    - 申請者(user) : 自分の pending のみ
    クエリ文字列 ?month=YYYY-MM&user=◯◯ もそのまま流用
    """
    # 既存の list_expenses と共通処理を再利用するため
    request.view_args["status_filter"] = "pending"
    return list_expenses()

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

# --- 最終確認 ON ---
@bp.route("/check/<int:eid>", methods=["POST"])
@admin_required
def final_check(eid):
    e = Expense.query.get_or_404(eid)
    e.final_checked = True
    db.session.commit()
    flash("最終確認しました ✅", "info")
    return redirect(url_for("expenses.list_expenses",
                            **request.args))    # ← 現在のフィルタを維持

# --- 最終確認 OFF ---
@bp.route("/uncheck/<int:eid>", methods=["POST"])
@admin_required
def undo_final_check(eid):
    e = Expense.query.get_or_404(eid)
    e.final_checked = False
    db.session.commit()
    flash("最終確認を解除しました", "secondary")
    return redirect(url_for("expenses.list_expenses",
                            **request.args))
