"""Tests for Subphase 15.10 Explainable Allocation Recommendations and Subphase 15.12 Driver GPS Telemetry Ingestion."""

import pytest
from datetime import datetime, timezone, timedelta
from app.models.enums import (
    CoordinateSource,
    CoordinateVerificationStatus,
    ParcelStatus,
    PaymentStatus,
    RouteObjective,
    RouteStatus,
    ServiceType,
    UserRole,
    VehicleStatus,
    VehicleType,
)
from app.models.organization import Organization
from app.models.branch import Branch
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.parcel import Parcel
from app.models.route import DeliveryRoute, RouteStop
from app.core.security import create_access_token, get_password_hash


def auth_headers(user: User) -> dict:
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def alloc_env(db_session):
    org = db_session.query(Organization).filter(Organization.code == "ALLOC_ORG").first()
    if not org:
        org = Organization(name="Alloc Org", code="ALLOC_ORG", contact_email="alloc@test.com", is_active=True)
        db_session.add(org)
        db_session.flush()

    branch = db_session.query(Branch).filter(Branch.branch_code == "AHC01").first()
    if not branch:
        branch = Branch(
            organization_id=org.id,
            branch_name="Alloc Hub Chennai",
            branch_code="AHC01",
            pincode="600002",
            city="Chennai",
            state="Tamil Nadu",
            address="20 Anna Salai",
            contact_email="ahc@test.com",
            contact_phone="9876501111",
            latitude=13.0600,
            longitude=80.2500,
            is_active=True,
        )
        db_session.add(branch)
        db_session.flush()

    other_branch = db_session.query(Branch).filter(Branch.branch_code == "OHM01").first()
    if not other_branch:
        other_branch = Branch(
            organization_id=org.id,
            branch_name="Other Hub Madurai",
            branch_code="OHM01",
            pincode="625001",
            city="Madurai",
            state="Tamil Nadu",
            address="5 West Masi St",
            contact_email="ohm@test.com",
            contact_phone="9876502222",
            latitude=9.9252,
            longitude=78.1198,
            is_active=True,
        )
        db_session.add(other_branch)
        db_session.flush()

    manager = db_session.query(User).filter(User.email == "alloc_manager@test.com").first()
    if not manager:
        manager = User(
            email="alloc_manager@test.com",
            hashed_password=get_password_hash("password123"),
            full_name="Alloc Manager",
            role=UserRole.BRANCH_MANAGER,
            organization_id=org.id,
            branch_id=branch.id,
            is_active=True,
        )
        db_session.add(manager)
        db_session.flush()

    driver_ready = db_session.query(User).filter(User.email == "alloc_driver_ready@test.com").first()
    if not driver_ready:
        driver_ready = User(
            email="alloc_driver_ready@test.com",
            hashed_password=get_password_hash("password123"),
            full_name="Driver Ready",
            role=UserRole.DELIVERY_AGENT,
            organization_id=org.id,
            branch_id=branch.id,
            is_active=True,
        )
        db_session.add(driver_ready)
        db_session.flush()

    driver_other_branch = db_session.query(User).filter(User.email == "alloc_driver_other@test.com").first()
    if not driver_other_branch:
        driver_other_branch = User(
            email="alloc_driver_other@test.com",
            hashed_password=get_password_hash("password123"),
            full_name="Driver Other Branch",
            role=UserRole.DELIVERY_AGENT,
            organization_id=org.id,
            branch_id=other_branch.id,
            is_active=True,
        )
        db_session.add(driver_other_branch)
        db_session.flush()

    veh_good = db_session.query(Vehicle).filter(Vehicle.vehicle_number == "TN02AL0001").first()
    if not veh_good:
        veh_good = Vehicle(
            organization_id=org.id,
            branch_id=branch.id,
            vehicle_number="TN02AL0001",
            vehicle_type=VehicleType.VAN,
            status=VehicleStatus.AVAILABLE,
            max_weight_kg=500.0,
            max_volume_cbm=3.5,
            is_active=True,
        )
        db_session.add(veh_good)
        db_session.flush()

    veh_maintenance = db_session.query(Vehicle).filter(Vehicle.vehicle_number == "TN02AL9999").first()
    if not veh_maintenance:
        veh_maintenance = Vehicle(
            organization_id=org.id,
            branch_id=branch.id,
            vehicle_number="TN02AL9999",
            vehicle_type=VehicleType.VAN,
            status=VehicleStatus.MAINTENANCE,
            max_weight_kg=500.0,
            max_volume_cbm=3.5,
            is_active=True,
        )
        db_session.add(veh_maintenance)
        db_session.flush()

    p1 = db_session.query(Parcel).filter(Parcel.tracking_number == "ALLOCTRK01").first()
    if not p1:
        p1 = Parcel(
            tracking_number="ALLOCTRK01",
            customer_id=manager.id,
            origin_branch_id=branch.id,
            dest_branch_id=branch.id,
            sender_name="Sender 1",
            sender_phone="9876543210",
            sender_address="Addr 1",
            sender_city=branch.city,
            sender_state=branch.state,
            sender_pincode=branch.pincode,
            receiver_name="Receiver 1",
            receiver_phone="9876543211",
            receiver_address="Dest 1",
            receiver_city=branch.city,
            receiver_state=branch.state,
            receiver_pincode=branch.pincode,
            dest_latitude=13.0650,
            dest_longitude=80.2550,
            dest_coordinate_source=CoordinateSource.VERIFIED_GPS,
            dest_confidence=0.95,
            dest_verification_status=CoordinateVerificationStatus.VERIFIED,
            length_cm=20.0,
            width_cm=15.0,
            height_cm=10.0,
            volumetric_weight_kg=0.6,
            base_charge=120.0,
            total_charge=141.6,
            payment_status=PaymentStatus.PAID,
            weight_kg=10.0,
            service_type=ServiceType.STANDARD,
            delivery_status=ParcelStatus.AT_DESTINATION_BRANCH,
            current_location=branch.branch_name,
        )
        db_session.add(p1)
        db_session.flush()

    return {
        "org": org,
        "branch": branch,
        "other_branch": other_branch,
        "manager": manager,
        "driver_ready": driver_ready,
        "driver_other": driver_other_branch,
        "veh_good": veh_good,
        "veh_maint": veh_maintenance,
        "parcel": p1,
    }


