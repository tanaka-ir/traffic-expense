"""fk cascade on receipt"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "bdc4fe5aa265"
down_revision = "356f079bdec8"   # 直前の revision に合わせる
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------
    # ① 既存 expense_receipt を退避
    # ------------------------------------------------------------
    op.execute("ALTER TABLE expense_receipt RENAME TO _tmp_expense_receipt;")

    # ------------------------------------------------------------
    # ② Cascade FK 付きで新テーブル作成
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # ③ 旧 → 新 へデータコピー
    # ------------------------------------------------------------
    op.execute(
        """
        INSERT INTO expense_receipt (id, file_path, expense_id)
        SELECT id, file_path, expense_id
        FROM   _tmp_expense_receipt;
        """
    )

    # ------------------------------------------------------------
    # ④ 一時テーブル削除
    # ------------------------------------------------------------
    op.execute("DROP TABLE _tmp_expense_receipt;")


def downgrade():
    # 元に戻したい場合（任意）
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
