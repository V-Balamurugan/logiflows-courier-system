import pytest
from unittest.mock import patch
from fastapi import HTTPException
from app.models.organization import Organization
from app.models.branch import Branch
from app.models.user import User
from app.models.parcel import Parcel
from app.models.tracking import TrackingHistory
from app.models.enums import UserRole, OperatingStatus, ServiceType, PaymentStatus, ParcelStatus
from app.core.security import create_access_token, get_password_hash
from app.services.state_machine import ShipmentStateMachine


def auth_headers(user):
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def tracking_test_data(db_session):
    org = db_session.query(Organization).filter(Organization.code == "TRK_ORG").first()
    if not org:
        org = Organization(name="Tracking Org", code="TRK_ORG", contact_email="trk@org.com", is_active=True)
        db_session.add(org)
        db_session.flush()

    branch = db_session.query(Branch).filter(Branch.branch_code == "TRK_B1").first()
    if not branch:
        branch = Branch(
            organization_id=org.id,
            branch_code="TRK_B1",
            branch_name="Branch TRK 1",
            address="Addr TRK1",
            pincode="220001",
            city="City TRK",
            state="State TRK",
            country="India",
            contact_email="btrk@org.com",
            contact_phone="9988001122",
            operating_status=OperatingStatus.ACTIVE,
            is_active=True
        )
        db_session.add(branch)
        db_session.flush()

    admin = db_session.query(User).filter(User.email == "admin@trk.com").first()
    if not admin:
        admin = User(
            email="admin@trk.com",
            hashed_password=get_password_hash("AdminPass123!"),
            full_name="Admin TRK",
            role=UserRole.ORG_ADMIN,
            organization_id=org.id,
            branch_id=branch.id,
            is_active=True
        )
        db_session.add(admin)
        db_session.flush()

    customer = db_session.query(User).filter(User.email == "cust@trk.com").first()
    if not customer:
        customer = User(
            email="cust@trk.com",
            hashed_password=get_password_hash("CustPass123!"),
            full_name="Cust TRK",
            role=UserRole.CUSTOMER,
            is_active=True
        )
        db_session.add(customer)
        db_session.flush()

    parcel = db_session.query(Parcel).filter(Parcel.tracking_number == "LF-TRK-TEST-001").first()
    if not parcel:
        parcel = Parcel(
            tracking_number="LF-TRK-TEST-001",
            customer_id=customer.id,
            origin_branch_id=branch.id,
            dest_branch_id=branch.id,
            sender_name="Sender TRK",
            sender_phone="9988112233",
            sender_address="Addr TRK 1",
            sender_city=branch.city,
            sender_state=branch.state,
            sender_pincode=branch.pincode,
            receiver_name="Receiver TRK",
            receiver_phone="9988112234",
            receiver_address="Addr TRK 2",
            receiver_city=branch.city,
            receiver_state=branch.state,
            receiver_pincode=branch.pincode,
            weight_kg=1.0,
            length_cm=10.0,
            width_cm=10.0,
            height_cm=10.0,
            volumetric_weight_kg=0.2,
            service_type=ServiceType.STANDARD,
            base_charge=50.0,
            total_charge=50.0,
            payment_status=PaymentStatus.PAID,
            delivery_status=ParcelStatus.BOOKED,
            version_id=1
        )
        db_session.add(parcel)
        db_session.flush()

    db_session.commit()
    return {
        "org": org,
        "branch": branch,
        "admin": admin,
        "customer": customer,
        "parcel": parcel
    }