def test_allocation_recommendations_endpoint(client, db_session, alloc_env):
    """Test GET /api/v1/routes/{id}/allocation-recommendations returns ranked recommendations with suitability and blocking reasons."""
    branch = alloc_env["branch"]
    manager = alloc_env["manager"]
    driver_ready = alloc_env["driver_ready"]
    veh_good = alloc_env["veh_good"]
    p1 = alloc_env["parcel"]

    headers = auth_headers(manager)

    create_resp = client.post(
        "/api/v1/routes",
        headers=headers,
        json={
            "branch_id": branch.id,
            "driver_id": driver_ready.id,
            "vehicle_id": veh_good.id,
            "objective": "FASTEST",
            "parcel_ids": [p1.id],
            "return_to_hub": True,
        },
    )
    assert create_resp.status_code == 201
    route_id = create_resp.json()["id"]

    rec_resp = client.get(
        f"/api/v1/routes/{route_id}/allocation-recommendations",
        headers=headers,
    )
    assert rec_resp.status_code == 200
    data = rec_resp.json()
    assert "recommended_drivers" in data
    assert "recommended_vehicles" in data

    # Check drivers ranking
    drivers = data["recommended_drivers"]
    assert len(drivers) >= 1
    ready_entry = next((d for d in drivers if d["driver_id"] == driver_ready.id), None)
    assert ready_entry is not None
    assert ready_entry["is_eligible"] is True
    assert len(ready_entry["suitability_reasons"]) > 0

    other_entry = next((d for d in drivers if d["driver_id"] == alloc_env["driver_other"].id), None)
    if other_entry:
        assert other_entry["is_eligible"] is False
        assert any("branch" in r.lower() for r in other_entry["blocking_reasons"])

    # Check vehicles ranking
    vehicles = data["recommended_vehicles"]
    good_entry = next((v for v in vehicles if v["vehicle_id"] == veh_good.id), None)
    assert good_entry is not None
    assert good_entry["is_eligible"] is True
    assert good_entry["max_weight_kg"] >= 490.0

    maint_entry = next((v for v in vehicles if v["vehicle_id"] == alloc_env["veh_maint"].id), None)
    if maint_entry:
        assert maint_entry["is_eligible"] is False
        assert any("maintenance" in r.lower() for r in maint_entry["blocking_reasons"])


