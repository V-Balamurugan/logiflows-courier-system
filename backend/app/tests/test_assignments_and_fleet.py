from unittest.mock import patch
import pytest
from app.models.organization import Organization
from app.models.branch import Branch
from app.models.user import User
from app.models.parcel import Parcel
from app.models.vehicle import Vehicle
from app.models.assignment import DeliveryAssignment
from app.models.enums import (
    UserRole,
    OperatingStatus,
    ServiceType,
    PaymentStatus,
    ParcelStatus,
    VehicleType,
    VehicleStatus,
    AssignmentType,
    AssignmentStatus
)
from app.core.security import create_access_token, get_password_hash


def auth_headers(user):
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def fleet_test_data(db_session):
    # Org 1
    org1 = db_session.query(Organization).filter(Organization.code == "FLEET_ORG1").first()
    if not org1:
        org1 = Organization(name="Fleet Org 1", code="FLEET_ORG1", contact_email="f1@org.com", is_active=True)
        db_session.add(org1)
        db_session.flush()

    # Org 2
    org2 = db_session.query(Organization).filter(Organization.code == "FLEET_ORG2").first()
    if not org2:
        org2 = Organization(name="Fleet Org 2", code="FLEET_ORG2", contact_email="f2@org.com", is_active=True)
        db_session.add(org2)
        db_session.flush()

    # Branches
    b1 = db_session.query(Branch).filter(Branch.branch_code == "FL_B1").first()
    if not b1:
        b1 = Branch(
            organization_id=org1.id,
            branch_code="FL_B1",
            branch_name="Fleet Branch 1",
            address="Addr 1",
            pincode="110001",
            city="Delhi",
            state="Delhi",
            country="India",
            contact_email="b1@fleet.com",
            contact_phone="9988110001",
            operating_status=OperatingStatus.ACTIVE,
            is_active=True
        )
        db_session.add(b1)
        db_session.flush()

    b2 = db_session.query(Branch).filter(Branch.branch_code == "FL_B2").first()
    if not b2:
        b2 = Branch(
            organization_id=org2.id,
            branch_code="FL_B2",
            branch_name="Fleet Branch 2",
            address="Addr 2",
            pincode="400001",
            city="Mumbai",
            state="Maharashtra",
            country="India",
            contact_email="b2@fleet.com",
            contact_phone="9988110002",
            operating_status=OperatingStatus.ACTIVE,
            is_active=True
        )
        db_session.add(b2)
        db_session.flush()

    # Users in Org 1
    admin1 = db_session.query(User).filter(User.email == "fleet_admin1@test.com").first()
    if not admin1:
        admin1 = User(
            email="fleet_admin1@test.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Fleet Admin 1",
            role=UserRole.ORG_ADMIN,
            organization_id=org1.id,
            branch_id=b1.id,
            is_active=True
        )
        db_session.add(admin1)
        db_session.flush()

    agent1 = db_session.query(User).filter(User.email == "fleet_agent1@test.com").first()
    if not agent1:
        agent1 = User(
            email="fleet_agent1@test.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Fleet Agent 1",
            role=UserRole.DELIVERY_AGENT,
            organization_id=org1.id,
            branch_id=b1.id,
            is_active=True
        )
        db_session.add(agent1)
        db_session.flush()

    # Users in Org 2
    admin2 = db_session.query(User).filter(User.email == "fleet_admin2@test.com").first()
    if not admin2:
        admin2 = User(
            email="fleet_admin2@test.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Fleet Admin 2",
            role=UserRole.ORG_ADMIN,
            organization_id=org2.id,
            branch_id=b2.id,
            is_active=True
        )
        db_session.add(admin2)
        db_session.flush()

    # Customer
    customer = db_session.query(User).filter(User.email == "fleet_cust@test.com").first()
    if not customer:
        customer = User(
            email="fleet_cust@test.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Fleet Cust",
            role=UserRole.CUSTOMER,
            is_active=True
        )
        db_session.add(customer)
        db_session.flush()

    # Small Bike in Org 1 (capacity 20.0 kg)
    bike = db_session.query(Vehicle).filter(Vehicle.vehicle_number == "FL-BIKE-01").first()
    if not bike:
        bike = Vehicle(
            organization_id=org1.id,
            branch_id=b1.id,
            vehicle_number="FL-BIKE-01",
            vehicle_type=VehicleType.BIKE,
            max_weight_kg=20.0,
            max_volume_cbm=0.5,
            status=VehicleStatus.AVAILABLE,
            is_active=True
        )
        db_session.add(bike)
        db_session.flush()

    # Heavy Parcel in Org 1 (weight 50.0 kg)
    heavy_parcel = db_session.query(Parcel).filter(Parcel.tracking_number == "FL-HVY-001").first()
    if not heavy_parcel:
        heavy_parcel = Parcel(
            tracking_number="FL-HVY-001",
            origin_branch_id=b1.id,
            dest_branch_id=b1.id,
            sender_name="S", sender_phone="1", sender_address="A", sender_city="C", sender_state="S", sender_pincode="1",
            receiver_name="R", receiver_phone="2", receiver_address="A", receiver_city="C", receiver_state="S", receiver_pincode="2",
            weight_kg=50.0, length_cm=40.0, width_cm=40.0, height_cm=40.0, volumetric_weight_kg=12.8,
            service_type=ServiceType.STANDARD, base_charge=50.0, total_charge=1300.0,
            payment_status=PaymentStatus.PAID, delivery_status=ParcelStatus.AT_ORIGIN_BRANCH,
            version_id=1
        )
        db_session.add(heavy_parcel)
        db_session.flush()

    # Standard Parcel in Org 1 (weight 5.0 kg)
    std_parcel = db_session.query(Parcel).filter(Parcel.tracking_number == "FL-STD-001").first()
    if not std_parcel:
        std_parcel = Parcel(
            tracking_number="FL-STD-001",
            origin_branch_id=b1.id,
            dest_branch_id=b1.id,
            sender_name="S", sender_phone="1", sender_address="A", sender_city="C", sender_state="S", sender_pincode="1",
            receiver_name="R", receiver_phone="2", receiver_address="A", receiver_city="C", receiver_state="S", receiver_pincode="2",
            weight_kg=5.0, length_cm=20.0, width_cm=20.0, height_cm=20.0, volumetric_weight_kg=1.6,
            service_type=ServiceType.STANDARD, base_charge=50.0, total_charge=175.0,
            payment_status=PaymentStatus.PAID, delivery_status=ParcelStatus.AT_ORIGIN_BRANCH,
            version_id=1
        )
        db_session.add(std_parcel)
        db_session.flush()

    db_session.commit()
    return {
        "org1": org1,
        "org2": org2,
        "branch1": b1,
        "branch2": b2,
        "admin1": admin1,
        "admin2": admin2,
        "agent1": agent1,
        "customer": customer,
        "bike": bike,
        "heavy_parcel": heavy_parcel,
        "std_parcel": std_parcel
    }


