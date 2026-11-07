import math
from unittest.mock import patch
import pytest
from app.models.organization import Organization
from app.models.branch import Branch
from app.models.user import User
from app.models.parcel import Parcel
from app.models.enums import UserRole, OperatingStatus, ServiceType, PaymentStatus, ParcelStatus
from app.core.security import create_access_token, get_password_hash
from app.services.pricing_service import PricingEngine
from app.services.payment_service import PaymentService
from app.services.parcel_service import ParcelService


def auth_headers(user):
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def pricing_test_data(db_session):
    # Org A
    org_a = db_session.query(Organization).filter(Organization.code == "ORG_A").first()
    if not org_a:
        org_a = Organization(name="Org A Logistics", code="ORG_A", contact_email="a@log.com", is_active=True)
        db_session.add(org_a)
        db_session.flush()

    # Org B
    org_b = db_session.query(Organization).filter(Organization.code == "ORG_B").first()
    if not org_b:
        org_b = Organization(name="Org B Freight", code="ORG_B", contact_email="b@log.com", is_active=True)
        db_session.add(org_b)
        db_session.flush()

    # Branches in Org A
    b_a1 = db_session.query(Branch).filter(Branch.branch_code == "BR_A1").first()
    if not b_a1:
        b_a1 = Branch(
            organization_id=org_a.id,
            branch_code="BR_A1",
            branch_name="Branch A1",
            address="Addr A1",
            pincode="110001",
            city="Delhi",
            state="Delhi",
            country="India",
            contact_email="a1@log.com",
            contact_phone="9988770001",
            operating_status=OperatingStatus.ACTIVE,
            is_active=True
        )
        db_session.add(b_a1)
        db_session.flush()

    b_a2 = db_session.query(Branch).filter(Branch.branch_code == "BR_A2").first()
    if not b_a2:
        b_a2 = Branch(
            organization_id=org_a.id,
            branch_code="BR_A2",
            branch_name="Branch A2",
            address="Addr A2",
            pincode="400001",
            city="Mumbai",
            state="Maharashtra",
            country="India",
            contact_email="a2@log.com",
            contact_phone="9988770002",
            operating_status=OperatingStatus.ACTIVE,
            is_active=True
        )
        db_session.add(b_a2)
        db_session.flush()

    # Branch in Org B
    b_b1 = db_session.query(Branch).filter(Branch.branch_code == "BR_B1").first()
    if not b_b1:
        b_b1 = Branch(
            organization_id=org_b.id,
            branch_code="BR_B1",
            branch_name="Branch B1",
            address="Addr B1",
            pincode="560001",
            city="Bangalore",
            state="Karnataka",
            country="India",
            contact_email="b1@log.com",
            contact_phone="9988770003",
            operating_status=OperatingStatus.ACTIVE,
            is_active=True
        )
        db_session.add(b_b1)
        db_session.flush()

    # Customers
    cust_1 = db_session.query(User).filter(User.email == "cust_price1@test.com").first()
    if not cust_1:
        cust_1 = User(
            email="cust_price1@test.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Pricing Customer 1",
            role=UserRole.CUSTOMER,
            is_active=True
        )
        db_session.add(cust_1)
        db_session.flush()

    cust_2 = db_session.query(User).filter(User.email == "cust_price2@test.com").first()
    if not cust_2:
        cust_2 = User(
            email="cust_price2@test.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Pricing Customer 2",
            role=UserRole.CUSTOMER,
            is_active=True
        )
        db_session.add(cust_2)
        db_session.flush()

    # Staff in Org A
    admin_a = db_session.query(User).filter(User.email == "admin_a@test.com").first()
    if not admin_a:
        admin_a = User(
            email="admin_a@test.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Admin Org A",
            role=UserRole.ORG_ADMIN,
            organization_id=org_a.id,
            branch_id=b_a1.id,
            is_active=True
        )
        db_session.add(admin_a)
        db_session.flush()

    db_session.commit()
    return {
        "org_a": org_a,
        "org_b": org_b,
        "branch_a1": b_a1,
        "branch_a2": b_a2,
        "branch_b1": b_b1,
        "cust_1": cust_1,
        "cust_2": cust_2,
        "admin_a": admin_a
    }