def test_driver_gps_telemetry_ingestion(client, db_session, alloc_env):
    """Test POST /api/v1/routes/{id}/telemetry updates driver location and calculates remaining distance and ETA."""
    branch = alloc_env["branch"]
    manager = alloc_env["manager"]
    driver = alloc_env["driver_ready"]
    veh = alloc_env["veh_good"]

    # Create a fresh parcel for telemetry test
    p2 = Parcel(
        tracking_number=f"TELTRK_{datetime.now(timezone.utc).timestamp()}",
        customer_id=manager.id,
        origin_branch_id=branch.id,
        dest_branch_id=branch.id,
        sender_name="Sender Tel",
        sender_phone="9876543210",
        sender_address="Addr Tel",
        sender_city=branch.city,
        sender_state=branch.state,
        sender_pincode=branch.pincode,
        receiver_name="Receiver Tel",
        receiver_phone="9876543211",
        receiver_address="Dest Tel",
        receiver_city=branch.city,
        receiver_state=branch.state,
        receiver_pincode=branch.pincode,
        dest_latitude=13.0650,
        dest_longitude=80.2550,
        dest_coordinate_source=CoordinateSource.VERIFIED_GPS,
        dest_confidence=0.95,
        dest_verification_status=CoordinateVerificationStatus.VERIFIED,
        length_cm=20.0,
        width_cm=15.0,
        height_cm=10.0,
        volumetric_weight_kg=0.6,
        base_charge=120.0,
        total_charge=141.6,
        payment_status=PaymentStatus.PAID,
        weight_kg=5.0,
        service_type=ServiceType.STANDARD,
        delivery_status=ParcelStatus.AT_DESTINATION_BRANCH,
        current_location=branch.branch_name,
    )
    db_session.add(p2)
    db_session.flush()

    headers_mgr = auth_headers(manager)
    headers_driver = auth_headers(driver)

    create_resp = client.post(
        "/api/v1/routes",
        headers=headers_mgr,
        json={
            "branch_id": branch.id,
            "driver_id": driver.id,
            "vehicle_id": veh.id,
            "objective": "FASTEST",
            "parcel_ids": [p2.id],
            "return_to_hub": True,
        },
    )
    assert create_resp.status_code == 201
    route_id = create_resp.json()["id"]

    # Dispatch route first
    disp_resp = client.post(f"/api/v1/routes/{route_id}/dispatch", headers=headers_mgr, json={})
    assert disp_resp.status_code == 200

    # Start route
    start_resp = client.post(f"/api/v1/routes/{route_id}/start", headers=headers_driver)
    assert start_resp.status_code == 200

    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Ingest valid telemetry
    tel_resp = client.post(
        f"/api/v1/routes/{route_id}/telemetry",
        headers=headers_driver,
        json={
            "latitude": 13.0620,
            "longitude": 80.2520,
            "speed_kmh": 32.5,
            "timestamp": now_iso,
        },
    )
    assert tel_resp.status_code == 200
    tel_data = tel_resp.json()
    assert tel_data["current_latitude"] == 13.0620
    assert tel_data["current_longitude"] == 80.2520
    assert tel_data["eta_source"] in ("DYNAMIC_TELEMETRY", "GPS_ADJUSTED")

    # 2. Ingest stale telemetry (timestamp older than previous) -> Rejected with 422
    stale_iso = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    stale_resp = client.post(
        f"/api/v1/routes/{route_id}/telemetry",
        headers=headers_driver,
        json={
            "latitude": 13.0610,
            "longitude": 80.2510,
            "speed_kmh": 20.0,
            "timestamp": stale_iso,
        },
    )
    assert stale_resp.status_code == 422
    assert "stale" in stale_resp.json()["detail"].lower()


def test_providers_health_endpoint(client, alloc_env):
    """Test GET /api/v1/routes/providers/health returns circuit breaker states and available adapters."""
    manager = alloc_env["manager"]
    headers = auth_headers(manager)

    resp = client.get("/api/v1/routes/providers/health", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "local" in data["registered_providers"]
    assert "circuit_breakers" in data
    assert "openrouteservice" in data["circuit_breakers"]
    assert "osrm" in data["circuit_breakers"]
