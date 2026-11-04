import pytest
from fastapi import HTTPException
from app.models.parcel import Parcel
from app.models.enums import ParcelStatus, UserRole, OperatingStatus, ServiceType, PaymentStatus
from app.models.branch import Branch
from app.models.user import User
from app.services.state_machine import ShipmentStateMachine, TRANSITION_TABLE, TERMINAL_STATES


@pytest.fixture
def state_test_setup(db_session):
    branch = db_session.query(Branch).first()
    admin = db_session.query(User).filter(User.role == UserRole.ORG_ADMIN).first()
    agent = db_session.query(User).filter(User.role == UserRole.DELIVERY_AGENT).first()
    cust = db_session.query(User).filter(User.role == UserRole.CUSTOMER).first()

    return {
        "branch": branch,
        "admin": admin,
        "agent": agent,
        "customer": cust
    }


def create_test_parcel(db, branch, customer, status=ParcelStatus.BOOKED):
    p = Parcel(
        tracking_number=f"LF-TEST-{status.value}",
        customer_id=customer.id if customer else None,
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
        delivery_status=status
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_transition_table_completeness():
    """AC2: Every defined transition in TRANSITION_TABLE must have valid from and to statuses."""
    for (from_s, to_s), rule in TRANSITION_TABLE.items():
        assert isinstance(from_s, ParcelStatus)
        assert isinstance(to_s, ParcelStatus)
        assert len(rule.allowed_roles) > 0


def test_terminal_states_reject_any_transition(db_session, state_test_setup):
    """AC2: Terminal states allow no further transitions."""
    admin = state_test_setup["admin"]
    branch = state_test_setup["branch"]

    for term_status in TERMINAL_STATES:
        p = create_test_parcel(db_session, branch, state_test_setup["customer"], status=term_status)
        with pytest.raises(HTTPException) as exc_info:
            ShipmentStateMachine.transition(
                db=db_session,
                current_user=admin,
                parcel=p,
                to_status=ParcelStatus.IN_TRANSIT
            )
        assert exc_info.value.status_code == 400
        assert "terminal state" in exc_info.value.detail.lower()


def test_disallowed_transition_fails(db_session, state_test_setup):
    """AC2: Disallowed state pair (e.g. BOOKED -> DELIVERED) fails with 400."""
    admin = state_test_setup["admin"]
    branch = state_test_setup["branch"]

    p = create_test_parcel(db_session, branch, state_test_setup["customer"], status=ParcelStatus.BOOKED)
    with pytest.raises(HTTPException) as exc_info:
        ShipmentStateMachine.transition(
            db=db_session,
            current_user=admin,
            parcel=p,
            to_status=ParcelStatus.DELIVERED
        )
    assert exc_info.value.status_code == 400
    assert "illegal state transition" in exc_info.value.detail.lower()


def test_unauthorized_role_transition_fails(db_session, state_test_setup):
    """AC2: Role unauthorized for transition fails with 403."""
    agent = state_test_setup["agent"]
    branch = state_test_setup["branch"]

    p = create_test_parcel(db_session, branch, state_test_setup["customer"], status=ParcelStatus.AT_ORIGIN_BRANCH)
    # Delivery Agent is not allowed to transition AT_ORIGIN_BRANCH -> IN_TRANSIT
    with pytest.raises(HTTPException) as exc_info:
        ShipmentStateMachine.transition(
            db=db_session,
            current_user=agent,
            parcel=p,
            to_status=ParcelStatus.IN_TRANSIT
        )
    assert exc_info.value.status_code == 403
    assert "not authorized" in exc_info.value.detail.lower()


def test_out_for_delivery_precondition_requires_assignment(db_session, state_test_setup):
    """AC2: Transition to OUT_FOR_DELIVERY requires active assignment."""
    admin = state_test_setup["admin"]
    branch = state_test_setup["branch"]

    p = create_test_parcel(db_session, branch, state_test_setup["customer"], status=ParcelStatus.AT_DESTINATION_BRANCH)
    with pytest.raises(HTTPException) as exc_info:
        ShipmentStateMachine.transition(
            db=db_session,
            current_user=admin,
            parcel=p,
            to_status=ParcelStatus.OUT_FOR_DELIVERY
        )
    assert exc_info.value.status_code == 400
    assert "without an active delivery assignment" in exc_info.value.detail.lower()