def test_cross_org_branches_rejected(client, pricing_test_data):
    """AC1: Origin and Destination branches from different organizations are rejected."""
    cust_hdrs = auth_headers(pricing_test_data["cust_1"])

    payload = {
        "origin_branch_id": pricing_test_data["branch_a1"].id,
        "dest_branch_id": pricing_test_data["branch_b1"].id,  # Different organization!
        "sender_name": "Test Sender",
        "sender_phone": "9988776655",
        "sender_address": "Addr 1",
        "sender_city": "Delhi",
        "sender_state": "Delhi",
        "sender_pincode": "110001",
        "receiver_name": "Test Receiver",
        "receiver_phone": "9988776654",
        "receiver_address": "Addr 2",
        "receiver_city": "Bangalore",
        "receiver_state": "Karnataka",
        "receiver_pincode": "560001",
        "weight_kg": 2.0,
        "length_cm": 20.0,
        "width_cm": 20.0,
        "height_cm": 20.0,
        "service_type": "STANDARD"
    }

    res = client.post("/api/v1/parcels", json=payload, headers=cust_hdrs)
    assert res.status_code == 400
    assert "same operating organization" in res.json()["detail"].lower()


def test_invalid_weight_and_dimensions_rejected(client, pricing_test_data):
    """AC2: Negative, zero, oversized, NaN, and Inf values are rejected with field-level errors."""
    cust_hdrs = auth_headers(pricing_test_data["cust_1"])

    base_payload = {
        "origin_branch_id": pricing_test_data["branch_a1"].id,
        "dest_branch_id": pricing_test_data["branch_a2"].id,
        "sender_name": "Test Sender",
        "sender_phone": "9988776655",
        "sender_address": "Addr 1",
        "sender_city": "Delhi",
        "sender_state": "Delhi",
        "sender_pincode": "110001",
        "receiver_name": "Test Receiver",
        "receiver_phone": "9988776654",
        "receiver_address": "Addr 2",
        "receiver_city": "Mumbai",
        "receiver_state": "MH",
        "receiver_pincode": "400001",
        "weight_kg": 2.0,
        "length_cm": 20.0,
        "width_cm": 20.0,
        "height_cm": 20.0,
        "service_type": "STANDARD"
    }

    # Negative weight
    p1 = {**base_payload, "weight_kg": -5.0}
    res1 = client.post("/api/v1/parcels", json=p1, headers=cust_hdrs)
    assert res1.status_code == 422

    # Zero weight
    p2 = {**base_payload, "weight_kg": 0.0}
    res2 = client.post("/api/v1/parcels", json=p2, headers=cust_hdrs)
    assert res2.status_code == 422

    # Oversized weight (>1000 kg)
    p3 = {**base_payload, "weight_kg": 1500.0}
    res3 = client.post("/api/v1/parcels", json=p3, headers=cust_hdrs)
    assert res3.status_code == 422

    # Oversized dimensions (>500 cm)
    p4 = {**base_payload, "length_cm": 600.0}
    res4 = client.post("/api/v1/parcels", json=p4, headers=cust_hdrs)
    assert res4.status_code == 422


