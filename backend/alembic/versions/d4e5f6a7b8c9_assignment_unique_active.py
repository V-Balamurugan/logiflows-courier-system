"""partial unique index on active assignments

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-07 20:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Partial unique index ensuring at most one active (ASSIGNED or IN_PROGRESS) assignment per parcel
    op.create_index(
        'uq_active_parcel_assignment',
        'delivery_assignments',
        ['parcel_id'],
        unique=True,
        postgresql_where=sa.text("status IN ('ASSIGNED', 'IN_PROGRESS')"),
        sqlite_where=sa.text("status IN ('ASSIGNED', 'IN_PROGRESS')")
    )


def downgrade() -> None:
    op.drop_index('uq_active_parcel_assignment', table_name='delivery_assignments')