def test_successful_transition_creates_atomic_tracking_history_record(db_session, tracking_test_data):
    """AC4 & AC6: Successful transition atomically creates an append-only tracking record with full audit metadata."""
    parcel = tracking_test_data["parcel"]
    admin = tracking_test_data["admin"]
    branch = tracking_test_data["branch"]

    initial_history_count = db_session.query(TrackingHistory).filter(TrackingHistory.parcel_id == parcel.id).count()

    # Perform transition
    updated = ShipmentStateMachine.transition(
        db=db_session,
        current_user=admin,
        parcel=parcel,
        to_status=ParcelStatus.AT_ORIGIN_BRANCH,
        remarks="Received at hub",
        location_name="Origin Hub Facility",
        branch_id=branch.id,
        source="API"
    )

    assert updated.delivery_status == ParcelStatus.AT_ORIGIN_BRANCH
    assert updated.version_id == 2

    # Check tracking history record was created
    new_history_count = db_session.query(TrackingHistory).filter(TrackingHistory.parcel_id == parcel.id).count()
    assert new_history_count == initial_history_count + 1

    latest_record = db_session.query(TrackingHistory).filter(
        TrackingHistory.parcel_id == parcel.id
    ).order_by(TrackingHistory.id.desc()).first()

    assert latest_record.from_status == ParcelStatus.BOOKED
    assert latest_record.status == ParcelStatus.AT_ORIGIN_BRANCH
    assert latest_record.source == "API"
    assert latest_record.employee_id == admin.id
    assert latest_record.branch_id == branch.id
    assert latest_record.location_name == "Origin Hub Facility"
    assert latest_record.remarks == "Received at hub"


def test_failed_transition_creates_zero_tracking_events(db_session, tracking_test_data):
    """AC6: A failed transition leaves no orphan tracking record, and parcel status is unaltered."""
    parcel = tracking_test_data["parcel"]
    customer = tracking_test_data["customer"]

    # Customer tries unauthorized transition to IN_TRANSIT
    initial_count = db_session.query(TrackingHistory).filter(TrackingHistory.parcel_id == parcel.id).count()
    current_status = parcel.delivery_status
    current_version = parcel.version_id

    with pytest.raises(HTTPException) as exc_info:
        ShipmentStateMachine.transition(
            db=db_session,
            current_user=customer,
            parcel=parcel,
            to_status=ParcelStatus.IN_TRANSIT,
            source="API"
        )

    assert exc_info.value.status_code == 403

    db_session.rollback()
    db_session.refresh(parcel)

    final_count = db_session.query(TrackingHistory).filter(TrackingHistory.parcel_id == parcel.id).count()
    assert final_count == initial_count
    assert parcel.delivery_status == current_status
    assert parcel.version_id == current_version


def test_tracking_endpoints_are_append_only_no_delete_or_put(client, tracking_test_data):
    """AC4: No update or delete endpoints exist for tracking history (append-only enforcement)."""
    admin_hdrs = auth_headers(tracking_test_data["admin"])

    # Attempt PUT on tracking history
    res_put = client.put("/api/v1/tracking/1", json={"remarks": "tampered"}, headers=admin_hdrs)
    assert res_put.status_code in [404, 405]

    # Attempt PATCH on tracking history
    res_patch = client.patch("/api/v1/tracking/1", json={"remarks": "tampered"}, headers=admin_hdrs)
    assert res_patch.status_code in [404, 405]

    # Attempt DELETE on tracking history
    res_delete = client.delete("/api/v1/tracking/1", headers=admin_hdrs)
    assert res_delete.status_code in [404, 405]


def test_transaction_rollback_atomicity(db_session, tracking_test_data):
    """AC6: If an exception occurs before commit, both parcel status and tracking event are cleanly rolled back."""
    parcel = tracking_test_data["parcel"]
    admin = tracking_test_data["admin"]
    initial_status = parcel.delivery_status
    initial_version = parcel.version_id
    initial_count = db_session.query(TrackingHistory).filter(TrackingHistory.parcel_id == parcel.id).count()

    # Simulate an error during transition by mocking db.commit to raise an exception
    with patch.object(db_session, "commit", side_effect=RuntimeError("Database write error")):
        with pytest.raises(RuntimeError):
            ShipmentStateMachine.transition(
                db=db_session,
                current_user=admin,
                parcel=parcel,
                to_status=ParcelStatus.IN_TRANSIT if initial_status == ParcelStatus.AT_ORIGIN_BRANCH else ParcelStatus.AT_ORIGIN_BRANCH,
                source="API"
            )

    db_session.rollback()
    db_session.refresh(parcel)

    # Verify parcel status and version were NOT modified
    assert parcel.delivery_status == initial_status
    assert parcel.version_id == initial_version

    # Verify no orphan tracking event was persisted
    post_count = db_session.query(TrackingHistory).filter(TrackingHistory.parcel_id == parcel.id).count()
    assert post_count == initial_count