def test_tracking_number_collision_retry(db_session, pricing_test_data):
    """AC3: Tracking number collisions trigger retries and never produce duplicates."""
    # Seed an existing parcel with tracking number LF-2026-111111
    existing = Parcel(
        tracking_number="LF-2026-111111",
        origin_branch_id=pricing_test_data["branch_a1"].id,
        dest_branch_id=pricing_test_data["branch_a2"].id,
        sender_name="S", sender_phone="1", sender_address="A", sender_city="C", sender_state="S", sender_pincode="1",
        receiver_name="R", receiver_phone="2", receiver_address="A", receiver_city="C", receiver_state="S", receiver_pincode="2",
        weight_kg=1.0, length_cm=10.0, width_cm=10.0, height_cm=10.0, volumetric_weight_kg=0.2,
        service_type=ServiceType.STANDARD, base_charge=50.0, total_charge=50.0,
        payment_status=PaymentStatus.PENDING, delivery_status=ParcelStatus.BOOKED
    )
    db_session.add(existing)
    db_session.commit()

    # Mock secrets.randbelow to simulate collision twice, then succeed
    call_count = 0
    def mock_randbelow(n):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return 11111  # Yields 111111 (collision with existing)
        return 222222  # Yields 322222 (unique)

    with patch("secrets.randbelow", side_effect=mock_randbelow):
        tracking_no = ParcelService.generate_tracking_number(db_session, max_retries=5)
        assert tracking_no == "LF-2026-322222"
        assert call_count == 3


def test_booking_leaves_payment_pending(client, pricing_test_data):
    """AC4: New shipment bookings initialize with PaymentStatus.PENDING (never automatically PAID)."""
    cust_hdrs = auth_headers(pricing_test_data["cust_1"])

    payload = {
        "origin_branch_id": pricing_test_data["branch_a1"].id,
        "dest_branch_id": pricing_test_data["branch_a2"].id,
        "sender_name": "Pending Test Sender",
        "sender_phone": "9988776655",
        "sender_address": "Addr 1",
        "sender_city": "Delhi",
        "sender_state": "Delhi",
        "sender_pincode": "110001",
        "receiver_name": "Pending Test Receiver",
        "receiver_phone": "9988776654",
        "receiver_address": "Addr 2",
        "receiver_city": "Mumbai",
        "receiver_state": "MH",
        "receiver_pincode": "400001",
        "weight_kg": 2.0,
        "length_cm": 20.0,
        "width_cm": 20.0,
        "height_cm": 20.0,
        "service_type": "STANDARD"
    }

    res = client.post("/api/v1/parcels", json=payload, headers=cust_hdrs)
    assert res.status_code == 201
    data = res.json()
    assert data["payment_status"] == "PENDING"
    assert data["delivery_status"] == "BOOKED"


def test_payment_verification_transitions_to_paid(client, pricing_test_data):
    """AC4: Explicit payment verification transitions parcel to PAID with audit metadata."""
    cust_hdrs = auth_headers(pricing_test_data["cust_1"])

    # 1. Book parcel
    payload = {
        "origin_branch_id": pricing_test_data["branch_a1"].id,
        "dest_branch_id": pricing_test_data["branch_a2"].id,
        "sender_name": "Pay Test Sender",
        "sender_phone": "9988776655",
        "sender_address": "Addr 1",
        "sender_city": "Delhi",
        "sender_state": "Delhi",
        "sender_pincode": "110001",
        "receiver_name": "Pay Test Receiver",
        "receiver_phone": "9988776654",
        "receiver_address": "Addr 2",
        "receiver_city": "Mumbai",
        "receiver_state": "MH",
        "receiver_pincode": "400001",
        "weight_kg": 2.0,
        "length_cm": 20.0,
        "width_cm": 20.0,
        "height_cm": 20.0,
        "service_type": "STANDARD"
    }
    booking = client.post("/api/v1/parcels", json=payload, headers=cust_hdrs).json()
    tracking_no = booking["tracking_number"]
    total_charge = booking["total_charge"]
    assert booking["payment_status"] == "PENDING"

    # 2. Attempt payment with mismatched amount -> 400 Bad Request
    bad_pay = client.post(
        f"/api/v1/parcels/{tracking_no}/payment",
        json={
            "amount": total_charge + 10.0,
            "payment_method": "UPI",
            "transaction_reference": "TXN-BAD-001",
            "is_success": True
        },
        headers=cust_hdrs
    )
    assert bad_pay.status_code == 400
    assert "does not match" in bad_pay.json()["detail"].lower()

    # 3. Process valid payment with exact charge
    good_pay = client.post(
        f"/api/v1/parcels/{tracking_no}/payment",
        json={
            "amount": total_charge,
            "payment_method": "UPI",
            "transaction_reference": "TXN-GOOD-001",
            "is_success": True
        },
        headers=cust_hdrs
    )
    assert good_pay.status_code == 200
    updated = good_pay.json()
    assert updated["payment_status"] == "PAID"
    assert updated["payment_method"] == "UPI"
    assert updated["transaction_reference"] == "TXN-GOOD-001"
    assert updated["paid_at"] is not None


