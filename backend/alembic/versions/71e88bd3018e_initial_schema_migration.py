"""Initial schema migration

Revision ID: 71e88bd3018e
Revises: 
Create Date: 2026-11-03 19:58:17.471739

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71e88bd3018e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

operating_status_enum = sa.Enum('ACTIVE', 'INACTIVE', 'UNDER_MAINTENANCE', name='operatingstatus')
user_role_enum = sa.Enum('SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER', 'DELIVERY_AGENT', 'CUSTOMER', name='userrole')
vehicle_type_enum = sa.Enum('BIKE', 'VAN', 'TRUCK', name='vehicletype')
vehicle_status_enum = sa.Enum('AVAILABLE', 'ASSIGNED', 'IN_TRANSIT', 'MAINTENANCE', 'RETIRED', name='vehiclestatus')
service_type_enum = sa.Enum('STANDARD', 'EXPRESS', 'SAME_DAY', 'OVERNIGHT', name='servicetype')
payment_status_enum = sa.Enum('PENDING', 'PAID', 'FAILED', 'REFUNDED', 'CANCELLED', name='paymentstatus')
parcel_status_enum = sa.Enum(
    'BOOKED', 'PICKUP_SCHEDULED', 'PICKED_UP', 'AT_ORIGIN_BRANCH', 'IN_TRANSIT',
    'AT_DESTINATION_BRANCH', 'OUT_FOR_DELIVERY', 'DELIVERED', 'DELIVERY_FAILED',
    'RETURN_TO_ORIGIN', 'CANCELLED', 'ON_HOLD',
    name='parcelstatus'
)
assignment_type_enum = sa.Enum('PICKUP', 'TRANSFER', 'LAST_MILE', name='assignmenttype')
assignment_status_enum = sa.Enum('ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'FAILED', name='assignmentstatus')
scan_type_enum = sa.Enum(
    'PICKUP_VERIFICATION', 'ORIGIN_INWARD', 'HUB_OUTWARD', 'DEST_INWARD',
    'OUT_FOR_DELIVERY', 'DELIVERY_CONFIRMATION',
    name='scantype'
)


def upgrade() -> None:
    # 1. organizations
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('contact_email', sa.String(length=255), nullable=False),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_organizations_id'), 'organizations', ['id'], unique=False)
    op.create_index(op.f('ix_organizations_code'), 'organizations', ['code'], unique=True)

    # 2. branches
    op.create_table(
        'branches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('branch_code', sa.String(length=50), nullable=False),
        sa.Column('branch_name', sa.String(length=255), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=False),
        sa.Column('pincode', sa.String(length=20), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=100), nullable=False),
        sa.Column('country', sa.String(length=100), nullable=False, server_default='India'),
        sa.Column('contact_email', sa.String(length=255), nullable=False),
        sa.Column('contact_phone', sa.String(length=50), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('operating_status', operating_status_enum, nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_branches_id'), 'branches', ['id'], unique=False)
    op.create_index(op.f('ix_branches_organization_id'), 'branches', ['organization_id'], unique=False)
    op.create_index(op.f('ix_branches_branch_code'), 'branches', ['branch_code'], unique=True)
    op.create_index(op.f('ix_branches_pincode'), 'branches', ['pincode'], unique=False)
    op.create_index(op.f('ix_branches_city'), 'branches', ['city'], unique=False)

    # 3. users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('branch_id', sa.Integer(), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('role', user_role_enum, nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_organization_id'), 'users', ['organization_id'], unique=False)
    op.create_index(op.f('ix_users_branch_id'), 'users', ['branch_id'], unique=False)
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)

    # 4. customer_profiles
    op.create_table(
        'customer_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=True),
        sa.Column('gst_number', sa.String(length=50), nullable=True),
        sa.Column('default_pickup_address', sa.Text(), nullable=True),
        sa.Column('default_delivery_address', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_customer_profiles_id'), 'customer_profiles', ['id'], unique=False)

    # 5. vehicles
    op.create_table(
        'vehicles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=True),
        sa.Column('vehicle_number', sa.String(length=50), nullable=False),
        sa.Column('vehicle_type', vehicle_type_enum, nullable=False),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('max_weight_kg', sa.Float(), nullable=False, server_default='500.0'),
        sa.Column('max_volume_cbm', sa.Float(), nullable=True, server_default='5.0'),
        sa.Column('status', vehicle_status_enum, nullable=False),
        sa.Column('assigned_employee_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['assigned_employee_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vehicles_id'), 'vehicles', ['id'], unique=False)
    op.create_index(op.f('ix_vehicles_organization_id'), 'vehicles', ['organization_id'], unique=False)
    op.create_index(op.f('ix_vehicles_branch_id'), 'vehicles', ['branch_id'], unique=False)
    op.create_index(op.f('ix_vehicles_vehicle_number'), 'vehicles', ['vehicle_number'], unique=True)
    op.create_index(op.f('ix_vehicles_status'), 'vehicles', ['status'], unique=False)

    # 6. parcels
    op.create_table(
        'parcels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tracking_number', sa.String(length=50), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('origin_branch_id', sa.Integer(), nullable=False),
        sa.Column('dest_branch_id', sa.Integer(), nullable=False),
        sa.Column('sender_name', sa.String(length=255), nullable=False),
        sa.Column('sender_phone', sa.String(length=50), nullable=False),
        sa.Column('sender_email', sa.String(length=255), nullable=True),
        sa.Column('sender_address', sa.Text(), nullable=False),
        sa.Column('sender_city', sa.String(length=100), nullable=False),
        sa.Column('sender_state', sa.String(length=100), nullable=False),
        sa.Column('sender_pincode', sa.String(length=20), nullable=False),
        sa.Column('receiver_name', sa.String(length=255), nullable=False),
        sa.Column('receiver_phone', sa.String(length=50), nullable=False),
        sa.Column('receiver_email', sa.String(length=255), nullable=True),
        sa.Column('receiver_address', sa.Text(), nullable=False),
        sa.Column('receiver_city', sa.String(length=100), nullable=False),
        sa.Column('receiver_state', sa.String(length=100), nullable=False),
        sa.Column('receiver_pincode', sa.String(length=20), nullable=False),
        sa.Column('weight_kg', sa.Float(), nullable=False),
        sa.Column('length_cm', sa.Float(), nullable=False),
        sa.Column('width_cm', sa.Float(), nullable=False),
        sa.Column('height_cm', sa.Float(), nullable=False),
        sa.Column('volumetric_weight_kg', sa.Float(), nullable=False),
        sa.Column('service_type', service_type_enum, nullable=False),
        sa.Column('base_charge', sa.Float(), nullable=False, server_default='50.0'),
        sa.Column('weight_charge', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('service_charge', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('tax_amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_charge', sa.Float(), nullable=False),
        sa.Column('payment_status', payment_status_enum, nullable=False),
        sa.Column('delivery_status', parcel_status_enum, nullable=False),
        sa.Column('current_location', sa.String(length=255), nullable=True),
        sa.Column('qr_code_data', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('booking_date', sa.DateTime(), nullable=False),
        sa.Column('expected_delivery_date', sa.DateTime(), nullable=True),
        sa.Column('actual_delivery_date', sa.DateTime(), nullable=True),
        sa.Column('cancellation_reason', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['dest_branch_id'], ['branches.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['origin_branch_id'], ['branches.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_parcels_id'), 'parcels', ['id'], unique=False)
    op.create_index(op.f('ix_parcels_tracking_number'), 'parcels', ['tracking_number'], unique=True)
    op.create_index(op.f('ix_parcels_customer_id'), 'parcels', ['customer_id'], unique=False)
    op.create_index(op.f('ix_parcels_origin_branch_id'), 'parcels', ['origin_branch_id'], unique=False)
    op.create_index(op.f('ix_parcels_dest_branch_id'), 'parcels', ['dest_branch_id'], unique=False)
    op.create_index(op.f('ix_parcels_delivery_status'), 'parcels', ['delivery_status'], unique=False)

    # 7. delivery_assignments
    op.create_table(
        'delivery_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('parcel_id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('vehicle_id', sa.Integer(), nullable=True),
        sa.Column('assignment_type', assignment_type_enum, nullable=False),
        sa.Column('status', assignment_status_enum, nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['parcel_id'], ['parcels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_delivery_assignments_id'), 'delivery_assignments', ['id'], unique=False)
    op.create_index(op.f('ix_delivery_assignments_parcel_id'), 'delivery_assignments', ['parcel_id'], unique=False)
    op.create_index(op.f('ix_delivery_assignments_employee_id'), 'delivery_assignments', ['employee_id'], unique=False)
    op.create_index(op.f('ix_delivery_assignments_vehicle_id'), 'delivery_assignments', ['vehicle_id'], unique=False)
    op.create_index(op.f('ix_delivery_assignments_status'), 'delivery_assignments', ['status'], unique=False)

    # 8. tracking_history
    op.create_table(
        'tracking_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('parcel_id', sa.Integer(), nullable=False),
        sa.Column('status', parcel_status_enum, nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=True),
        sa.Column('employee_id', sa.Integer(), nullable=True),
        sa.Column('location_name', sa.String(length=255), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['employee_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['parcel_id'], ['parcels.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tracking_history_id'), 'tracking_history', ['id'], unique=False)
    op.create_index(op.f('ix_tracking_history_parcel_id'), 'tracking_history', ['parcel_id'], unique=False)
    op.create_index(op.f('ix_tracking_history_created_at'), 'tracking_history', ['created_at'], unique=False)

    # 9. custody_scans
    op.create_table(
        'custody_scans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('parcel_id', sa.Integer(), nullable=False),
        sa.Column('scanned_by_id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=True),
        sa.Column('scan_type', scan_type_enum, nullable=False),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['parcel_id'], ['parcels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scanned_by_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_custody_scans_id'), 'custody_scans', ['id'], unique=False)
    op.create_index(op.f('ix_custody_scans_parcel_id'), 'custody_scans', ['parcel_id'], unique=False)
    op.create_index(op.f('ix_custody_scans_scanned_by_id'), 'custody_scans', ['scanned_by_id'], unique=False)
    op.create_index(op.f('ix_custody_scans_created_at'), 'custody_scans', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('custody_scans')
    op.drop_table('tracking_history')
    op.drop_table('delivery_assignments')
    op.drop_table('parcels')
    op.drop_table('vehicles')
    op.drop_table('customer_profiles')
    op.drop_table('users')
    op.drop_table('branches')
    op.drop_table('organizations')

    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        for enum_name in [
            'scantype', 'assignmentstatus', 'assignmenttype',
            'parcelstatus', 'paymentstatus', 'servicetype',
            'vehiclestatus', 'vehicletype', 'userrole', 'operatingstatus'
        ]:
            op.execute(f"DROP TYPE IF EXISTS {enum_name} CASCADE")