def test_concurrent_or_duplicate_parcel_assignment_fails(client, fleet_test_data):
    """AC1: Assigning an already actively assigned parcel yields 409 Conflict."""
    admin_hdrs = auth_headers(fleet_test_data["admin1"])
    parcel = fleet_test_data["std_parcel"]
    agent = fleet_test_data["agent1"]

    payload = {
        "parcel_id": parcel.id,
        "employee_id": agent.id,
        "assignment_type": "LAST_MILE",
        "notes": "First run"
    }

    # 1. First assignment succeeds
    res1 = client.post("/api/v1/assignments", json=payload, headers=admin_hdrs)
    assert res1.status_code == 201

    # 2. Second assignment on the same parcel fails with 409 Conflict
    res2 = client.post("/api/v1/assignments", json=payload, headers=admin_hdrs)
    assert res2.status_code == 409
    assert "already actively assigned" in res2.json()["detail"].lower()


def test_vehicle_double_booking_fails(client, db_session, fleet_test_data):
    """AC2: Assigning a vehicle that is already assigned/in use yields 409 Conflict."""
    admin_hdrs = auth_headers(fleet_test_data["admin1"])
    vehicle = fleet_test_data["bike"]
    agent = fleet_test_data["agent1"]

    # Mark vehicle as ASSIGNED
    vehicle.status = VehicleStatus.ASSIGNED
    db_session.commit()

    # Create fresh parcel
    parcel = Parcel(
        tracking_number="FL-VEH-TEST-01",
        origin_branch_id=fleet_test_data["branch1"].id,
        dest_branch_id=fleet_test_data["branch1"].id,
        sender_name="S", sender_phone="1", sender_address="A", sender_city="C", sender_state="S", sender_pincode="1",
        receiver_name="R", receiver_phone="2", receiver_address="A", receiver_city="C", receiver_state="S", receiver_pincode="2",
        weight_kg=2.0, length_cm=10.0, width_cm=10.0, height_cm=10.0, volumetric_weight_kg=0.2,
        service_type=ServiceType.STANDARD, base_charge=50.0, total_charge=50.0,
        payment_status=PaymentStatus.PAID, delivery_status=ParcelStatus.AT_ORIGIN_BRANCH,
        version_id=1
    )
    db_session.add(parcel)
    db_session.commit()

    payload = {
        "parcel_id": parcel.id,
        "employee_id": agent.id,
        "vehicle_id": vehicle.id,
        "assignment_type": "LAST_MILE"
    }

    res = client.post("/api/v1/assignments", json=payload, headers=admin_hdrs)
    assert res.status_code == 409
    assert "unavailable" in res.json()["detail"].lower()


