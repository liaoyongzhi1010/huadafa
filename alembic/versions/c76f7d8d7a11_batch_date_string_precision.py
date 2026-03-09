"""store batch production date as validated string

Revision ID: c76f7d8d7a11
Revises: 24bfa7f2e5b2
Create Date: 2026-03-09 00:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c76f7d8d7a11"
down_revision: Union[str, Sequence[str], None] = "24bfa7f2e5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("batches", schema=None) as batch_op:
        batch_op.alter_column(
            "production_date",
            existing_type=sa.Date(),
            type_=sa.String(length=10),
            existing_nullable=False,
        )


def downgrade() -> None:
    op.execute(
        "UPDATE batches SET production_date = production_date || '-01-01' WHERE length(production_date) = 4"
    )
    op.execute(
        "UPDATE batches SET production_date = production_date || '-01' WHERE length(production_date) = 7"
    )
    with op.batch_alter_table("batches", schema=None) as batch_op:
        batch_op.alter_column(
            "production_date",
            existing_type=sa.String(length=10),
            type_=sa.Date(),
            existing_nullable=False,
        )
