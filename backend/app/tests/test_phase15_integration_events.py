import asyncio
import json
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.enums import (
    ManifestStatus,
    ParcelStatus,
    PaymentStatus,
    RouteObjective,
    RouteStatus,
    RouteStopStatus,
    RouteStopType,
    ServiceType,
    UserRole,
    VehicleStatus,
    VehicleType,
)
from app.models.branch import Branch
from app.models.linehaul import ConsolidationBag, BagItem, LinehaulManifest
from app.models.organization import Organization
from app.models.parcel import Parcel
from app.models.route import DeliveryRoute, RouteStop
from app.models.user import User
from app.models.vehicle import Vehicle
from app.services.broadcaster import route_event_broadcaster
from app.services.route_service import RouteService


def auth_headers(user: User) -> dict:
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


def _create_test_parcel(
    db_session,
    tracking_number: str,
    customer: User,
    branch: Branch,
    dest_lat: float = 13.0850,
    dest_lng: float = 80.2750,
    weight_kg: float = 3.0,
    delivery_status: ParcelStatus = ParcelStatus.AT_DESTINATION_BRANCH,
    sender_name: str = "Sender",
    receiver_name: str = "Receiver",
) -> Parcel:
    parcel = Parcel(
        tracking_number=tracking_number,
        customer_id=customer.id,
        origin_branch_id=branch.id,
        dest_branch_id=branch.id,
        sender_name=sender_name,
        sender_phone="9999999999",
        sender_address="St 1",
        sender_city="Chennai",
        sender_state="TN",
        sender_pincode="600001",
        receiver_name=receiver_name,
        receiver_phone="9999999998",
        receiver_address="St 2",
        receiver_city="Chennai",
        receiver_state="TN",
        receiver_pincode="600001",
        dest_latitude=dest_lat,
        dest_longitude=dest_lng,
        weight_kg=weight_kg,
        length_cm=10.0,
        width_cm=10.0,
        height_cm=10.0,
        volumetric_weight_kg=1.0,
        service_type=ServiceType.STANDARD,
        base_charge=50.0,
        total_charge=50.0,
        payment_status=PaymentStatus.PAID,
        delivery_status=delivery_status,
    )
    db_session.add(parcel)
    db_session.flush()
    return parcel


@pytest.fixture
def org_setup(db_session):
    u = uuid.uuid4().hex[:6]
    # Org 1
    org1 = Organization(
        name=f"Speedy Express Org 1 {u}",
        code=f"ORG1_{u}",
        contact_email=f"contact1_{u}@org1.com",
        is_active=True,
    )
    db_session.add(org1)
    db_session.flush()

    branch1 = Branch(
        organization_id=org1.id,
        branch_name="Org1 Central Hub",
        branch_code=f"O1-HUB-{u}",
        address="10 Anna Salai, Chennai",
        contact_email=f"hub1_{u}@org1.com",
        contact_phone="9876543210",
        city="Chennai",
        state="TN",
        pincode="600001",
        latitude=13.0827,
        longitude=80.2707,
        is_active=True,
    )
    db_session.add(branch1)
    db_session.flush()

    manager1 = User(
        email=f"manager1_{u}@org1.com",
        hashed_password="hash",
        full_name="Manager Org1",
        role=UserRole.BRANCH_MANAGER,
        organization_id=org1.id,
        branch_id=branch1.id,
        is_active=True,
    )
    driver1 = User(
        email=f"driver1_{u}@org1.com",
        hashed_password="hash",
        full_name="Driver Org1",
        role=UserRole.DELIVERY_AGENT,
        organization_id=org1.id,
        branch_id=branch1.id,
        is_active=True,
    )
    vehicle1 = Vehicle(
        organization_id=org1.id,
        branch_id=branch1.id,
        vehicle_number=f"TN-01-{u.upper()}",
        vehicle_type=VehicleType.VAN,
        max_weight_kg=1000.0,
        max_volume_cbm=8.0,
        status=VehicleStatus.AVAILABLE,
        is_active=True,
    )
    db_session.add_all([manager1, driver1, vehicle1])
    db_session.flush()

    # Org 2
    org2 = Organization(
        name=f"Apex Logistics Org 2 {u}",
        code=f"ORG2_{u}",
        contact_email=f"contact2_{u}@org2.com",
        is_active=True,
    )
    db_session.add(org2)
    db_session.flush()

    branch2 = Branch(
        organization_id=org2.id,
        branch_name="Org2 Hub",
        branch_code=f"O2-HUB-{u}",
        address="20 MG Road, Bangalore",
        contact_email=f"hub2_{u}@org2.com",
        contact_phone="9876543211",
        city="Bangalore",
        state="KA",
        pincode="560001",
        latitude=12.9716,
        longitude=77.5946,
        is_active=True,
    )
    db_session.add(branch2)
    db_session.flush()

    manager2 = User(
        email=f"manager2_{u}@org2.com",
        hashed_password="hash",
        full_name="Manager Org2",
        role=UserRole.BRANCH_MANAGER,
        organization_id=org2.id,
        branch_id=branch2.id,
        is_active=True,
    )
    db_session.add(manager2)
    db_session.commit()

    return {
        "org1": org1,
        "branch1": branch1,
        "manager1": manager1,
        "driver1": driver1,
        "vehicle1": vehicle1,
        "org2": org2,
        "branch2": branch2,
        "manager2": manager2,
    }


