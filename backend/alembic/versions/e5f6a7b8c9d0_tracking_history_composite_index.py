"""tracking history composite index

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-07 21:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        'ix_tracking_history_parcel_created_id',
        'tracking_history',
        ['parcel_id', 'created_at', 'id'],
        unique=False
    )


def downgrade():
    op.drop_index('ix_tracking_history_parcel_created_id', table_name='tracking_history')