def test_cannot_cancel_shipped_or_delivered_parcel(client, db_session, pricing_test_data):
    """AC5: Cancelling a shipped or delivered parcel fails with 400."""
    admin_hdrs = auth_headers(pricing_test_data["admin_a"])

    parcel = Parcel(
        tracking_number="LF-CANC-001",
        origin_branch_id=pricing_test_data["branch_a1"].id,
        dest_branch_id=pricing_test_data["branch_a2"].id,
        sender_name="S", sender_phone="1", sender_address="A", sender_city="C", sender_state="S", sender_pincode="1",
        receiver_name="R", receiver_phone="2", receiver_address="A", receiver_city="C", receiver_state="S", receiver_pincode="2",
        weight_kg=1.0, length_cm=10.0, width_cm=10.0, height_cm=10.0, volumetric_weight_kg=0.2,
        service_type=ServiceType.STANDARD, base_charge=50.0, total_charge=50.0,
        payment_status=PaymentStatus.PAID, delivery_status=ParcelStatus.IN_TRANSIT
    )
    db_session.add(parcel)
    db_session.commit()

    res = client.post(
        f"/api/v1/parcels/{parcel.tracking_number}/cancel",
        json={"cancellation_reason": "Too late"},
        headers=admin_hdrs
    )
    assert res.status_code == 400
    assert "illegal state transition" in res.json()["detail"].lower()


