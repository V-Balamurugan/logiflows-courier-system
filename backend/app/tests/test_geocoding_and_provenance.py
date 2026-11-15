"""Tests for Subphase 15.11 Coordinate Provenance, Address Geocoding, and Dispatch Guards."""

import pytest
from app.models.enums import (
    CoordinateSource,
    CoordinateVerificationStatus,
    ParcelStatus,
    RouteObjective,
    RouteStatus,
    PaymentStatus,
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
from app.services.geocoding_service import (
    normalize_address,
    GeocodingService,
    MockGeocodingProvider,
    GeocodingResult,
)
from app.services.routing.base import BaseRoutingProvider, Waypoint
from app.services.routing.engine import RoutingEngine
from app.schemas.route_plan import RoutePlanResult, RouteLegResult, DistanceBasis, OptimizationStatus, RouteProvenance


def auth_headers(user: User) -> dict:
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


class StubTestProvider(BaseRoutingProvider):
    name = "stub_test_provider"

    def compute_route(
        self,
        start,
        waypoints,
        vehicle_type=VehicleType.VAN,
        objective="FASTEST",
        return_to_hub=True,
    ):
        return RoutePlanResult(
            provider_used="stub_test_provider",
            fallback_used=False,
            ordered_stops=[w.index for w in waypoints],
            legs=[],
            total_distance_m=1000.0,
            total_duration_s=120.0,
            geometry=None,
            per_stop_eta=[],
            objective=objective,
            optimization_status=OptimizationStatus.OPTIMAL,
            warnings=["stub_warning"],
            provenance=RouteProvenance(
                data_source="stub",
                algorithm="stub_algo_1.0",
                distance_basis=DistanceBasis.STRAIGHT_LINE,
            ),
        )


@pytest.fixture
def geo_env(db_session):
    org = db_session.query(Organization).filter(Organization.code == "GEO_ORG").first()
    if not org:
        org = Organization(name="Geo Test Org", code="GEO_ORG", contact_email="geo@test.com", is_active=True)
        db_session.add(org)
        db_session.flush()

    branch = db_session.query(Branch).filter(Branch.branch_code == "GMH01").first()
    if not branch:
        branch = Branch(
            organization_id=org.id,
            branch_name="Geo Main Hub",
            branch_code="GMH01",
            pincode="600001",
            city="Chennai",
            state="Tamil Nadu",
            address="10 Marina Road, George Town",
            contact_email="gmh@test.com",
            contact_phone="9876501111",
            latitude=13.0827,
            longitude=80.2707,
            is_active=True,
        )
        db_session.add(branch)
        db_session.flush()

    manager = db_session.query(User).filter(User.email == "geo_manager@test.com").first()
    if not manager:
        manager = User(
            email="geo_manager@test.com",
            hashed_password=get_password_hash("password123"),
            full_name="Geo Manager",
            role=UserRole.BRANCH_MANAGER,
            organization_id=org.id,
            branch_id=branch.id,
            is_active=True,
        )
        db_session.add(manager)
        db_session.flush()

    driver = db_session.query(User).filter(User.email == "geo_driver@test.com").first()
    if not driver:
        driver = User(
            email="geo_driver@test.com",
            hashed_password=get_password_hash("password123"),
            full_name="Geo Driver",
            role=UserRole.DELIVERY_AGENT,
            organization_id=org.id,
            branch_id=branch.id,
            is_active=True,
        )
        db_session.add(driver)
        db_session.flush()

    vehicle = db_session.query(Vehicle).filter(Vehicle.vehicle_number == "TN01GEO123").first()
    if not vehicle:
        vehicle = Vehicle(
            organization_id=org.id,
            branch_id=branch.id,
            vehicle_number="TN01GEO123",
            vehicle_type=VehicleType.VAN,
            status=VehicleStatus.AVAILABLE,
            max_weight_kg=600.0,
            max_volume_cbm=4.0,
            is_active=True,
        )
        db_session.add(vehicle)
        db_session.flush()

    return {
        "org": org,
        "branch": branch,
        "manager": manager,
        "driver": driver,
        "vehicle": vehicle,
    }


def test_address_normalization():
    raw_addr = "   123/4,  Anna   Salai,   Near Gemini flyover, chennai - 600006,  Tamil nadu  "
    normalized = normalize_address(raw_addr)
    assert "  " not in normalized
    assert "CHENNAI" in normalized
    assert "TAMIL NADU" in normalized
    assert "600006" in normalized
    assert not normalized.startswith(" ")
    assert not normalized.endswith(" ")


def test_geocoding_service_caching_and_mock():
    GeocodingService.clear_cache()
    addr = "42 Mount Road, Guindy, Chennai - 600032"
    res1 = GeocodingService.geocode(addr)
    assert res1 is not None
    assert isinstance(res1, GeocodingResult)
    assert res1.coordinate_source == CoordinateSource.VERIFIED_GEOCODING
    assert res1.confidence >= 0.85
    assert res1.latitude is not None
    assert res1.longitude is not None

    # Second call should hit in-memory TTL cache
    res2 = GeocodingService.geocode(addr)
    assert res2 == res1


def test_routing_engine_pluggable_stub_provider():
    stub = StubTestProvider()
    RoutingEngine.register_provider("stub_test", stub)

    registered = RoutingEngine.get_provider("stub_test")
    assert registered is stub

    health = RoutingEngine.get_providers_health()
    assert "stub_test" in health["registered_providers"]

    # Clean up unregister
    RoutingEngine.unregister_provider("stub_test")
    assert RoutingEngine.get_provider("stub_test") is None


def test_low_confidence_stops_dispatch_guard(client, db_session, geo_env):
    """Test that a route with low-confidence / vicinity-estimate stops requires a valid manager override to dispatch."""
    branch = geo_env["branch"]
    manager = geo_env["manager"]
    driver = geo_env["driver"]
    vehicle = geo_env["vehicle"]

    # Create parcel without verified GPS (forcing vicinity estimate)
    p = Parcel(
        tracking_number="LCONF001",
        customer_id=manager.id,
        origin_branch_id=branch.id,
        dest_branch_id=branch.id,
        sender_name="Sender",
        sender_phone="9999900001",
        sender_address="Addr 1",
        sender_city=branch.city,
        sender_state=branch.state,
        sender_pincode=branch.pincode,
        receiver_name="Receiver Low Conf",
        receiver_phone="9999900002",
        receiver_address="Remote unmapped area",
        receiver_city=branch.city,
        receiver_state=branch.state,
        receiver_pincode=branch.pincode,
        dest_latitude=None,  # No coordinates -> will trigger BRANCH_VICINITY_ESTIMATE
        dest_longitude=None,
        dest_coordinate_source=CoordinateSource.BRANCH_VICINITY_ESTIMATE,
        dest_confidence=0.30,
        dest_verification_status=CoordinateVerificationStatus.UNVERIFIED,
        length_cm=20.0,
        width_cm=15.0,
        height_cm=10.0,
        volumetric_weight_kg=0.6,
        base_charge=120.0,
        total_charge=141.6,
        payment_status=PaymentStatus.PAID,
        weight_kg=3.0,
        service_type=ServiceType.STANDARD,
        delivery_status=ParcelStatus.AT_DESTINATION_BRANCH,
        current_location=branch.branch_name,
    )
    db_session.add(p)
    db_session.flush()

    headers = auth_headers(manager)

    # 1. Create Route
    create_resp = client.post(
        "/api/v1/routes",
        headers=headers,
        json={
            "branch_id": branch.id,
            "driver_id": driver.id,
            "vehicle_id": vehicle.id,
            "objective": "FASTEST",
            "parcel_ids": [p.id],
            "return_to_hub": True,
        },
    )
    assert create_resp.status_code == 201
    route_data = create_resp.json()
    route_id = route_data["id"]
    assert route_data["has_low_confidence_stops"] is True

    # 2. Attempt dispatch without override -> Must be rejected with 422
    dispatch_fail = client.post(
        f"/api/v1/routes/{route_id}/dispatch",
        headers=headers,
        json={},
    )
    assert dispatch_fail.status_code == 422
    detail = dispatch_fail.json()["detail"]
    assert "override" in detail.lower() or "low-confidence" in detail.lower()

    # 3. Attempt dispatch with short override reason (< 10 chars) -> Rejected with 422
    dispatch_short = client.post(
        f"/api/v1/routes/{route_id}/dispatch",
        headers=headers,
        json={"low_confidence_override_reason": "Too short"},
    )
    assert dispatch_short.status_code == 422

    # 4. Attempt dispatch with valid override reason (>= 10 chars) -> Succeeded
    dispatch_ok = client.post(
        f"/api/v1/routes/{route_id}/dispatch",
        headers=headers,
        json={"low_confidence_override_reason": "Verified address with customer directly via phone"},
    )
    assert dispatch_ok.status_code == 200
    dispatched_data = dispatch_ok.json()
    assert dispatched_data["status"] == "DISPATCHED"
    assert dispatched_data["low_confidence_override_reason"] == "Verified address with customer directly via phone"
    assert dispatched_data["low_confidence_overridden_by_id"] == manager.id