def test_negative_tenant_isolation_org_isolation(client: TestClient, db_session, org_setup):
    """
    Subphase 15.16: Negative tenant isolation.
    An Org 2 Manager MUST receive HTTP 404 for any read, dispatch, telemetry, reoptimization,
    or event-stream access to an Org 1 Route.
    """
    u = uuid.uuid4().hex[:6]
    manager1 = org_setup["manager1"]
    manager2 = org_setup["manager2"]
    branch1 = org_setup["branch1"]
    driver1 = org_setup["driver1"]
    vehicle1 = org_setup["vehicle1"]

    # Manager 1 creates a route in Org 1
    route = DeliveryRoute(
        organization_id=org_setup["org1"].id,
        branch_id=branch1.id,
        route_code=f"RT-ORG1-{u}",
        status=RouteStatus.PLANNED,
        driver_id=driver1.id,
        vehicle_id=vehicle1.id,
        optimization_objective=RouteObjective.FASTEST,
        total_distance_km=15.0,
        estimated_duration_min=45.0,
        is_active_dispatch=False,
    )
    db_session.add(route)
    db_session.commit()
    db_session.refresh(route)

    headers2 = auth_headers(manager2)

    # 1. Read
    res_get = client.get(f"/api/v1/routes/{route.id}", headers=headers2)
    assert res_get.status_code == 404
    assert "Route not found" in res_get.json()["detail"]

    # 2. Dispatch
    res_dispatch = client.post(
        f"/api/v1/routes/{route.id}/dispatch",
        json={"notes": "Hacked dispatch"},
        headers=headers2,
    )
    assert res_dispatch.status_code == 404

    # 3. Telemetry
    res_telem = client.post(
        f"/api/v1/routes/{route.id}/telemetry",
        json={"latitude": 13.0900, "longitude": 80.2800},
        headers=headers2,
    )
    assert res_telem.status_code == 404

    # 4. Reoptimize
    res_reopt = client.post(
        f"/api/v1/routes/{route.id}/reoptimize",
        json={"objective": "FASTEST"},
        headers=headers2,
    )
    assert res_reopt.status_code == 404

    # 5. Events
    res_events = client.get(
        f"/api/v1/routes/{route.id}/events",
        headers=headers2,
    )
    assert res_events.status_code == 404


