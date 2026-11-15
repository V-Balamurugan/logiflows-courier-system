"""add coordinate provenance, geocoding fields, and route idempotency

Revision ID: c8f1a2b3c4d5
Revises: a7d6f19c882b
Create Date: 2026-11-15 19:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c8f1a2b3c4d5'
down_revision: Union[str, Sequence[str], None] = 'a7d6f19c882b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

coord_source_enum = sa.Enum(
    'VERIFIED_GPS',
    'VERIFIED_GEOCODING',
    'MANUAL',
    'BRANCH_VICINITY_ESTIMATE',
    name='coordinatesource',
)

coord_verification_enum = sa.Enum(
    'VERIFIED',
    'UNVERIFIED',
    'FAILED',
    name='coordinateverificationstatus',
)

old_objective_enum = sa.Enum(
    'FASTEST',
    'SHORTEST',
    'BALANCED',
    'MANUAL',
    name='routeobjective',
)

new_objective_enum = sa.Enum(
    'FASTEST',
    'SHORTEST',
    'SHORTEST_DISTANCE',
    'BALANCED',
    'PRIORITY_FIRST',
    'MANUAL',
    name='routeobjective',
)


def upgrade() -> None:
    # 1. DeliveryRoutes modifications
    with op.batch_alter_table('delivery_routes', schema=None) as batch_op:
        batch_op.alter_column(
            'optimization_objective',
            existing_type=old_objective_enum,
            type_=new_objective_enum,
            existing_nullable=False,
        )
        batch_op.add_column(sa.Column('idempotency_key', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('current_latitude', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('current_longitude', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('last_telemetry_at', sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'eta_source',
                sa.String(length=50),
                server_default='LOCAL_ESTIMATE',
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column('eta_calculated_at', sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'has_low_confidence_stops',
                sa.Boolean(),
                server_default=sa.text('0'),
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column('low_confidence_override_reason', sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column('low_confidence_overridden_by_id', sa.Integer(), nullable=True)
        )
        batch_op.add_column(sa.Column('low_confidence_overridden_at', sa.DateTime(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_delivery_routes_idempotency_key'),
            ['idempotency_key'],
            unique=True,
        )
        batch_op.create_foreign_key(
            'fk_delivery_routes_override_user',
            'users',
            ['low_confidence_overridden_by_id'],
            ['id'],
            ondelete='SET NULL',
        )

    # 2. Parcels additions
    with op.batch_alter_table('parcels', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sender_normalized_address', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('receiver_normalized_address', sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'origin_coordinate_source',
                coord_source_enum,
                server_default='BRANCH_VICINITY_ESTIMATE',
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column('origin_confidence', sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'origin_verification_status',
                coord_verification_enum,
                server_default='UNVERIFIED',
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column('origin_last_verified_at', sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'dest_coordinate_source',
                coord_source_enum,
                server_default='BRANCH_VICINITY_ESTIMATE',
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column('dest_confidence', sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'dest_verification_status',
                coord_verification_enum,
                server_default='UNVERIFIED',
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column('dest_last_verified_at', sa.DateTime(), nullable=True))

    # 3. RouteStops additions
    with op.batch_alter_table('route_stops', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'coordinate_source',
                coord_source_enum,
                server_default='BRANCH_VICINITY_ESTIMATE',
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column('confidence', sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'verification_status',
                coord_verification_enum,
                server_default='UNVERIFIED',
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column('last_verified_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('normalized_address', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('time_window_start', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('time_window_end', sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'waiting_time_min',
                sa.Float(),
                server_default=sa.text('0.0'),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                'service_duration_min',
                sa.Float(),
                server_default=sa.text('5.0'),
                nullable=False,
            )
        )

    # 4. Backfill existing data
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE route_stops SET coordinate_source = 'BRANCH_VICINITY_ESTIMATE' "
            "WHERE coordinate_source IS NULL OR coordinate_source = ''"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE parcels SET origin_coordinate_source = 'BRANCH_VICINITY_ESTIMATE' "
            "WHERE origin_coordinate_source IS NULL OR origin_coordinate_source = ''"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE parcels SET dest_coordinate_source = 'BRANCH_VICINITY_ESTIMATE' "
            "WHERE dest_coordinate_source IS NULL OR dest_coordinate_source = ''"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table('route_stops', schema=None) as batch_op:
        batch_op.drop_column('service_duration_min')
        batch_op.drop_column('waiting_time_min')
        batch_op.drop_column('time_window_end')
        batch_op.drop_column('time_window_start')
        batch_op.drop_column('normalized_address')
        batch_op.drop_column('last_verified_at')
        batch_op.drop_column('verification_status')
        batch_op.drop_column('confidence')
        batch_op.drop_column('coordinate_source')

    with op.batch_alter_table('parcels', schema=None) as batch_op:
        batch_op.drop_column('dest_last_verified_at')
        batch_op.drop_column('dest_verification_status')
        batch_op.drop_column('dest_confidence')
        batch_op.drop_column('dest_coordinate_source')
        batch_op.drop_column('origin_last_verified_at')
        batch_op.drop_column('origin_verification_status')
        batch_op.drop_column('origin_confidence')
        batch_op.drop_column('origin_coordinate_source')
        batch_op.drop_column('receiver_normalized_address')
        batch_op.drop_column('sender_normalized_address')

    with op.batch_alter_table('delivery_routes', schema=None) as batch_op:
        batch_op.drop_constraint('fk_delivery_routes_override_user', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_delivery_routes_idempotency_key'))
        batch_op.drop_column('low_confidence_overridden_at')
        batch_op.drop_column('low_confidence_overridden_by_id')
        batch_op.drop_column('low_confidence_override_reason')
        batch_op.drop_column('has_low_confidence_stops')
        batch_op.drop_column('eta_calculated_at')
        batch_op.drop_column('eta_source')
        batch_op.drop_column('last_telemetry_at')
        batch_op.drop_column('current_longitude')
        batch_op.drop_column('current_latitude')
        batch_op.drop_column('idempotency_key')
        batch_op.alter_column(
            'optimization_objective',
            existing_type=new_objective_enum,
            type_=old_objective_enum,
            existing_nullable=False,
        )
