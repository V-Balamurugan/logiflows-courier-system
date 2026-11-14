from unittest.mock import patch
import pytest

from app.core.security import create_access_token, get_password_hash
from app.models.assignment import DeliveryAssignment
from app.models.branch import Branch
from app.models.enums import (
    AssignmentStatus,
    OperatingStatus,
    ParcelStatus,
    PaymentStatus,
    RouteObjective,
    RouteStatus,
    RouteStopStatus,
    ServiceType,
    UserRole,
    VehicleStatus,
    VehicleType,
)
from app.models.organization import Organization
from app.models.parcel import Parcel
from app.models.route import DeliveryRoute, RouteStop
from app.models.tracking import TrackingHistory
from app.models.user import User
from app.models.vehicle import Vehicle
from app.services.routing_providers import RoutingEngine


def auth_headers(user: User) -> dict:
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


def _make_parcel(
    db_session,
    tracking_number: str,
    origin_branch: Branch,
    dest_branch: Branch,
    customer: User,
    weight_kg: float = 5.0,
    status: ParcelStatus = ParcelStatus.AT_DESTINATION_BRANCH,
    dest_lat: float | None = None,
    dest_lng: float | None = None,
    origin_lat: float | None = None,
    origin_lng: float | None = None,
    service_type: ServiceType = ServiceType.STANDARD,
) -> Parcel:
    existing = db_session.query(Parcel).filter(Parcel.tracking_number == tracking_number).first()
    if existing:
        return existing
    parcel = Parcel(
        tracking_number=tracking_number,
        customer_id=customer.id,
        origin_branch_id=origin_branch.id,
        dest_branch_id=dest_branch.id,
        sender_name="Sender Co",
        sender_phone="9876501111",
        sender_address="Sender Plot 10",
        sender_city=origin_branch.city,
        sender_state=origin_branch.state,
        sender_pincode=origin_branch.pincode,
        receiver_name=f"Receiver {tracking_number}",
        receiver_phone="9876502222",
        receiver_address="Receiver Avenue 42",
        receiver_city=dest_branch.city,
        receiver_state=dest_branch.state,
        receiver_pincode=dest_branch.pincode,
        origin_latitude=origin_lat,
        origin_longitude=origin_lng,
        dest_latitude=dest_lat,
        dest_longitude=dest_lng,
        weight_kg=weight_kg,
        length_cm=20.0,
        width_cm=15.0,
        height_cm=10.0,
        volumetric_weight_kg=0.6,
        service_type=service_type,
        base_charge=120.0,
        total_charge=141.6,
        payment_status=PaymentStatus.PAID,
        delivery_status=status,
        current_location=dest_branch.branch_name,
    )
    db_session.add(parcel)
    db_session.flush()
    return parcel


