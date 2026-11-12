"""add custody hash chain

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-10 19:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('custody_scans', sa.Column('previous_hash', sa.String(length=64), nullable=True))
    op.add_column('custody_scans', sa.Column('record_hash', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('custody_scans', 'record_hash')
    op.drop_column('custody_scans', 'previous_hash')
