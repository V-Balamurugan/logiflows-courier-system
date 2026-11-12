import pytest
from app.core.security import create_access_token, get_password_hash
from app.models.branch import Branch
from app.models.enums import (
    BagStatus,
    DiscrepancyStatus,
    DiscrepancyType,
    ManifestItemStatus,
    ManifestStatus,
    OperatingStatus,
    ParcelStatus,
    PaymentStatus,
    ServiceType,
    UserRole,
    VehicleStatus,
    VehicleType,
)
from app.models.organization import Organization
from app.models.parcel import Parcel
from app.models.user import User
from app.models.vehicle import Vehicle


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
    status: ParcelStatus = ParcelStatus.AT_ORIGIN_BRANCH,
) -> Parcel:
    p = Parcel(
        tracking_number=tracking_number,
        customer_id=customer.id,
        origin_branch_id=origin_branch.id,
        dest_branch_id=dest_branch.id,
        sender_name="Sender Co",
        sender_phone="9876500001",
        sender_address="Warehouse 1",
        sender_city=origin_branch.city,
        sender_state=origin_branch.state,
        sender_pincode=origin_branch.pincode,
        receiver_name="Receiver Co",
        receiver_phone="9876500002",
        receiver_address="Hub Street 9",
        receiver_city=dest_branch.city,
        receiver_state=dest_branch.state,
        receiver_pincode=dest_branch.pincode,
        weight_kg=weight_kg,
        length_cm=20.0,
        width_cm=15.0,
        height_cm=10.0,
        volumetric_weight_kg=0.6,
        service_type=ServiceType.EXPRESS,
        base_charge=100.0,
        total_charge=118.0,
        payment_status=PaymentStatus.PAID,
        delivery_status=status,
        current_location=origin_branch.branch_name,
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def phase14_env(db_session):
    org1 = db_session.query(Organization).filter(Organization.code == "P14_ORG1").first()
    if not org1:
        org1 = Organization(name="Linehaul Corp 1", code="P14_ORG1", contact_email="ops@p14a.com", is_active=True)
        db_session.add(org1)
        db_session.flush()

    org2 = db_session.query(Organization).filter(Organization.code == "P14_ORG2").first()
    if not org2:
        org2 = Organization(name="Foreign Linehaul 2", code="P14_ORG2", contact_email="ops@p14b.com", is_active=True)
        db_session.add(org2)
        db_session.flush()

    def ensure_branch(code, name, org, city, pincode):
        b = db_session.query(Branch).filter(Branch.branch_code == code).first()
        if not b:
            b = Branch(
                organization_id=org.id,
                branch_code=code,
                branch_name=name,
                address=f"{name} Road",
                pincode=pincode,
                city=city,
                state="State",
                country="India",
                contact_email=f"{code.lower()}@p14.com",
                contact_phone="9876543210",
                latitude=19.07,
                longitude=72.87,
                operating_status=OperatingStatus.ACTIVE,
                is_active=True,
            )
            db_session.add(b)
            db_session.flush()
        return b

    b_origin = ensure_branch("P14-BOM", "Mumbai Linehaul Hub", org1, "Mumbai", "400069")
    b_dest = ensure_branch("P14-DEL", "Delhi Linehaul Hub", org1, "New Delhi", "110037")
    b_other = ensure_branch("P14-BLR", "Bengaluru Spokes", org1, "Bengaluru", "560100")
    b_foreign = ensure_branch("P14-FGN", "Foreign Hub", org2, "Pune", "411001")

    def ensure_user(email, role, org, branch=None, name="User"):
        u = db_session.query(User).filter(User.email == email).first()
        if not u:
            u = User(
                organization_id=org.id if org else None,
                branch_id=branch.id if branch else None,
                email=email,
                hashed_password=get_password_hash("Pass@12345"),
                full_name=name,
                role=role,
                is_active=True,
            )
            db_session.add(u)
            db_session.flush()
        return u

    org1_admin = ensure_user("p14_orgadmin@a.com", UserRole.ORG_ADMIN, org1, None, "P14 OrgAdmin")
    bm_origin = ensure_user("p14_bm_origin@a.com", UserRole.BRANCH_MANAGER, org1, b_origin, "Origin BM")
    bm_dest = ensure_user("p14_bm_dest@a.com", UserRole.BRANCH_MANAGER, org1, b_dest, "Dest BM")
    driver = ensure_user("p14_driver@a.com", UserRole.DELIVERY_AGENT, org1, b_origin, "Linehaul Driver")
    other_agent = ensure_user("p14_other_agent@a.com", UserRole.DELIVERY_AGENT, org1, b_origin, "Other Agent")
    customer = ensure_user("p14_cust@a.com", UserRole.CUSTOMER, org1, None, "P14 Customer")
    org2_admin = ensure_user("p14_org2admin@b.com", UserRole.ORG_ADMIN, org2, b_foreign, "Foreign Admin")

    def ensure_vehicle(vnum, capacity, status=VehicleStatus.AVAILABLE):
        v = db_session.query(Vehicle).filter(Vehicle.vehicle_number == vnum).first()
        if not v:
            v = Vehicle(
                organization_id=org1.id,
                branch_id=b_origin.id,
                vehicle_number=vnum,
                vehicle_type=VehicleType.TRUCK,
                model="Tata Prima",
                max_weight_kg=capacity,
                max_volume_cbm=25.0,
                status=status,
                is_active=True,
            )
            db_session.add(v)
            db_session.flush()
        else:
            v.status = status
            db_session.flush()
        return v

    truck = ensure_vehicle("P14TRUCK01", 500.0, VehicleStatus.AVAILABLE)
    small_van = ensure_vehicle("P14VAN01", 8.0, VehicleStatus.AVAILABLE)
    maint_truck = ensure_vehicle("P14MAINT01", 500.0, VehicleStatus.MAINTENANCE)

    db_session.commit()
    return {
        "org1": org1,
        "org2": org2,
        "b_origin": b_origin,
        "b_dest": b_dest,
        "b_other": b_other,
        "b_foreign": b_foreign,
        "org1_admin": org1_admin,
        "bm_origin": bm_origin,
        "bm_dest": bm_dest,
        "driver": driver,
        "other_agent": other_agent,
        "customer": customer,
        "org2_admin": org2_admin,
        "truck": truck,
        "small_van": small_van,
        "maint_truck": maint_truck,
    }


def test_consolidation_bag_and_debag_lifecycle(client, db_session, phase14_env):
    env = phase14_env
    bm_origin_hdr = auth_headers(env["bm_origin"])
    bm_dest_hdr = auth_headers(env["bm_dest"])

    p1 = _make_parcel(db_session, "LF-P14-BAG1", env["b_origin"], env["b_dest"], env["customer"], weight_kg=4.5)
    p2 = _make_parcel(db_session, "LF-P14-BAG2", env["b_origin"], env["b_dest"], env["customer"], weight_kg=3.0)
    p_wrong_route = _make_parcel(db_session, "LF-P14-WRNG", env["b_origin"], env["b_other"], env["customer"], weight_kg=2.0)
    db_session.commit()

    # Same branch rejected (422)
    r_same = client.post(
        "/api/v1/linehaul/bags",
        json={"origin_branch_id": env["b_origin"].id, "dest_branch_id": env["b_origin"].id},
        headers=bm_origin_hdr,
    )
    assert r_same.status_code == 422

    # Dest BM cannot originate a bag at origin branch (403)
    r_wrong_bm = client.post(
        "/api/v1/linehaul/bags",
        json={"origin_branch_id": env["b_origin"].id, "dest_branch_id": env["b_dest"].id},
        headers=bm_dest_hdr,
    )
    assert r_wrong_bm.status_code == 403

    # Create bag at origin
    r_bag = client.post(
        "/api/v1/linehaul/bags",
        json={"origin_branch_id": env["b_origin"].id, "dest_branch_id": env["b_dest"].id, "notes": "Delhi pouch"},
        headers=bm_origin_hdr,
    )
    assert r_bag.status_code == 201, r_bag.text
    bag = r_bag.json()
    assert bag["bag_code"].startswith("BAG-")
    assert bag["status"] == "OPEN"

    # Cannot seal empty bag
    r_seal_empty = client.post(f"/api/v1/linehaul/bags/{bag['id']}/seal", json={}, headers=bm_origin_hdr)
    assert r_seal_empty.status_code == 422

    # Route mismatch rejected
    r_mismatch = client.post(
        f"/api/v1/linehaul/bags/{bag['id']}/parcels",
        json={"parcel_ids": [p_wrong_route.id]},
        headers=bm_origin_hdr,
    )
    assert r_mismatch.status_code == 400

    # Attach parcels p1 & p2
    r_attach = client.post(
        f"/api/v1/linehaul/bags/{bag['id']}/parcels",
        json={"parcel_ids": [p1.id], "tracking_numbers": [p2.tracking_number]},
        headers=bm_origin_hdr,
    )
    assert r_attach.status_code == 200
    assert r_attach.json()["parcel_count"] == 2
    assert r_attach.json()["total_weight_kg"] == pytest.approx(7.5)

    # Second open bag cannot steal p1 (409)
    r_bag2 = client.post(
        "/api/v1/linehaul/bags",
        json={"origin_branch_id": env["b_origin"].id, "dest_branch_id": env["b_dest"].id},
        headers=bm_origin_hdr,
    )
    bag2_id = r_bag2.json()["id"]
    r_steal = client.post(
        f"/api/v1/linehaul/bags/{bag2_id}/parcels",
        json={"parcel_ids": [p1.id]},
        headers=bm_origin_hdr,
    )
    assert r_steal.status_code == 409

    # Remove p2 and verify totals recomputed, then re-attach
    r_rm = client.delete(f"/api/v1/linehaul/bags/{bag['id']}/parcels/{p2.id}", headers=bm_origin_hdr)
    assert r_rm.status_code == 200
    assert r_rm.json()["parcel_count"] == 1
    assert r_rm.json()["total_weight_kg"] == pytest.approx(4.5)

    client.post(
        f"/api/v1/linehaul/bags/{bag['id']}/parcels",
        json={"parcel_ids": [p2.id]},
        headers=bm_origin_hdr,
    )

    # Seal bag
    r_seal = client.post(
        f"/api/v1/linehaul/bags/{bag['id']}/seal",
        json={"seal_number": " seal-001 "},
        headers=bm_origin_hdr,
    )
    assert r_seal.status_code == 200
    assert r_seal.json()["status"] == "SEALED"
    assert r_seal.json()["seal_number"] == "SEAL-001"

    # Cannot add parcel once SEALED
    r_sealed_mod = client.post(
        f"/api/v1/linehaul/bags/{bag['id']}/parcels",
        json={"parcel_ids": [p1.id]},
        headers=bm_origin_hdr,
    )
    assert r_sealed_mod.status_code == 409

    # Debagging blocked while SEALED
    r_debag_early = client.post(f"/api/v1/linehaul/bags/{bag['id']}/debag", json={}, headers=bm_dest_hdr)
    assert r_debag_early.status_code == 409


def test_manifest_end_to_end_dispatch_arrival_reconcile_and_discrepancies(client, db_session, phase14_env):
    env = phase14_env
    bm_origin_hdr = auth_headers(env["bm_origin"])
    bm_dest_hdr = auth_headers(env["bm_dest"])
    driver_hdr = auth_headers(env["driver"])
    org1_hdr = auth_headers(env["org1_admin"])

    p_bagged = _make_parcel(db_session, "LF-P14-M1", env["b_origin"], env["b_dest"], env["customer"], weight_kg=6.0)
    p_damaged = _make_parcel(db_session, "LF-P14-M2", env["b_origin"], env["b_dest"], env["customer"], weight_kg=4.0)
    p_missing = _make_parcel(db_session, "LF-P14-M3", env["b_origin"], env["b_dest"], env["customer"], weight_kg=5.0)
    db_session.commit()

    # Bag p_bagged and seal
    bag_res = client.post(
        "/api/v1/linehaul/bags",
        json={"origin_branch_id": env["b_origin"].id, "dest_branch_id": env["b_dest"].id},
        headers=bm_origin_hdr,
    ).json()
    client.post(
        f"/api/v1/linehaul/bags/{bag_res['id']}/parcels",
        json={"parcel_ids": [p_bagged.id]},
        headers=bm_origin_hdr,
    )
    client.post(f"/api/v1/linehaul/bags/{bag_res['id']}/seal", json={}, headers=bm_origin_hdr)

    # Weight exceeding small_van (8 kg) rejected on manifest create (422)
    r_over = client.post(
        "/api/v1/linehaul/manifests",
        json={
            "origin_branch_id": env["b_origin"].id,
            "dest_branch_id": env["b_dest"].id,
            "vehicle_id": env["small_van"].id,
            "bag_ids": [bag_res["id"]],
            "parcel_ids": [p_damaged.id],
        },
        headers=bm_origin_hdr,
    )
    assert r_over.status_code == 422

    # Maintenance vehicle rejected (409)
    r_maint = client.post(
        "/api/v1/linehaul/manifests",
        json={
            "origin_branch_id": env["b_origin"].id,
            "dest_branch_id": env["b_dest"].id,
            "vehicle_id": env["maint_truck"].id,
            "parcel_ids": [p_damaged.id],
        },
        headers=bm_origin_hdr,
    )
    assert r_maint.status_code == 409

    # Create valid manifest with bag + loose parcels
    r_man = client.post(
        "/api/v1/linehaul/manifests",
        json={
            "origin_branch_id": env["b_origin"].id,
            "dest_branch_id": env["b_dest"].id,
            "vehicle_id": env["truck"].id,
            "driver_id": env["driver"].id,
            "bag_ids": [bag_res["id"]],
            "parcel_ids": [p_damaged.id, p_missing.id],
        },
        headers=bm_origin_hdr,
    )
    assert r_man.status_code == 201, r_man.text
    manifest = r_man.json()
    assert manifest["expected_parcel_count"] == 3
    assert manifest["total_weight_kg"] == pytest.approx(15.0)

    # Cannot double-assign a manifested parcel for last-mile delivery (409)
    r_double_assign = client.post(
        "/api/v1/assignments",
        json={"parcel_id": p_bagged.id, "employee_id": env["driver"].id, "assignment_type": "LAST_MILE"},
        headers=bm_origin_hdr,
    )
    assert r_double_assign.status_code == 409

    # Cannot deactivate branch while active manifest exists (409)
    r_branch_del = client.delete(f"/api/v1/branches/{env['b_dest'].id}", headers=org1_hdr)
    assert r_branch_del.status_code == 409

    # Seal then dispatch manifest
    r_seal = client.post(
        f"/api/v1/linehaul/manifests/{manifest['id']}/seal",
        json={"seal_number": "lh-seal-99"},
        headers=bm_origin_hdr,
    )
    assert r_seal.status_code == 200
    assert r_seal.json()["status"] == "SEALED"

    r_disp = client.post(
        f"/api/v1/linehaul/manifests/{manifest['id']}/dispatch",
        json={"notes": "Departing Mumbai Hub"},
        headers=bm_origin_hdr,
    )
    assert r_disp.status_code == 200, r_disp.text
    disp = r_disp.json()
    assert disp["status"] == "IN_TRANSIT"
    assert disp["seal_number"] == "LH-SEAL-99"

    # Vehicle must be IN_TRANSIT and blocked from maintenance
    db_session.expire_all()
    truck_obj = db_session.query(Vehicle).filter(Vehicle.id == env["truck"].id).first()
    assert truck_obj.status == VehicleStatus.IN_TRANSIT
    r_veh_maint = client.patch(
        f"/api/v1/vehicles/{env['truck'].id}/maintenance",
        json={"is_in_maintenance": True, "notes": "Oil change"},
        headers=org1_hdr,
    )
    assert r_veh_maint.status_code == 409

    # Parcels must be IN_TRANSIT
    for p in (p_bagged, p_damaged, p_missing):
        db_session.refresh(p)
        assert p.delivery_status == ParcelStatus.IN_TRANSIT

    # Cannot cancel IN_TRANSIT manifest
    r_cancel = client.post(
        f"/api/v1/linehaul/manifests/{manifest['id']}/cancel",
        json={"reason": "Abort"},
        headers=bm_origin_hdr,
    )
    assert r_cancel.status_code == 409

    # Unrelated agent cannot mark manifest arrived (404 due to scoped get)
    r_unrel_arrive = client.post(
        f"/api/v1/linehaul/manifests/{manifest['id']}/arrive",
        json={"seal_intact": True},
        headers=auth_headers(env["other_agent"]),
    )
    assert r_unrel_arrive.status_code == 404

    # Assigned driver marks arrival
    r_arrive = client.post(
        f"/api/v1/linehaul/manifests/{manifest['id']}/arrive",
        json={"seal_intact": True, "notes": "Reached Delhi dock"},
        headers=driver_hdr,
    )
    assert r_arrive.status_code == 200, r_arrive.text
    assert r_arrive.json()["status"] == "ARRIVED"

    db_session.refresh(truck_obj)
    assert truck_obj.status == VehicleStatus.AVAILABLE

    # Debag received consolidation bag at destination
    r_debag = client.post(
        f"/api/v1/linehaul/bags/{bag_res['id']}/debag",
        json={"notes": "Cut seal clean"},
        headers=bm_dest_hdr,
    )
    assert r_debag.status_code == 200
    assert r_debag.json()["status"] == "OPENED_AT_DEST"

    # Reconcile at destination: p_bagged received, p_damaged damaged, p_missing omitted -> MISSING, broken seal
    r_rec = client.post(
        f"/api/v1/linehaul/manifests/{manifest['id']}/reconcile",
        json={
            "received_tracking_numbers": [p_bagged.tracking_number],
            "damaged_tracking_numbers": [p_damaged.tracking_number],
            "excess_tracking_numbers": ["LF-UNKNOWN-EXCESS"],
            "seal_intact": False,
            "finalize": True,
            "notes": "Reconciled at Delhi bay 4",
        },
        headers=bm_dest_hdr,
    )
    assert r_rec.status_code == 200, r_rec.text
    rec = r_rec.json()
    assert rec["received_count"] == 1
    assert rec["damaged_count"] == 1
    assert rec["missing_count"] == 1
    assert rec["excess_count"] == 1
    assert rec["discrepancies_created"] == 4
    assert rec["manifest"]["status"] == "RECONCILED"

    db_session.refresh(p_bagged)
    db_session.refresh(p_damaged)
    db_session.refresh(p_missing)
    assert p_bagged.delivery_status == ParcelStatus.AT_DESTINATION_BRANCH
    assert p_damaged.delivery_status == ParcelStatus.ON_HOLD
    assert p_missing.delivery_status == ParcelStatus.ON_HOLD

    # List discrepancies & resolve the missing one releasing parcel to destination
    r_discs = client.get(
        f"/api/v1/linehaul/discrepancies?manifest_id={manifest['id']}",
        headers=bm_dest_hdr,
    )
    assert r_discs.status_code == 200
    discs = r_discs.json()
    assert len(discs) == 4
    missing_disc = next(d for d in discs if d["discrepancy_type"] == "MISSING")

    r_res = client.patch(
        f"/api/v1/linehaul/discrepancies/{missing_disc['id']}",
        json={
            "status": "RESOLVED",
            "resolution_notes": "Located on dock 2",
            "release_parcel_to_dest": True,
        },
        headers=bm_dest_hdr,
    )
    assert r_res.status_code == 200
    assert r_res.json()["status"] == "RESOLVED"
    db_session.refresh(p_missing)
    assert p_missing.delivery_status == ParcelStatus.AT_DESTINATION_BRANCH

    # Cannot reopen RESOLVED discrepancy
    r_reopen = client.patch(
        f"/api/v1/linehaul/discrepancies/{missing_disc['id']}",
        json={"status": "OPEN", "resolution_notes": "Reopening"},
        headers=bm_dest_hdr,
    )
    assert r_reopen.status_code == 409


def test_cancel_manifest_and_concurrency_vehicle_double_dispatch(client, db_session, phase14_env):
    env = phase14_env
    org1_hdr = auth_headers(env["org1_admin"])

    p1 = _make_parcel(db_session, "LF-P14-C1", env["b_origin"], env["b_dest"], env["customer"], weight_kg=5.0)
    p2 = _make_parcel(db_session, "LF-P14-C2", env["b_origin"], env["b_dest"], env["customer"], weight_kg=5.0)
    db_session.commit()

    m1 = client.post(
        "/api/v1/linehaul/manifests",
        json={
            "origin_branch_id": env["b_origin"].id,
            "dest_branch_id": env["b_dest"].id,
            "vehicle_id": env["truck"].id,
            "parcel_ids": [p1.id],
        },
        headers=org1_hdr,
    ).json()

    m2 = client.post(
        "/api/v1/linehaul/manifests",
        json={
            "origin_branch_id": env["b_origin"].id,
            "dest_branch_id": env["b_dest"].id,
            "parcel_ids": [p2.id],
        },
        headers=org1_hdr,
    ).json()

    # Cancel m2 and verify p2 can now be re-manifested on m1
    r_cancel = client.post(
        f"/api/v1/linehaul/manifests/{m2['id']}/cancel",
        json={"reason": "Consolidated onto M1"},
        headers=org1_hdr,
    )
    assert r_cancel.status_code == 200
    assert r_cancel.json()["status"] == "CANCELLED"

    r_add_p2 = client.post(
        f"/api/v1/linehaul/manifests/{m1['id']}/items",
        json={"parcel_ids": [p2.id]},
        headers=org1_hdr,
    )
    assert r_add_p2.status_code == 200
    assert r_add_p2.json()["expected_parcel_count"] == 2

    # Create another DRAFT manifest m3 using same truck before either dispatches; race dispatch!
    p3 = _make_parcel(db_session, "LF-P14-C3", env["b_origin"], env["b_dest"], env["customer"], weight_kg=4.0)
    db_session.commit()
    m3 = client.post(
        "/api/v1/linehaul/manifests",
        json={
            "origin_branch_id": env["b_origin"].id,
            "dest_branch_id": env["b_dest"].id,
            "vehicle_id": env["truck"].id,
            "parcel_ids": [p3.id],
        },
        headers=org1_hdr,
    ).json()

    # Two manifests provisionally referencing the same AVAILABLE truck:
    # first dispatch atomically claims vehicle (200), second hits conflict (409)
    r_disp_1 = client.post(
        f"/api/v1/linehaul/manifests/{m1['id']}/dispatch",
        json={"seal_number": f"RACE-{m1['id']}"},
        headers=org1_hdr,
    )
    r_disp_3 = client.post(
        f"/api/v1/linehaul/manifests/{m3['id']}/dispatch",
        json={"seal_number": f"RACE-{m3['id']}"},
        headers=org1_hdr,
    )
    assert [r_disp_1.status_code, r_disp_3.status_code] == [200, 409]

    # Cleanly mark arriving so shared truck is not left IN_TRANSIT on m1
    r_arr = client.post(
        f"/api/v1/linehaul/manifests/{m1['id']}/arrive",
        json={"seal_intact": True},
        headers=org1_hdr,
    )
    assert r_arr.status_code == 200


def test_linehaul_tenant_isolation_and_rbac_negative(client, db_session, phase14_env):
    env = phase14_env
    bm_origin_hdr = auth_headers(env["bm_origin"])
    org2_hdr = auth_headers(env["org2_admin"])
    cust_hdr = auth_headers(env["customer"])
    driver_hdr = auth_headers(env["driver"])

    p1 = _make_parcel(db_session, "LF-P14-ISO1", env["b_origin"], env["b_dest"], env["customer"])
    iso_truck = Vehicle(
        organization_id=env["org1"].id,
        branch_id=env["b_origin"].id,
        vehicle_number="P14ISOTRUCK",
        vehicle_type=VehicleType.TRUCK,
        model="Tata Prima",
        max_weight_kg=500.0,
        max_volume_cbm=25.0,
        status=VehicleStatus.AVAILABLE,
        is_active=True,
    )
    db_session.add(iso_truck)
    db_session.commit()

    bag = client.post(
        "/api/v1/linehaul/bags",
        json={"origin_branch_id": env["b_origin"].id, "dest_branch_id": env["b_dest"].id},
        headers=bm_origin_hdr,
    ).json()
    manifest_resp = client.post(
        "/api/v1/linehaul/manifests",
        json={
            "origin_branch_id": env["b_origin"].id,
            "dest_branch_id": env["b_dest"].id,
            "vehicle_id": iso_truck.id,
            "parcel_ids": [p1.id],
        },
        headers=bm_origin_hdr,
    )
    assert manifest_resp.status_code == 201, manifest_resp.text
    manifest = manifest_resp.json()
    client.post(
        f"/api/v1/linehaul/manifests/{manifest['id']}/dispatch",
        json={},
        headers=bm_origin_hdr,
    )
    disc = client.post(
        "/api/v1/linehaul/discrepancies",
        json={
            "manifest_id": manifest["id"],
            "parcel_id": p1.id,
            "discrepancy_type": "DAMAGED",
            "description": "Crushed corner during load",
        },
        headers=bm_origin_hdr,
    ).json()

    # Cross-tenant org2 admin gets 404 (no resource existence leak)
    assert client.get(f"/api/v1/linehaul/bags/{bag['id']}", headers=org2_hdr).status_code == 404
    assert client.get(f"/api/v1/linehaul/manifests/{manifest['id']}", headers=org2_hdr).status_code == 404
    assert (
        client.patch(
            f"/api/v1/linehaul/discrepancies/{disc['id']}",
            json={"status": "RESOLVED", "resolution_notes": "Hijack"},
            headers=org2_hdr,
        ).status_code
        == 404
    )
    assert client.get("/api/v1/linehaul/manifests", headers=org2_hdr).json() == []
    assert client.get("/api/v1/linehaul/discrepancies", headers=org2_hdr).json() == []

    # Customer & Delivery Agent forbidden from creating/dispatching manifests/bags
    assert (
        client.post(
            "/api/v1/linehaul/bags",
            json={"origin_branch_id": env["b_origin"].id, "dest_branch_id": env["b_dest"].id},
            headers=cust_hdr,
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/linehaul/manifests",
            json={"origin_branch_id": env["b_origin"].id, "dest_branch_id": env["b_dest"].id},
            headers=driver_hdr,
        ).status_code
        == 403
    )


def test_atomic_dispatch_rollback_on_parcel_state_conflict(client, db_session, phase14_env):
    """If any parcel on a manifest cannot transition during dispatch, the entire batch rolls back cleanly."""
    env = phase14_env
    org1_hdr = auth_headers(env["org1_admin"])

    p_good = _make_parcel(db_session, "LF-P14-RB1", env["b_origin"], env["b_dest"], env["customer"])
    p_stale = _make_parcel(db_session, "LF-P14-RB2", env["b_origin"], env["b_dest"], env["customer"])
    rb_truck = Vehicle(
        organization_id=env["org1"].id,
        branch_id=env["b_origin"].id,
        vehicle_number="P14RBTRUCK",
        vehicle_type=VehicleType.TRUCK,
        model="Tata Prima",
        max_weight_kg=500.0,
        max_volume_cbm=25.0,
        status=VehicleStatus.AVAILABLE,
        is_active=True,
    )
    db_session.add(rb_truck)
    db_session.commit()

    manifest = client.post(
        "/api/v1/linehaul/manifests",
        json={
            "origin_branch_id": env["b_origin"].id,
            "dest_branch_id": env["b_dest"].id,
            "vehicle_id": rb_truck.id,
            "parcel_ids": [p_good.id, p_stale.id],
        },
        headers=org1_hdr,
    ).json()

    # Simulate out-of-band hold applied to second parcel before dispatch runs
    p_stale.delivery_status = ParcelStatus.ON_HOLD
    db_session.commit()

    r_disp = client.post(
        f"/api/v1/linehaul/manifests/{manifest['id']}/dispatch",
        json={"seal_number": "RB-SEAL-1"},
        headers=org1_hdr,
    )
    assert r_disp.status_code == 409

    # Verify rollback: first parcel stayed AT_ORIGIN_BRANCH, vehicle stayed AVAILABLE, manifest stayed DRAFT
    db_session.expire_all()
    p_good_db = db_session.query(Parcel).filter(Parcel.id == p_good.id).first()
    truck_db = db_session.query(Vehicle).filter(Vehicle.id == rb_truck.id).first()
    assert p_good_db.delivery_status == ParcelStatus.AT_ORIGIN_BRANCH
    assert truck_db.status == VehicleStatus.AVAILABLE
    m_get = client.get(f"/api/v1/linehaul/manifests/{manifest['id']}", headers=org1_hdr).json()
    assert m_get["status"] == "DRAFT"


def test_linehaul_listing_filters_and_draft_item_removal(client, db_session, phase14_env):
    """Covers listing filters for manifests/bags and removing loose parcels or detaching sealed bags."""
    env = phase14_env
    bm_origin_hdr = auth_headers(env["bm_origin"])
    driver_hdr = auth_headers(env["driver"])

    p_bag = _make_parcel(db_session, "LF-P14-FLT1", env["b_origin"], env["b_dest"], env["customer"], weight_kg=3.0)
    p_loose = _make_parcel(db_session, "LF-P14-FLT2", env["b_origin"], env["b_dest"], env["customer"], weight_kg=4.0)
    db_session.commit()

    bag = client.post(
        "/api/v1/linehaul/bags",
        json={"origin_branch_id": env["b_origin"].id, "dest_branch_id": env["b_dest"].id},
        headers=bm_origin_hdr,
    ).json()
    client.post(
        f"/api/v1/linehaul/bags/{bag['id']}/parcels",
        json={"parcel_ids": [p_bag.id]},
        headers=bm_origin_hdr,
    )
    client.post(f"/api/v1/linehaul/bags/{bag['id']}/seal", json={}, headers=bm_origin_hdr)

    # Filter bags and inspect single bag
    bags_res = client.get(
        f"/api/v1/linehaul/bags?status=SEALED&origin_branch_id={env['b_origin'].id}&dest_branch_id={env['b_dest'].id}&unassigned_only=true",
        headers=bm_origin_hdr,
    )
    assert bags_res.status_code == 200
    assert any(b["id"] == bag["id"] for b in bags_res.json())
    assert client.get(f"/api/v1/linehaul/bags/{bag['id']}", headers=bm_origin_hdr).status_code == 200

    # Create draft manifest with bag and loose parcel
    m = client.post(
        "/api/v1/linehaul/manifests",
        json={
            "origin_branch_id": env["b_origin"].id,
            "dest_branch_id": env["b_dest"].id,
            "driver_id": env["driver"].id,
            "bag_ids": [bag["id"]],
            "parcel_ids": [p_loose.id],
        },
        headers=bm_origin_hdr,
    ).json()
    assert m["expected_parcel_count"] == 2

    # Driver sees manifest assigned to them; unrelated agent does not
    drv_list = client.get(
        f"/api/v1/linehaul/manifests?status=DRAFT&origin_branch_id={env['b_origin'].id}&dest_branch_id={env['b_dest'].id}",
        headers=driver_hdr,
    )
    assert drv_list.status_code == 200
    assert any(row["id"] == m["id"] for row in drv_list.json())

    # Removing a parcel belonging to a sealed bag directly must fail with 409
    r_bad_rm = client.delete(
        f"/api/v1/linehaul/manifests/{m['id']}/items/parcels/{p_bag.id}",
        headers=bm_origin_hdr,
    )
    assert r_bad_rm.status_code == 409

    # Removing loose parcel and detaching whole sealed bag succeed
    r_rm_loose = client.delete(
        f"/api/v1/linehaul/manifests/{m['id']}/items/parcels/{p_loose.id}",
        headers=bm_origin_hdr,
    )
    assert r_rm_loose.status_code == 200
    assert r_rm_loose.json()["expected_parcel_count"] == 1

    r_detach = client.delete(
        f"/api/v1/linehaul/manifests/{m['id']}/items/bags/{bag['id']}",
        headers=bm_origin_hdr,
    )
    assert r_detach.status_code == 200
    assert r_detach.json()["expected_parcel_count"] == 0
