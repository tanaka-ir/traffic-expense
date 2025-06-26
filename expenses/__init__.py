from flask import Blueprint, g, current_app 
from flask_login import current_user

from .models import Expense         # ← 追加
from .utils import admin_required   # noqa

bp = Blueprint("expenses", __name__, template_folder="../templates")

# ──────────────────────────────────────────────────────────────
# ここから：承認待ち件数をテンプレートへ渡す
# ──────────────────────────────────────────────────────────────
@bp.before_app_request                # ← アプリ全体に効く
def inject_pending_count():
    """
    admin でログインしている場合だけ
    g.pending_count と Jinja グローバル pending_count を設定
    """
    if current_user.is_authenticated and current_user.role == "admin":
        pending = Expense.query.filter_by(status="pending").count()
        g.pending_count = pending
    else:
        g.pending_count = 0

    # Jinja から {{ pending_count }} で参照できるように
    current_app.jinja_env.globals["pending_count"] = g.pending_count
# ──────────────────────────────────────────────────────────────

from . import routes   # noqa: E402,F401
