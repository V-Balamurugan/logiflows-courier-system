"""state machine and concurrency

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-04 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add version_id to parcels
    with op.batch_alter_table('parcels', schema=None) as batch_op:
        batch_op.add_column(sa.Column('version_id', sa.Integer(), server_default='1', nullable=False))

    # 2. Add from_status and source to tracking_history
    with op.batch_alter_table('tracking_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('from_status', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('source', sa.String(length=50), server_default='API', nullable=False))

    # 3. Add is_successful and failure_reason to custody_scans
    with op.batch_alter_table('custody_scans', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_successful', sa.Boolean(), server_default='1', nullable=False))
        batch_op.add_column(sa.Column('failure_reason', sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('custody_scans', schema=None) as batch_op:
        batch_op.drop_column('failure_reason')
        batch_op.drop_column('is_successful')

    with op.batch_alter_table('tracking_history', schema=None) as batch_op:
        batch_op.drop_column('source')
        batch_op.drop_column('from_status')

    with op.batch_alter_table('parcels', schema=None) as batch_op:
        batch_op.drop_column('version_id')

