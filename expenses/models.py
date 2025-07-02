# expenses/models.py
from datetime import datetime
from sqlalchemy import Enum

from flask_login import UserMixin, LoginManager
from werkzeug.security import generate_password_hash, check_password_hash

from app import db, login_manager   # ← app.py で生成したインスタンス

# ─────────────────────────────────────
# User  : ログイン&権限管理
# ─────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = "user"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(32), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role          = db.Column(db.String(10), default="user")   # "user" or "admin"

    # パスワード操作
    def set_password(self, pw: str):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw: str) -> bool:
        return check_password_hash(self.password_hash, pw)

    @property
    def is_admin(self) -> bool:
        """role カラムが 'admin' の場合に True を返す."""
        return self.role == 'admin'

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

# Flask-Login とのひも付け
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ─────────────────────────────────────
# Expense : 交通費申請
# ─────────────────────────────────────
class Expense(db.Model):
    __tablename__ = "expense"

    id               = db.Column(db.Integer, primary_key=True)
    date             = db.Column(db.Date,     nullable=False)
    departure        = db.Column(db.String(64),  nullable=False)
    destination      = db.Column(db.String(64),  nullable=False)
    amount           = db.Column(db.Integer,  nullable=False)
    memo             = db.Column(db.String(256))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    file_path        = db.Column(db.String(256))
    status           = db.Column(
        Enum("pending", "approved", "rejected", "canceled", name="expense_status"),
        default="pending", nullable=False
    )
    carried_forward  = db.Column(db.Boolean, default=False, nullable=False)
    final_checked    = db.Column(db.Boolean, default=False, nullable=False)
    transport        = db.Column(
        Enum(
            "バス", "電車", "特急", "新幹線",
            "高速道路", "自動車", "立替経費", "その他",
            name="transport_type"
        ),
        nullable=False,
        default="電車"
    )

    # 申請者
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user    = db.relationship("User", backref="expenses")

    # 領収書（双方向リレーション）
    receipts = db.relationship(
        "ExpenseReceipt",
        back_populates="expense",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    def __repr__(self):
        return f"<Expense {self.id} {self.date} {self.departure}->{self.destination} ¥{self.amount}>"


# ─────────────────────────────────────
# ExpenseReceipt : 添付領収書
# ─────────────────────────────────────
class ExpenseReceipt(db.Model):
    __tablename__ = "expense_receipt"

    id          = db.Column(db.Integer, primary_key=True)
    expense_id  = db.Column(
        db.Integer,
        db.ForeignKey("expense.id", ondelete="CASCADE"),
        nullable=False
    )
    file_path   = db.Column(db.String(256), nullable=False)

    # どの Expense に紐づくか
    expense     = db.relationship(
        "Expense",
        back_populates="receipts"
    )

    def __repr__(self):
        return f"<Receipt {self.id} for Expense {self.expense_id}>"
