import pytest
from fastapi import HTTPException
from app.models.parcel import Parcel
from app.models.enums import ParcelStatus, UserRole, ServiceType, PaymentStatus
from app.models.branch import Branch
from app.models.user import User
from app.services.state_machine import ShipmentStateMachine
from app.core.security import create_access_token


def auth_headers(user):
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


def test_optimistic_locking_conflict_detection(db_session):
    """AC3: Transition with an outdated expected_version must raise 409 Conflict."""
    branch = db_session.query(Branch).first()
    admin = db_session.query(User).filter(User.role == UserRole.ORG_ADMIN).first()

    parcel = Parcel(
        tracking_number="LF-CONC-001",
        origin_branch_id=branch.id,
        dest_branch_id=branch.id,
        sender_name="Sender",
        sender_phone="9988776655",
        sender_address="Addr 1",
        sender_city=branch.city,
        sender_state=branch.state,
        sender_pincode=branch.pincode,
        receiver_name="Receiver",
        receiver_phone="9988776654",
        receiver_address="Addr 2",
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
    db_session.commit()
    db_session.refresh(parcel)

    # First transition increments version to 2
    ShipmentStateMachine.transition(
        db=db_session,
        current_user=admin,
        parcel=parcel,
        to_status=ParcelStatus.AT_ORIGIN_BRANCH,
        expected_version=1
    )
    assert parcel.delivery_status == ParcelStatus.AT_ORIGIN_BRANCH
    assert parcel.version_id == 2

    # Second transition attempting with stale version 1 must raise 409 Conflict
    with pytest.raises(HTTPException) as exc_info:
        ShipmentStateMachine.transition(
            db=db_session,
            current_user=admin,
            parcel=parcel,
            to_status=ParcelStatus.IN_TRANSIT,
            expected_version=1  # Stale version!
        )
    assert exc_info.value.status_code == 409
    assert "conflict" in exc_info.value.detail.lower()


def test_concurrent_conflicting_transitions_produce_one_success(client, db_session):
    """AC3: Two simultaneous conflicting update requests produce exactly 1 success (200) and 1 conflict (409)."""
    branch = db_session.query(Branch).first()
    admin = db_session.query(User).filter(User.role == UserRole.ORG_ADMIN).first()
    hdrs = auth_headers(admin)

    parcel = Parcel(
        tracking_number="LF-CONC-002",
        origin_branch_id=branch.id,
        dest_branch_id=branch.id,
        sender_name="Sender",
        sender_phone="9988776655",
        sender_address="Addr 1",
        sender_city=branch.city,
        sender_state=branch.state,
        sender_pincode=branch.pincode,
        receiver_name="Receiver",
        receiver_phone="9988776654",
        receiver_address="Addr 2",
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
    db_session.commit()
    db_session.refresh(parcel)

    initial_version = parcel.version_id
    assert initial_version == 1

    # Request 1 arrives with initial_version (1)
    res1 = client.post(
        f"/api/v1/tracking/{parcel.tracking_number}/update",
        json={"status": "AT_ORIGIN_BRANCH", "expected_version": initial_version},
        headers=hdrs
    )
    assert res1.status_code == 200, res1.text

    # Request 2 (conflicting concurrent update initialized at same time with stale initial_version 1)
    res2 = client.post(
        f"/api/v1/tracking/{parcel.tracking_number}/update",
        json={"status": "CANCELLED", "expected_version": initial_version},
        headers=hdrs
    )
    assert res2.status_code == 409
    assert "conflict" in res2.json()["detail"].lower()

    # Verify parcel state is preserved from first valid transition
    db_session.refresh(parcel)
    assert parcel.delivery_status == ParcelStatus.AT_ORIGIN_BRANCH
    assert parcel.version_id == 2