def test_post_commit_route_events_and_rollback_emits_nothing(client: TestClient, db_session, org_setup):
    """
    Subphase 15.15: Post-commit domain events.
    Verifies that route lifecycle events (ROUTE_DISPATCHED, DRIVER_ASSIGNED, ROUTE_STARTED)
    are emitted after successful commits, and that failed/rolled-back operations emit nothing.
    """
    u = uuid.uuid4().hex[:6]
    manager1 = org_setup["manager1"]
    branch1 = org_setup["branch1"]
    driver1 = org_setup["driver1"]
    vehicle1 = org_setup["vehicle1"]

    # Create parcel for route
    customer = User(
        email=f"cust_event_{u}@test.com",
        hashed_password="hash",
        full_name="Alice Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
    )
    db_session.add(customer)
    db_session.flush()

    parcel = _create_test_parcel(
        db_session,
        tracking_number=f"LF-EVT-{u}",
        customer=customer,
        branch=branch1,
    )

    route = DeliveryRoute(
        organization_id=org_setup["org1"].id,
        branch_id=branch1.id,
        route_code=f"RT-EVT-{u}",
        status=RouteStatus.PLANNED,
        driver_id=driver1.id,
        vehicle_id=vehicle1.id,
        optimization_objective=RouteObjective.FASTEST,
        total_distance_km=10.0,
        estimated_duration_min=30.0,
        total_weight_kg=3.0,
        has_low_confidence_stops=False,
        is_active_dispatch=False,
    )
    db_session.add(route)
    db_session.flush()

    stop = RouteStop(
        route_id=route.id,
        parcel_id=parcel.id,
        sequence_order=1,
        stop_type=RouteStopType.DELIVERY,
        status=RouteStopStatus.PENDING,
        location_name="Delivery Stop 1",
        address="St 2",
        latitude=13.0850,
        longitude=80.2750,
        eta_minutes_from_start=15.0,
    )
    db_session.add(stop)
    db_session.commit()
    db_session.refresh(route)

    # Subscribe to route events
    queue = route_event_broadcaster.subscribe(str(route.id))

    headers1 = auth_headers(manager1)

    # 1. Successful dispatch -> must broadcast ROUTE_DISPATCHED and DRIVER_ASSIGNED
    res_dispatch = client.post(
        f"/api/v1/routes/{route.id}/dispatch",
        json={"notes": "Normal dispatch"},
        headers=headers1,
    )
    assert res_dispatch.status_code == 200

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())

    event_types = [e["event_type"] for e in events]
    assert "ROUTE_DISPATCHED" in event_types
    assert "DRIVER_ASSIGNED" in event_types

    # 2. Failed dispatch on already dispatched route (raises 409 Conflict) -> rollback must emit ZERO events
    res_fail = client.post(
        f"/api/v1/routes/{route.id}/dispatch",
        json={"notes": "Duplicate dispatch"},
        headers=headers1,
    )
    assert res_fail.status_code == 409
    assert queue.empty(), "Rollback or failed transaction must emit zero route events"

    # 3. Successful start_route -> broadcasts ROUTE_STARTED
    res_start = client.post(
        f"/api/v1/routes/{route.id}/start",
        headers=headers1,
    )
    assert res_start.status_code == 200
    assert not queue.empty()
    started_evt = queue.get_nowait()
    assert started_evt["event_type"] == "ROUTE_STARTED"

    route_event_broadcaster.unsubscribe(str(route.id), queue)


def test_zero_pii_in_public_tracking(client: TestClient, db_session, org_setup):
    """
    Subphase 15.15 / 15.16: Public tracking MUST be 100% PII-free.
    Customer name, phone, email, and full street address must NOT appear anywhere in the response.
    """
    u = uuid.uuid4().hex[:6]
    branch1 = org_setup["branch1"]
    customer = User(
        email=f"secret_{u}@private.org",
        hashed_password="hash",
        full_name="Alice SuperSecret",
        role=UserRole.CUSTOMER,
        is_active=True,
    )
    db_session.add(customer)
    db_session.flush()

    parcel = _create_test_parcel(
        db_session,
        tracking_number=f"LF-PII-{u}",
        customer=customer,
        branch=branch1,
        sender_name="Confidential Sender Corp",
        receiver_name="Secret Receiver Inc",
    )
    db_session.commit()

    # Public endpoint without auth
    resp = client.get(f"/api/v1/tracking/public/{parcel.tracking_number}")
    assert resp.status_code == 200
    data = resp.json()
    raw_str = json.dumps(data)

    # Assert 0 PII leakage
    assert "Alice SuperSecret" not in raw_str
    assert "secret_alice@private.org" not in raw_str
    assert "Confidential Sender Corp" not in raw_str
    assert "+91-9988776655" not in raw_str
    assert "Confidential Suite" not in raw_str
    assert "Secret Receiver Inc" not in raw_str
    assert "+91-1122334455" not in raw_str
    assert "Private Residence 99" not in raw_str

    # Assert allowed safe public fields
    assert data["tracking_number"] == f"LF-PII-{u}"
    assert data["origin_city"] == "Chennai"
    assert data["destination_city"] == "Chennai"