@pytest.fixture
def phase15_env(db_session):
    org1 = db_session.query(Organization).filter(Organization.code == "P15_ORG1").first()
    if not org1:
        org1 = Organization(
            name="Phase15 Express Corp",
            code="P15_ORG1",
            contact_email="ops@p15a.com",
            is_active=True,
        )
        db_session.add(org1)
        db_session.flush()

    org2 = db_session.query(Organization).filter(Organization.code == "P15_ORG2").first()
    if not org2:
        org2 = Organization(
            name="Foreign Route Org",
            code="P15_ORG2",
            contact_email="ops@p15b.com",
            is_active=True,
        )
        db_session.add(org2)
        db_session.flush()

    def ensure_branch(code, name, org, city, pincode, lat=19.0760, lng=72.8777):
        b = db_session.query(Branch).filter(Branch.branch_code == code).first()
        if not b:
            b = Branch(
                organization_id=org.id,
                branch_code=code,
                branch_name=name,
                address=f"{name} Complex",
                pincode=pincode,
                city=city,
                state="Maharashtra",
                country="India",
                contact_email=f"{code.lower()}@p15.com",
                contact_phone="9876543210",
                latitude=lat,
                longitude=lng,
                operating_status=OperatingStatus.ACTIVE,
                is_active=True,
            )
            db_session.add(b)
            db_session.flush()
        return b

    b_bom = ensure_branch("P15_BOM", "P15 Mumbai Central", org1, "Mumbai", "400001", 19.0760, 72.8777)
    b_pune = ensure_branch("P15_PNQ", "P15 Pune Hub", org1, "Pune", "411001", 18.5204, 73.8567)
    b_nocoord = ensure_branch("P15_NCD", "P15 NoCoord Hub", org1, "Nashik", "422001", None, None)
    b_for = ensure_branch("P15_FOR", "P15 Foreign Hub", org2, "Chennai", "600001", 13.0827, 80.2707)

    def ensure_user(email, role, org, branch, name):
        u = db_session.query(User).filter(User.email == email).first()
        if not u:
            u = User(
                email=email,
                hashed_password=get_password_hash("Pass123!"),
                full_name=name,
                role=role,
                organization_id=org.id if org else None,
                branch_id=branch.id if branch else None,
                is_active=True,
            )
            db_session.add(u)
            db_session.flush()
        return u

    oa1 = ensure_user("oa1@p15.com", UserRole.ORG_ADMIN, org1, None, "P15 Org Admin 1")
    bm_bom = ensure_user("bm_bom@p15.com", UserRole.BRANCH_MANAGER, org1, b_bom, "P15 BOM Manager")
    bm_pune = ensure_user("bm_pnq@p15.com", UserRole.BRANCH_MANAGER, org1, b_pune, "P15 PNQ Manager")
    agent1 = ensure_user("agent1@p15.com", UserRole.DELIVERY_AGENT, org1, b_bom, "P15 Driver One")
    agent2 = ensure_user("agent2@p15.com", UserRole.DELIVERY_AGENT, org1, b_bom, "P15 Driver Two")
    cust1 = ensure_user("cust1@p15.com", UserRole.CUSTOMER, org1, None, "P15 Customer")

    oa2 = ensure_user("oa2@p15.com", UserRole.ORG_ADMIN, org2, None, "P15 Org Admin 2")

    def ensure_vehicle(vnum, org, branch, vtype=VehicleType.VAN, max_w=200.0):
        v = db_session.query(Vehicle).filter(Vehicle.vehicle_number == vnum).first()
        if not v:
            v = Vehicle(
                organization_id=org.id,
                branch_id=branch.id,
                vehicle_number=vnum,
                vehicle_type=vtype,
                model="Test EV Van",
                max_weight_kg=max_w,
                status=VehicleStatus.AVAILABLE,
                is_active=True,
            )
            db_session.add(v)
            db_session.flush()
        return v

    van_bom = ensure_vehicle("MH-15-RT-101", org1, b_bom, VehicleType.VAN, 100.0)
    bike_small = ensure_vehicle("MH-15-BK-102", org1, b_bom, VehicleType.BIKE, 10.0)
    van_pune = ensure_vehicle("MH-15-PN-103", org1, b_pune, VehicleType.VAN, 200.0)
    van_for = ensure_vehicle("TN-15-FR-999", org2, b_for, VehicleType.VAN, 300.0)

    db_session.commit()
    return {
        "org1": org1,
        "org2": org2,
        "b_bom": b_bom,
        "b_pune": b_pune,
        "b_nocoord": b_nocoord,
        "b_for": b_for,
        "oa1": oa1,
        "bm_bom": bm_bom,
        "bm_pune": bm_pune,
        "agent1": agent1,
        "agent2": agent2,
        "cust1": cust1,
        "oa2": oa2,
        "van_bom": van_bom,
        "bike_small": bike_small,
        "van_pune": van_pune,
        "van_for": van_for,
    }


