from expenses.drive import drive_upload

from datetime import datetime, date
from pathlib import Path
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


@bp.route("/submit", methods=["GET", "POST"])
@login_required
def submit():
    if request.method == "POST":
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
            if not (dt and dpt and dst and amt):
                continue

            expense = Expense(
                date=datetime.strptime(dt, "%Y-%m-%d").date(),
                departure=dpt,
                destination=dst,
                amount=int(amt),
                transport=trn,
                memo=memo or None,
                status="pending",
                user_id=current_user.id
            )
            db.session.add(expense)
            db.session.flush()
            added_cnt += 1

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
                f.save(save_to)

                drive_link = drive_upload(
                    save_to,
                    filename,
                    folder_id=current_app.config["GDRIVE_UPLOAD_FOLDER_ID"],
                    credentials_path=current_app.config["GDRIVE_SERVICE_JSON"],
                )

                receipt = ExpenseReceipt(
                    expense_id=expense.id,
                    file_path=drive_link
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


@bp.route("/receipts/<path:filename>")
def view_receipt(filename):
    receipts_dir = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(str(receipts_dir), filename)


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