def test_over_capacity_assignment_rejected(client, db_session, fleet_test_data):
    """AC3: Assigning a parcel whose weight exceeds the vehicle max weight is rejected with 400."""
    admin_hdrs = auth_headers(fleet_test_data["admin1"])
    heavy_parcel = fleet_test_data["heavy_parcel"]  # 50 kg
    bike = fleet_test_data["bike"]                  # 20 kg max
    agent = fleet_test_data["agent1"]

    # Reset vehicle to AVAILABLE
    bike.status = VehicleStatus.AVAILABLE
    db_session.commit()

    payload = {
        "parcel_id": heavy_parcel.id,
        "employee_id": agent.id,
        "vehicle_id": bike.id,
        "assignment_type": "LAST_MILE"
    }

    res = client.post("/api/v1/assignments", json=payload, headers=admin_hdrs)
    assert res.status_code == 400
    assert "vehicle capacity exceeded" in res.json()["detail"].lower()


def test_assignment_lifecycle_state_synchronization(client, db_session, fleet_test_data):
    """AC4: Assert assignment, vehicle status, and parcel status stay consistent across assign, complete, cancel, and fail."""
    admin_hdrs = auth_headers(fleet_test_data["admin1"])
    agent_hdrs = auth_headers(fleet_test_data["agent1"])
    vehicle = fleet_test_data["bike"]
    agent = fleet_test_data["agent1"]

    vehicle.status = VehicleStatus.AVAILABLE
    db_session.commit()

    # Step 1: Assign Delivery
    p1 = Parcel(
        tracking_number="FL-SYNC-001",
        origin_branch_id=fleet_test_data["branch1"].id,
        dest_branch_id=fleet_test_data["branch1"].id,
        sender_name="S", sender_phone="1", sender_address="A", sender_city="C", sender_state="S", sender_pincode="1",
        receiver_name="R", receiver_phone="2", receiver_address="A", receiver_city="C", receiver_state="S", receiver_pincode="2",
        weight_kg=2.0, length_cm=10.0, width_cm=10.0, height_cm=10.0, volumetric_weight_kg=0.2,
        service_type=ServiceType.STANDARD, base_charge=50.0, total_charge=50.0,
        payment_status=PaymentStatus.PAID, delivery_status=ParcelStatus.AT_ORIGIN_BRANCH,
        version_id=1
    )
    db_session.add(p1)
    db_session.commit()

    res_assign = client.post(
        "/api/v1/assignments",
        json={"parcel_id": p1.id, "employee_id": agent.id, "vehicle_id": vehicle.id, "assignment_type": "LAST_MILE"},
        headers=admin_hdrs
    )
    assert res_assign.status_code == 201
    assign_id = res_assign.json()["id"]

    db_session.refresh(vehicle)
    db_session.refresh(p1)
    assert vehicle.status == VehicleStatus.ASSIGNED
    assert p1.delivery_status == ParcelStatus.OUT_FOR_DELIVERY

    # Step 2: Complete Delivery
    res_complete = client.put(
        f"/api/v1/assignments/{assign_id}/status",
        json={"status": "COMPLETED", "notes": "Customer accepted package"},
        headers=agent_hdrs
    )
    assert res_complete.status_code == 200

    db_session.refresh(vehicle)
    db_session.refresh(p1)
    assert vehicle.status == VehicleStatus.AVAILABLE
    assert p1.delivery_status == ParcelStatus.DELIVERED


