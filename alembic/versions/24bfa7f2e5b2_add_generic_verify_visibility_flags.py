"""add generic verify visibility flags

Revision ID: 24bfa7f2e5b2
Revises: 0d8dcd6e61ad
Create Date: 2026-03-07 20:15:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "24bfa7f2e5b2"
down_revision: Union[str, Sequence[str], None] = "0d8dcd6e61ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        op.execute(
            "ALTER TABLE verify_configs ADD COLUMN show_product_name BOOLEAN NOT NULL DEFAULT 1"
        )
        op.execute(
            "ALTER TABLE verify_configs ADD COLUMN show_batch_date BOOLEAN NOT NULL DEFAULT 1"
        )
        return

    op.add_column(
        "verify_configs",
        sa.Column("show_product_name", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "verify_configs",
        sa.Column("show_batch_date", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("verify_configs", "show_product_name", server_default=None)
    op.alter_column("verify_configs", "show_batch_date", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        # sqlite 不支持直接 drop column，这里使用 batch 方式重建表
        with op.batch_alter_table("verify_configs", schema=None) as batch_op:
            batch_op.drop_column("show_batch_date")
            batch_op.drop_column("show_product_name")
        return

    op.drop_column("verify_configs", "show_batch_date")
    op.drop_column("verify_configs", "show_product_name")