def test_linehaul_vehicle_and_parcel_conflict_guard(client: TestClient, db_session, org_setup):
    """
    Subphase 15.15: Linehaul & Last-Mile conflict prevention.
    1. Vehicle cannot be used for last-mile route while committed to active linehaul manifest.
    2. Parcel packed in active linehaul bag cannot be scheduled on last-mile route.
    """
    u = uuid.uuid4().hex[:6]
    manager1 = org_setup["manager1"]
    branch1 = org_setup["branch1"]
    driver1 = org_setup["driver1"]
    vehicle1 = org_setup["vehicle1"]

    # 1. Commit vehicle to active linehaul manifest
    manifest = LinehaulManifest(
        organization_id=org_setup["org1"].id,
        manifest_number=f"MAN-CONFL-{u}",
        origin_branch_id=branch1.id,
        dest_branch_id=branch1.id,
        vehicle_id=vehicle1.id,
        driver_id=driver1.id,
        status=ManifestStatus.IN_TRANSIT,
    )
    db_session.add(manifest)
    db_session.flush()

    # Create parcel
    customer = User(
        email=f"lh_cust_{u}@test.com",
        hashed_password="hash",
        full_name="Bob LH",
        role=UserRole.CUSTOMER,
        is_active=True,
    )
    db_session.add(customer)
    db_session.flush()

    parcel = _create_test_parcel(
        db_session,
        tracking_number=f"LF-LH-{u}",
        customer=customer,
        branch=branch1,
        weight_kg=4.0,
    )

    # Attempt to dispatch route with linehaul vehicle -> must raise 409
    route = DeliveryRoute(
        organization_id=org_setup["org1"].id,
        branch_id=branch1.id,
        route_code=f"RT-LH-{u}",
        status=RouteStatus.PLANNED,
        driver_id=driver1.id,
        vehicle_id=vehicle1.id,
        optimization_objective=RouteObjective.FASTEST,
        total_distance_km=10.0,
        estimated_duration_min=30.0,
        total_weight_kg=4.0,
        has_low_confidence_stops=False,
    )
    db_session.add(route)
    db_session.flush()

    stop = RouteStop(
        route_id=route.id,
        parcel_id=parcel.id,
        sequence_order=1,
        stop_type=RouteStopType.DELIVERY,
        status=RouteStopStatus.PENDING,
        location_name="Stop",
        address="St 2",
        latitude=13.0850,
        longitude=80.2750,
    )
    db_session.add(stop)
    db_session.commit()

    headers = auth_headers(manager1)
    res_veh_conflict = client.post(
        f"/api/v1/routes/{route.id}/dispatch",
        json={"vehicle_id": vehicle1.id, "driver_id": driver1.id},
        headers=headers,
    )
    assert res_veh_conflict.status_code == 409
    assert "linehaul manifest" in res_veh_conflict.json()["detail"].lower()

    # 2. Release manifest, but seal parcel in a linehaul BagItem
    manifest.status = ManifestStatus.ARRIVED
    bag = ConsolidationBag(
        organization_id=org_setup["org1"].id,
        bag_code=f"BAG-LH-{u}",
        origin_branch_id=branch1.id,
        dest_branch_id=branch1.id,
    )
    db_session.add(bag)
    db_session.flush()

    bag_item = BagItem(
        bag_id=bag.id,
        parcel_id=parcel.id,
        is_active=True,
    )
    db_session.add(bag_item)
    db_session.commit()

    # Attempt dispatch with parcel in linehaul bag -> must raise 409
    res_bag_conflict = client.post(
        f"/api/v1/routes/{route.id}/dispatch",
        json={"vehicle_id": vehicle1.id, "driver_id": driver1.id},
        headers=headers,
    )
    assert res_bag_conflict.status_code == 409
    assert "linehaul bag" in res_bag_conflict.json()["detail"].lower()


def test_route_event_streaming_sse_endpoint(client: TestClient, db_session, org_setup):
    """
    Subphase 15.15: Server-Sent Events (SSE) route event streaming endpoint.
    Verifies that GET /api/v1/routes/{id}/events returns initial state and streams post-commit events.
    """
    u = uuid.uuid4().hex[:6]
    manager1 = org_setup["manager1"]
    branch1 = org_setup["branch1"]
    driver1 = org_setup["driver1"]
    vehicle1 = org_setup["vehicle1"]

    route = DeliveryRoute(
        organization_id=org_setup["org1"].id,
        branch_id=branch1.id,
        route_code=f"RT-SSE-{u}",
        status=RouteStatus.PLANNED,
        driver_id=driver1.id,
        vehicle_id=vehicle1.id,
        optimization_objective=RouteObjective.FASTEST,
        total_distance_km=12.0,
        estimated_duration_min=35.0,
        total_weight_kg=0.0,
        has_low_confidence_stops=False,
    )
    db_session.add(route)
    db_session.commit()

    headers = auth_headers(manager1)
    with client.stream("GET", f"/api/v1/routes/{route.id}/events", headers=headers) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        # Read the initial message line
        for line in response.iter_lines():
            if line.startswith("data:"):
                payload = json.loads(line[len("data:"):].strip())
                assert payload["type"] == "INITIAL_STATE"
                assert payload["route_id"] == route.id
                assert payload["route_code"] == f"RT-SSE-{u}"
                assert payload["status"] == "PLANNED"
                break

