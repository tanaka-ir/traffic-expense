"""add transport column

Revision ID: 356f079bdec8
Revises: c82a153c03d7
Create Date: 2025-06-19 13:02:37.387927

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '356f079bdec8'
down_revision = 'c82a153c03d7'
branch_labels = None
depends_on = None


def upgrade():
    # ──────────────────────────────────────────────────────────
    # ① 既存テーブルを一時名に退避
    # ──────────────────────────────────────────────────────────
    op.execute("ALTER TABLE expense_receipt RENAME TO _tmp_expense_receipt;")

    # ──────────────────────────────────────────────────────────
    # ② Cascade 外部キー付きで新テーブルを作成
    #    ※SQLite は ALTER TABLE ... ADD CONSTRAINT が使えないため
    #      作り直すのが確実です
    # ──────────────────────────────────────────────────────────
    op.create_table(
        "expense_receipt",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("file_path", sa.String(256), nullable=False),
        sa.Column(
            "expense_id",
            sa.Integer,
            sa.ForeignKey("expense.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # ──────────────────────────────────────────────────────────
    # ③ 旧テーブル→新テーブルへデータコピー
    # ──────────────────────────────────────────────────────────
    op.execute(
        """
        INSERT INTO expense_receipt (id, file_path, expense_id)
        SELECT id, file_path, expense_id
        FROM   _tmp_expense_receipt;
        """
    )

    # ──────────────────────────────────────────────────────────
    # ④ 一時テーブルを削除
    # ──────────────────────────────────────────────────────────
    op.execute("DROP TABLE _tmp_expense_receipt;")


def downgrade():
    # 逆順：元の構造に戻したい場合（省略可）
    op.execute("ALTER TABLE expense_receipt RENAME TO _tmp_expense_receipt;")
    op.create_table(
        "expense_receipt",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("file_path", sa.String(256), nullable=False),
        sa.Column("expense_id", sa.Integer, nullable=False),
    )
    op.execute(
        """
        INSERT INTO expense_receipt (id, file_path, expense_id)
        SELECT id, file_path, expense_id
        FROM   _tmp_expense_receipt;
        """
    )
    op.execute("DROP TABLE _tmp_expense_receipt;")