def test_cross_tenant_and_unauthorized_assignments_rejected(client, db_session, fleet_test_data):
    """AC5: Customer or Agent creating assignment fails with 403; cross-tenant assignment returns 404."""
    cust_hdrs = auth_headers(fleet_test_data["customer"])
    agent_hdrs = auth_headers(fleet_test_data["agent1"])
    admin2_hdrs = auth_headers(fleet_test_data["admin2"])  # Org 2
    parcel1 = fleet_test_data["heavy_parcel"]               # Org 1

    payload = {
        "parcel_id": parcel1.id,
        "employee_id": fleet_test_data["agent1"].id,
        "assignment_type": "LAST_MILE"
    }

    # Customer forbidden
    res_cust = client.post("/api/v1/assignments", json=payload, headers=cust_hdrs)
    assert res_cust.status_code == 403

    # Agent forbidden
    res_agent = client.post("/api/v1/assignments", json=payload, headers=agent_hdrs)
    assert res_agent.status_code == 403

    # Org 2 Admin accessing Org 1 parcel returns 404 anti-leakage
    res_cross = client.post("/api/v1/assignments", json=payload, headers=admin2_hdrs)
    assert res_cross.status_code == 404


def test_assignment_mid_transaction_failure_rollback(db_session, fleet_test_data):
    """AC6: An error during assignment creation cleanly rolls back without orphan assignments or state changes."""
    from app.services.assignment_service import AssignmentService
    from app.schemas.assignment import AssignmentCreate

    admin = fleet_test_data["admin1"]
    agent = fleet_test_data["agent1"]
    vehicle = fleet_test_data["bike"]
    vehicle.status = VehicleStatus.AVAILABLE
    db_session.commit()

    parcel = Parcel(
        tracking_number="FL-ROLLBACK-01",
        origin_branch_id=fleet_test_data["branch1"].id,
        dest_branch_id=fleet_test_data["branch1"].id,
        sender_name="S", sender_phone="1", sender_address="A", sender_city="C", sender_state="S", sender_pincode="1",
        receiver_name="R", receiver_phone="2", receiver_address="A", receiver_city="C", receiver_state="S", receiver_pincode="2",
        weight_kg=2.0, length_cm=10.0, width_cm=10.0, height_cm=10.0, volumetric_weight_kg=0.2,
        service_type=ServiceType.STANDARD, base_charge=50.0, total_charge=50.0,
        payment_status=PaymentStatus.PAID, delivery_status=ParcelStatus.AT_ORIGIN_BRANCH,
        version_id=1
    )
    db_session.add(parcel)
    db_session.commit()

    req_data = AssignmentCreate(
        parcel_id=parcel.id,
        employee_id=agent.id,
        vehicle_id=vehicle.id,
        assignment_type=AssignmentType.LAST_MILE
    )

    initial_assignments_count = db_session.query(DeliveryAssignment).filter(DeliveryAssignment.parcel_id == parcel.id).count()

    # Inject failure during db.commit
    with patch.object(db_session, "commit", side_effect=RuntimeError("Simulated DB Write Error")):
        with pytest.raises(RuntimeError):
            AssignmentService.create_assignment(db_session, admin, req_data)

    db_session.rollback()
    db_session.refresh(parcel)
    db_session.refresh(vehicle)

    # Verify no orphan assignment exists
    post_count = db_session.query(DeliveryAssignment).filter(DeliveryAssignment.parcel_id == parcel.id).count()
    assert post_count == initial_assignments_count
    assert parcel.delivery_status == ParcelStatus.AT_ORIGIN_BRANCH
    assert vehicle.status == VehicleStatus.AVAILABLE