def test_stateless_preview_vicinity_capacity_warning_and_fallback(client, db_session, phase15_env):
    """Preview resolves explicit vs vicinity coords, flags capacity exceed, and discloses fallback."""
    env = phase15_env
    bm_hdrs = auth_headers(env["bm_bom"])

    # Parcel 1 has explicit stored destination coords; Parcel 2 relies on vicinity estimate
    p1 = _make_parcel(
        db_session,
        "P15-PREV-01",
        env["b_bom"],
        env["b_bom"],
        env["cust1"],
        weight_kg=8.0,
        dest_lat=19.1200,
        dest_lng=72.9100,
    )
    p2 = _make_parcel(
        db_session,
        "P15-PREV-02",
        env["b_bom"],
        env["b_bom"],
        env["cust1"],
        weight_kg=7.0,
    )
    db_session.commit()

    # Use bike_small (10 kg capacity) against 15 kg cargo -> capacity_exceeded=True, no DB locks created
    res = client.post(
        "/api/v1/routes/preview",
        headers=bm_hdrs,
        json={
            "branch_id": env["b_bom"].id,
            "vehicle_id": env["bike_small"].id,
            "objective": "FASTEST",
            "provider": "openrouteservice",
            "return_to_hub": True,
            "stops": [
                {"parcel_id": p1.id, "stop_type": "DELIVERY"},
                {"parcel_id": p2.id, "stop_type": "DELIVERY"},
                {
                    "stop_type": "DELIVERY",
                    "location_name": "Ad-Hoc Kiosk",
                    "latitude": 19.0950,
                    "longitude": 72.8900,
                },
            ],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["capacity_exceeded"] is True
    assert body["utilization_pct"] == 150.0
    assert body["provider_used"] == "local_fallback"
    assert body["is_fallback"] is True
    assert "unavailable" in body["fallback_reason"].lower()
    sources = {s["parcel_id"]: s["coords_source"] for s in body["stops"]}
    assert sources[p1.id] == "PARCEL_STORED"
    assert sources[p2.id] == "BRANCH_VICINITY_ESTIMATE"
    assert sources[None] == "EXPLICIT"
    assert len(body["geometry_points"]) >= 4

    # Preview is stateless: zero DeliveryRoute rows persisted for p1/p2
    assert db_session.query(RouteStop).filter(RouteStop.parcel_id == p1.id).count() == 0

    # Branch without depot coordinates returns 422
    oa_hdrs = auth_headers(env["oa1"])
    bad_branch = client.post(
        "/api/v1/routes/preview",
        headers=oa_hdrs,
        json={
            "branch_id": env["b_nocoord"].id,
            "stops": [{"stop_type": "DELIVERY", "location_name": "X", "latitude": 19.99, "longitude": 73.78}],
        },
    )
    assert bad_branch.status_code == 422

    # Extra unknown fields rejected (extra="forbid")
    bad_extra = client.post(
        "/api/v1/routes/preview",
        headers=bm_hdrs,
        json={
            "branch_id": env["b_bom"].id,
            "parcel_ids": [p1.id],
            "injected_admin": True,
        },
    )
    assert bad_extra.status_code == 422


def test_create_reoptimize_manual_and_optimistic_concurrency(client, db_session, phase15_env):
    """Creating a route runs 2-opt TSP savings; manual reorder bumps version_id and detects stale edits."""
    env = phase15_env
    bm_hdrs = auth_headers(env["bm_bom"])

    # Create intentionally zig-zagged coords from hub (19.0760, 72.8777) so baseline > 2-opt
    p_far_n = _make_parcel(
        db_session, "P15-OPT-01", env["b_bom"], env["b_bom"], env["cust1"],
        weight_kg=4.0, dest_lat=19.2200, dest_lng=72.8800,
    )
    p_south = _make_parcel(
        db_session, "P15-OPT-02", env["b_bom"], env["b_bom"], env["cust1"],
        weight_kg=4.0, dest_lat=18.9300, dest_lng=72.8300,
    )
    p_near_n = _make_parcel(
        db_session, "P15-OPT-03", env["b_bom"], env["b_bom"], env["cust1"],
        weight_kg=4.0, dest_lat=19.2000, dest_lng=72.8900,
    )
    db_session.commit()

    create_res = client.post(
        "/api/v1/routes",
        headers=bm_hdrs,
        json={
            "branch_id": env["b_bom"].id,
            "vehicle_id": env["van_bom"].id,
            "driver_id": env["agent1"].id,
            "objective": "SHORTEST",
            "return_to_hub": True,
            "parcel_ids": [p_far_n.id, p_south.id, p_near_n.id],
            "notes": "Morning South-North wave",
        },
    )
    assert create_res.status_code == 201
    route = create_res.json()
    assert route["status"] == "PLANNED"
    assert route["version_id"] == 1
    assert route["distance_saved_km"] > 0.0
    assert route["total_distance_km"] < route["baseline_distance_km"]
    stop_ids = [s["id"] for s in route["stops"]]

    # Invalid manual permutation (missing a stop) -> 422
    bad_manual = client.post(
        f"/api/v1/routes/{route['id']}/reoptimize",
        headers=bm_hdrs,
        json={
            "objective": "MANUAL",
            "manual_stop_ids": stop_ids[:2],
            "expected_version_id": 1,
        },
    )
    assert bad_manual.status_code == 422

    # Valid manual permutation bumps version_id
    reversed_ids = list(reversed(stop_ids))
    reopt_res = client.post(
        f"/api/v1/routes/{route['id']}/reoptimize",
        headers=bm_hdrs,
        json={
            "objective": "MANUAL",
            "manual_stop_ids": reversed_ids,
            "expected_version_id": 1,
        },
    )
    assert reopt_res.status_code == 200
    reopted = reopt_res.json()
    assert reopted["version_id"] == 2
    assert [s["id"] for s in reopted["stops"]] == reversed_ids

    # Stale expected_version_id=1 must fail with 409 Conflict
    stale_res = client.post(
        f"/api/v1/routes/{route['id']}/reoptimize",
        headers=bm_hdrs,
        json={
            "objective": "FASTEST",
            "expected_version_id": 1,
        },
    )
    assert stale_res.status_code == 409

    # Cleanup via cancel so later tests have clean state
    cancel_res = client.post(
        f"/api/v1/routes/{route['id']}/cancel",
        headers=bm_hdrs,
        json={"cancellation_reason": "Replanned morning wave"},
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"


def test_atomic_dispatch_cas_vehicle_conflict_and_rollback(client, db_session, phase15_env):
    """Dispatch atomically locks vehicle, prevents concurrent double-booking, and rolls back on failure."""
    env = phase15_env
    bm_hdrs = auth_headers(env["bm_bom"])

    p1 = _make_parcel(
        db_session, "P15-DSP-01", env["b_bom"], env["b_bom"], env["cust1"],
        weight_kg=5.0, dest_lat=19.10, dest_lng=72.88,
    )
    p2 = _make_parcel(
        db_session, "P15-DSP-02", env["b_bom"], env["b_bom"], env["cust1"],
        weight_kg=5.0, dest_lat=19.14, dest_lng=72.90,
    )
    p3 = _make_parcel(
        db_session, "P15-DSP-03", env["b_bom"], env["b_bom"], env["cust1"],
        weight_kg=5.0, dest_lat=19.16, dest_lng=72.85,
    )
    db_session.commit()

    r1 = client.post(
        "/api/v1/routes",
        headers=bm_hdrs,
        json={"branch_id": env["b_bom"].id, "parcel_ids": [p1.id, p2.id]},
    ).json()
    r2 = client.post(
        "/api/v1/routes",
        headers=bm_hdrs,
        json={"branch_id": env["b_bom"].id, "parcel_ids": [p3.id]},
    ).json()

    # Simulated mid-dispatch state machine exception must roll back BOTH vehicle lock and assignments
    with patch(
        "app.services.route_service.ShipmentStateMachine.transition",
        side_effect=RuntimeError("Simulated transient failure"),
    ):
        with pytest.raises(RuntimeError):
            client.post(
                f"/api/v1/routes/{r1['id']}/dispatch",
                headers=bm_hdrs,
                json={"vehicle_id": env["van_bom"].id, "driver_id": env["agent1"].id},
            )

    db_session.expire_all()
    assert db_session.get(Vehicle, env["van_bom"].id).status == VehicleStatus.AVAILABLE
    assert db_session.get(DeliveryRoute, r1["id"]).status == RouteStatus.PLANNED
    assert db_session.query(DeliveryAssignment).filter(DeliveryAssignment.parcel_id == p1.id).count() == 0

    # Real dispatch of r1 succeeds cleanly
    dsp1 = client.post(
        f"/api/v1/routes/{r1['id']}/dispatch",
        headers=bm_hdrs,
        json={"vehicle_id": env["van_bom"].id, "driver_id": env["agent1"].id},
    )
    assert dsp1.status_code == 200
    body1 = dsp1.json()
    assert body1["status"] == "DISPATCHED"
    assert body1["is_active_dispatch"] is True
    assert all(s["assignment_id"] is not None for s in body1["stops"])

    # Attempting to dispatch r2 with same locked vehicle fails with 409 Conflict
    dsp2 = client.post(
        f"/api/v1/routes/{r2['id']}/dispatch",
        headers=bm_hdrs,
        json={"vehicle_id": env["van_bom"].id, "driver_id": env["agent2"].id},
    )
    assert dsp2.status_code == 409

    # Cancel r1 & r2 to restore clean fleet state
    assert client.post(
        f"/api/v1/routes/{r1['id']}/cancel",
        headers=bm_hdrs,
        json={"cancellation_reason": "End of dispatch concurrency test"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/routes/{r2['id']}/cancel",
        headers=bm_hdrs,
        json={"cancellation_reason": "End of dispatch concurrency test"},
    ).status_code == 200


def test_execution_gps_multi_stop_vehicle_retention_and_autocomplete(client, db_session, phase15_env):
    """Completing stop 1 keeps vehicle IN_TRANSIT until final stop finishes, then releases vehicle & records GPS."""
    env = phase15_env
    bm_hdrs = auth_headers(env["bm_bom"])
    agent1_hdrs = auth_headers(env["agent1"])

    p1 = _make_parcel(
        db_session, "P15-EXE-01", env["b_bom"], env["b_bom"], env["cust1"],
        weight_kg=3.0, dest_lat=19.110, dest_lng=72.885,
    )
    p2 = _make_parcel(
        db_session, "P15-EXE-02", env["b_bom"], env["b_bom"], env["cust1"],
        weight_kg=4.0, dest_lat=19.155, dest_lng=72.905,
    )
    db_session.commit()

    r = client.post(
        "/api/v1/routes",
        headers=bm_hdrs,
        json={
            "branch_id": env["b_bom"].id,
            "vehicle_id": env["van_bom"].id,
            "driver_id": env["agent1"].id,
            "parcel_ids": [p1.id, p2.id],
        },
    ).json()
    dsp = client.post(f"/api/v1/routes/{r['id']}/dispatch", headers=bm_hdrs, json={}).json()
    stop1, stop2 = dsp["stops"][0], dsp["stops"][1]

    # Assigned driver starts route
    started = client.post(f"/api/v1/routes/{r['id']}/start", headers=agent1_hdrs)
    assert started.status_code == 200
    assert started.json()["status"] == "IN_PROGRESS"
    assert started.json()["stops"][0]["status"] == "EN_ROUTE"

    # Driver marks stop 1 DELIVERED with explicit GPS coords
    s1_done = client.post(
        f"/api/v1/routes/{r['id']}/stops/{stop1['id']}/update",
        headers=agent1_hdrs,
        json={"status": "COMPLETED", "latitude": 19.1105, "longitude": 72.8855, "notes": "Left at reception"},
    )
    assert s1_done.status_code == 200
    after_s1 = s1_done.json()
    assert after_s1["status"] == "IN_PROGRESS"
    assert after_s1["completed_stops"] == 1

    # Critical regression check: vehicle remains IN_TRANSIT while stop 2 is pending!
    db_session.expire_all()
    assert db_session.get(Vehicle, env["van_bom"].id).status == VehicleStatus.IN_TRANSIT
    stop1_parcel = db_session.get(Parcel, stop1["parcel_id"])
    assert stop1_parcel.delivery_status == ParcelStatus.DELIVERED
    gps_hist = (
        db_session.query(TrackingHistory)
        .filter(TrackingHistory.parcel_id == stop1["parcel_id"], TrackingHistory.status == ParcelStatus.DELIVERED)
        .first()
    )
    assert gps_hist is not None
    assert gps_hist.latitude == 19.1105
    assert gps_hist.longitude == 72.8855

    # Invalid stop update: FAILED without failure_reason -> 422
    bad_fail = client.post(
        f"/api/v1/routes/{r['id']}/stops/{stop2['id']}/update",
        headers=agent1_hdrs,
        json={"status": "FAILED"},
    )
    assert bad_fail.status_code == 422

    # Driver arrives then marks stop 2 FAILED -> route auto-completes and vehicle releases
    arr_res = client.post(
        f"/api/v1/routes/{r['id']}/stops/{stop2['id']}/update",
        headers=agent1_hdrs,
        json={"status": "ARRIVED", "latitude": 19.1552, "longitude": 72.9052},
    )
    assert arr_res.status_code == 200
    assert arr_res.json()["stops"][1]["status"] == "ARRIVED"

    fail_res = client.post(
        f"/api/v1/routes/{r['id']}/stops/{stop2['id']}/update",
        headers=agent1_hdrs,
        json={"status": "FAILED", "failure_reason": "Premises locked", "latitude": 19.1552, "longitude": 72.9052},
    )
    assert fail_res.status_code == 200
    final_route = fail_res.json()
    assert final_route["status"] == "COMPLETED"
    assert final_route["is_active_dispatch"] is False

    db_session.expire_all()
    assert db_session.get(Vehicle, env["van_bom"].id).status == VehicleStatus.AVAILABLE
    assert db_session.get(Parcel, stop2["parcel_id"]).delivery_status == ParcelStatus.DELIVERY_FAILED

    # Subsequent update on finalized stop fails with 409 Conflict
    late_res = client.post(
        f"/api/v1/routes/{r['id']}/stops/{stop2['id']}/update",
        headers=agent1_hdrs,
        json={"status": "COMPLETED"},
    )
    assert late_res.status_code == 409


def test_pickup_route_cancel_and_cross_module_409_guards(client, db_session, phase15_env):
    """Pickup dispatch/cancel works cleanly and active routes block branch/vehicle/assignment/linehaul conflicts."""
    env = phase15_env
    bm_hdrs = auth_headers(env["bm_bom"])
    oa_hdrs = auth_headers(env["oa1"])

    p_pick = _make_parcel(
        db_session, "P15-PKP-01", env["b_bom"], env["b_pune"], env["cust1"],
        status=ParcelStatus.BOOKED, origin_lat=19.082, origin_lng=72.882,
    )
    p_del = _make_parcel(
        db_session, "P15-GRD-01", env["b_bom"], env["b_pune"], env["cust1"],
        status=ParcelStatus.AT_ORIGIN_BRANCH, dest_lat=19.092, dest_lng=72.892,
    )
    db_session.commit()

    # Create & dispatch a pickup route
    pkp_route = client.post(
        "/api/v1/routes",
        headers=bm_hdrs,
        json={
            "branch_id": env["b_bom"].id,
            "vehicle_id": env["van_bom"].id,
            "driver_id": env["agent1"].id,
            "stops": [{"parcel_id": p_pick.id, "stop_type": "PICKUP"}],
        },
    ).json()
    assert client.post(f"/api/v1/routes/{pkp_route['id']}/dispatch", headers=bm_hdrs, json={}).status_code == 200
    db_session.expire_all()
    assert db_session.get(Parcel, p_pick.id).delivery_status == ParcelStatus.PICKUP_SCHEDULED

    # Cross-module Guard 1: Branch soft-deactivation blocked specifically by active route (isolated zero-parcel branch)
    b_adhoc = Branch(
        organization_id=env["org1"].id,
        branch_code="P15_ADH",
        branch_name="P15 Adhoc Guard Hub",
        address="Guard Street",
        pincode="400099",
        city="Mumbai",
        state="Maharashtra",
        country="India",
        contact_email="adhoc@p15.com",
        contact_phone="9876543999",
        latitude=19.08,
        longitude=72.88,
        operating_status=OperatingStatus.ACTIVE,
        is_active=True,
    )
    db_session.add(b_adhoc)
    db_session.commit()
    adhoc_route = client.post(
        "/api/v1/routes",
        headers=oa_hdrs,
        json={
            "branch_id": b_adhoc.id,
            "stops": [{"stop_type": "DELIVERY", "location_name": "Kiosk", "latitude": 19.09, "longitude": 72.89}],
        },
    ).json()
    br_del = client.delete(f"/api/v1/branches/{b_adhoc.id}", headers=oa_hdrs)
    assert br_del.status_code == 409
    assert "route" in br_del.json()["detail"].lower()
    assert client.post(
        f"/api/v1/routes/{adhoc_route['id']}/cancel",
        headers=oa_hdrs,
        json={"cancellation_reason": "Clear guard test route"},
    ).status_code == 200

    # Cross-module Guard 2: Vehicle maintenance blocked while dispatched on route
    veh_maint = client.patch(
        f"/api/v1/vehicles/{env['van_bom'].id}/maintenance",
        headers=bm_hdrs,
        json={"is_in_maintenance": True, "notes": "Service check"},
    )
    assert veh_maint.status_code == 409

    # Cross-module Guard 3: Creating manual assignment blocked while parcel is on active RouteStop
    assign_conflict = client.post(
        "/api/v1/assignments",
        headers=bm_hdrs,
        json={"parcel_id": p_pick.id, "employee_id": env["agent2"].id, "assignment_type": "PICKUP"},
    )
    assert assign_conflict.status_code == 409

    # Cancel pickup route -> restores parcel to BOOKED and frees vehicle
    cnl = client.post(
        f"/api/v1/routes/{pkp_route['id']}/cancel",
        headers=bm_hdrs,
        json={"cancellation_reason": "Customer rescheduled pickup"},
    )
    assert cnl.status_code == 200
    db_session.expire_all()
    assert db_session.get(Parcel, p_pick.id).delivery_status == ParcelStatus.BOOKED
    assert db_session.get(Vehicle, env["van_bom"].id).status == VehicleStatus.AVAILABLE

    # Cross-module Guard 4: Parcel on PLANNED route blocks linehaul bag packing (409)
    del_route = client.post(
        "/api/v1/routes",
        headers=bm_hdrs,
        json={
            "branch_id": env["b_bom"].id,
            "parcel_ids": [p_del.id],
        },
    ).json()
    bag_res = client.post(
        "/api/v1/linehaul/bags",
        headers=bm_hdrs,
        json={"origin_branch_id": env["b_bom"].id, "dest_branch_id": env["b_pune"].id},
    ).json()
    pack_conflict = client.post(
        f"/api/v1/linehaul/bags/{bag_res['id']}/parcels",
        headers=bm_hdrs,
        json={"parcel_ids": [p_del.id]},
    )
    assert pack_conflict.status_code == 409

    # Cancel planned route cleanly
    assert client.post(
        f"/api/v1/routes/{del_route['id']}/cancel",
        headers=bm_hdrs,
        json={"cancellation_reason": "Sent via linehaul instead"},
    ).status_code == 200


def test_rbac_and_tenant_branch_agent_negative_isolation(client, db_session, phase15_env):
    """Verify strict RBAC 403 and anti-enumeration 404 across org, branch, and driver boundaries."""
    env = phase15_env
    bm_bom_hdrs = auth_headers(env["bm_bom"])
    bm_pune_hdrs = auth_headers(env["bm_pune"])
    oa2_hdrs = auth_headers(env["oa2"])
    agent1_hdrs = auth_headers(env["agent1"])
    agent2_hdrs = auth_headers(env["agent2"])
    cust_hdrs = auth_headers(env["cust1"])

    p_bom = _make_parcel(
        db_session, "P15-SEC-01", env["b_bom"], env["b_bom"], env["cust1"],
        dest_lat=19.10, dest_lng=72.88,
    )
    p_pune = _make_parcel(
        db_session, "P15-SEC-02", env["b_pune"], env["b_pune"], env["cust1"],
        dest_lat=18.53, dest_lng=73.86,
    )
    p_for = _make_parcel(
        db_session, "P15-SEC-03", env["b_for"], env["b_for"], env["cust1"],
        dest_lat=13.09, dest_lng=80.28,
    )
    db_session.commit()

    route_res = client.post(
        "/api/v1/routes",
        headers=bm_bom_hdrs,
        json={
            "branch_id": env["b_bom"].id,
            "vehicle_id": env["van_bom"].id,
            "driver_id": env["agent1"].id,
            "parcel_ids": [p_bom.id],
        },
    ).json()
    rid = route_res["id"]
    sid = route_res["stops"][0]["id"]
    assert client.post(f"/api/v1/routes/{rid}/dispatch", headers=bm_bom_hdrs, json={}).status_code == 200

    # Customers denied all route endpoints (403)
    for method, url, payload in [
        ("POST", "/api/v1/routes/preview", {"branch_id": env["b_bom"].id, "parcel_ids": [p_bom.id]}),
        ("POST", "/api/v1/routes", {"branch_id": env["b_bom"].id, "parcel_ids": [p_bom.id]}),
        ("GET", "/api/v1/routes", None),
        ("GET", f"/api/v1/routes/{rid}", None),
        ("POST", f"/api/v1/routes/{rid}/start", None),
        ("POST", f"/api/v1/routes/{rid}/stops/{sid}/update", {"status": "COMPLETED"}),
        ("POST", f"/api/v1/routes/{rid}/cancel", {"cancellation_reason": "Hack"}),
    ]:
        resp = client.request(method, url, json=payload, headers=cust_hdrs)
        assert resp.status_code == 403, f"Expected 403 for CUSTOMER {method} {url}, got {resp.status_code}"

    # Delivery Agents cannot preview, create, reoptimize, dispatch, or cancel (403)
    for method, url, payload in [
        ("POST", "/api/v1/routes/preview", {"branch_id": env["b_bom"].id, "parcel_ids": [p_bom.id]}),
        ("POST", "/api/v1/routes", {"branch_id": env["b_bom"].id, "parcel_ids": [p_bom.id]}),
        ("POST", f"/api/v1/routes/{rid}/reoptimize", {"objective": "FASTEST"}),
        ("POST", f"/api/v1/routes/{rid}/dispatch", {}),
        ("POST", f"/api/v1/routes/{rid}/cancel", {"cancellation_reason": "Unauthorized"}),
    ]:
        resp = client.request(method, url, json=payload, headers=agent1_hdrs)
        assert resp.status_code == 403, f"Expected 403 for AGENT {method} {url}, got {resp.status_code}"

    # Non-assigned Delivery Agent (agent2) in same branch gets 404 anti-enumeration on agent1's route
    assert client.get(f"/api/v1/routes/{rid}", headers=agent2_hdrs).status_code == 404
    assert client.post(f"/api/v1/routes/{rid}/start", headers=agent2_hdrs).status_code == 404
    assert (
        client.post(
            f"/api/v1/routes/{rid}/stops/{sid}/update",
            headers=agent2_hdrs,
            json={"status": "COMPLETED"},
        ).status_code
        == 404
    )
    assert all(r["driver_id"] == env["agent2"].id for r in client.get("/api/v1/routes", headers=agent2_hdrs).json())

    # Cross-branch BM (Pune) & Cross-org OA (Org 2) get 404 on BOM route
    for foreign_hdrs in (bm_pune_hdrs, oa2_hdrs):
        assert client.get(f"/api/v1/routes/{rid}", headers=foreign_hdrs).status_code == 404
        assert client.post(f"/api/v1/routes/{rid}/reoptimize", headers=foreign_hdrs, json={"objective": "FASTEST"}).status_code == 404
        assert client.post(f"/api/v1/routes/{rid}/cancel", headers=foreign_hdrs, json={"cancellation_reason": "Cross tenant access check"}).status_code == 404

    # Altering IDs in body cannot cross branch or tenant boundaries (404)
    assert (
        client.post(
            "/api/v1/routes",
            headers=bm_bom_hdrs,
            json={"branch_id": env["b_pune"].id, "parcel_ids": [p_pune.id]},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/routes",
            headers=bm_bom_hdrs,
            json={"branch_id": env["b_bom"].id, "parcel_ids": [p_for.id]},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/routes",
            headers=oa2_hdrs,
            json={"branch_id": env["b_for"].id, "vehicle_id": env["van_bom"].id, "parcel_ids": [p_for.id]},
        ).status_code
        == 404
    )

    # Clean up active route
    assert client.post(
        f"/api/v1/routes/{rid}/cancel",
        headers=bm_bom_hdrs,
        json={"cancellation_reason": "Security test cleanup"},
    ).status_code == 200