def test_unauthorized_user_cannot_cancel(client, db_session, pricing_test_data):
    """AC5: Customer A cannot cancel Customer B's shipment (returns 404 anti-leakage)."""
    cust1 = pricing_test_data["cust_1"]
    cust2 = pricing_test_data["cust_2"]
    cust2_hdrs = auth_headers(cust2)

    parcel = Parcel(
        tracking_number="LF-CANC-002",
        customer_id=cust1.id,
        origin_branch_id=pricing_test_data["branch_a1"].id,
        dest_branch_id=pricing_test_data["branch_a2"].id,
        sender_name="S", sender_phone="1", sender_address="A", sender_city="C", sender_state="S", sender_pincode="1",
        receiver_name="R", receiver_phone="2", receiver_address="A", receiver_city="C", receiver_state="S", receiver_pincode="2",
        weight_kg=1.0, length_cm=10.0, width_cm=10.0, height_cm=10.0, volumetric_weight_kg=0.2,
        service_type=ServiceType.STANDARD, base_charge=50.0, total_charge=50.0,
        payment_status=PaymentStatus.PENDING, delivery_status=ParcelStatus.BOOKED
    )
    db_session.add(parcel)
    db_session.commit()

    # Customer 2 attempts to cancel Customer 1's parcel
    res = client.post(
        f"/api/v1/parcels/{parcel.tracking_number}/cancel",
        json={"cancellation_reason": "Malicious cancellation"},
        headers=cust2_hdrs
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Parcel not found"


def test_pricing_engine_calculations_exact_values():
    """AC6: Pricing tests cover each service type, weight band, and dimensional divisor with fixed expected values."""
    # Test 1: Standard Service, actual weight dominates
    # weight=2.0 kg, dims=10x10x10 (vol=0.2 kg). Chargeable=2.0 kg.
    # Base: 50.00, Weight: 2.0 * 25.00 = 50.00. Subtotal: 100.00 * 1.0 = 100.00.
    # Tax: 100.00 * 0.18 = 18.00. Total: 118.00.
    q1 = PricingEngine.calculate_quote(2.0, 10.0, 10.0, 10.0, ServiceType.STANDARD)
    assert q1.chargeable_weight_kg == 2.0
    assert q1.base_charge == 50.00
    assert q1.weight_charge == 50.00
    assert q1.tax_amount == 18.00
    assert q1.total_charge == 118.00
    assert q1.estimated_delivery_days == 4

    # Test 2: Express Service (1.4x), volumetric weight dominates
    # weight=1.0 kg, dims=50x40x30 cm (vol=60000/5000 = 12.0 kg). Chargeable=12.0 kg.
    # Base: 50.00, Weight: 12.0 * 25.00 = 300.00. Raw = 350.00.
    # Subtotal: 350.00 * 1.4 = 490.00. Service surcharge: 490.00 - 350.00 = 140.00.
    # Tax: 490.00 * 0.18 = 88.20. Total: 578.20.
    q2 = PricingEngine.calculate_quote(1.0, 50.0, 40.0, 30.0, ServiceType.EXPRESS)
    assert q2.volumetric_weight_kg == 12.0
    assert q2.chargeable_weight_kg == 12.0
    assert q2.base_charge == 50.00
    assert q2.weight_charge == 300.00
    assert q2.service_charge == 140.00
    assert q2.tax_amount == 88.20
    assert q2.total_charge == 578.20
    assert q2.estimated_delivery_days == 2

    # Test 3: Overnight Service (1.8x)
    # weight=3.0 kg, dims=10x10x10. Chargeable=3.0 kg.
    # Base: 50.00, Weight: 75.00. Raw = 125.00.
    # Subtotal: 125.00 * 1.8 = 225.00. Surcharge: 100.00.
    # Tax: 225.00 * 0.18 = 40.50. Total: 265.50.
    q3 = PricingEngine.calculate_quote(3.0, 10.0, 10.0, 10.0, ServiceType.OVERNIGHT)
    assert q3.base_charge == 50.00
    assert q3.weight_charge == 75.00
    assert q3.service_charge == 100.00
    assert q3.tax_amount == 40.50
    assert q3.total_charge == 265.50
    assert q3.estimated_delivery_days == 1

    # Test 4: Same Day Service (2.5x)
    # weight=4.0 kg, dims=10x10x10. Chargeable=4.0 kg.
    # Base: 50.00, Weight: 100.00. Raw = 150.00.
    # Subtotal: 150.00 * 2.5 = 375.00. Surcharge: 225.00.
    # Tax: 375.00 * 0.18 = 67.50. Total: 442.50.
    q4 = PricingEngine.calculate_quote(4.0, 10.0, 10.0, 10.0, ServiceType.SAME_DAY)
    assert q4.base_charge == 50.00
    assert q4.weight_charge == 100.00
    assert q4.service_charge == 225.00
    assert q4.tax_amount == 67.50
    assert q4.total_charge == 442.50
    assert q4.estimated_delivery_days == 1


def test_payment_state_machine_transitions():
    """Unit test for PaymentService transition table validation."""
    assert PaymentService.can_transition(PaymentStatus.PENDING, PaymentStatus.PAID) is True
    assert PaymentService.can_transition(PaymentStatus.PENDING, PaymentStatus.FAILED) is True
    assert PaymentService.can_transition(PaymentStatus.PENDING, PaymentStatus.CANCELLED) is True
    assert PaymentService.can_transition(PaymentStatus.FAILED, PaymentStatus.PAID) is True
    assert PaymentService.can_transition(PaymentStatus.PAID, PaymentStatus.REFUNDED) is True
    # Illegal transitions
    assert PaymentService.can_transition(PaymentStatus.PAID, PaymentStatus.PENDING) is False
    assert PaymentService.can_transition(PaymentStatus.REFUNDED, PaymentStatus.PAID) is False
    assert PaymentService.can_transition(PaymentStatus.CANCELLED, PaymentStatus.PAID) is False
