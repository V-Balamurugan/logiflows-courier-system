"""payment states and audit fields

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-07 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('parcels', schema=None) as batch_op:
        batch_op.add_column(sa.Column('payment_method', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('transaction_reference', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('paid_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('parcels', schema=None) as batch_op:
        batch_op.drop_column('paid_at')
        batch_op.drop_column('transaction_reference')
        batch_op.drop_column('payment_method')
