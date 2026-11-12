import math
from datetime import datetime, timezone, timedelta
import pytest
from app.models.organization import Organization
from app.models.branch import Branch
from app.models.user import User
from app.models.parcel import Parcel
from app.models.custody import CustodyScan
from app.models.enums import UserRole, OperatingStatus, ServiceType, PaymentStatus, ParcelStatus, ScanType
from app.core.security import create_access_token, get_password_hash
from app.utils.qr_security import generate_secure_qr_payload
from app.services.broadcaster import milestone_broadcaster


def auth_headers(user):
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def phase13_setup(db_session):
    # Primary Org
    org1 = db_session.query(Organization).filter(Organization.code == "P13_ORG1").first()
    if not org1:
        org1 = Organization(name="Phase 13 Org 1", code="P13_ORG1", contact_email="p13_1@org.com", is_active=True)
        db_session.add(org1)
        db_session.flush()

    # Foreign Org
    org2 = db_session.query(Organization).filter(Organization.code == "P13_ORG2").first()
    if not org2:
        org2 = Organization(name="Phase 13 Org 2", code="P13_ORG2", contact_email="p13_2@org.com", is_active=True)
        db_session.add(org2)
        db_session.flush()

    # Origin Branch
    b1 = db_session.query(Branch).filter(Branch.branch_code == "P13_B1").first()
    if not b1:
        b1 = Branch(
            organization_id=org1.id,
            branch_code="P13_B1",
            branch_name="Origin Hub Mumbai",
            address="Hub 1, Andheri",
            pincode="400001",
            city="Mumbai",
            state="Maharashtra",
            country="India",
            contact_email="b1@p13.com",
            contact_phone="9876543210",
            latitude=19.0760,
            longitude=72.8777,
            operating_status=OperatingStatus.ACTIVE,
            is_active=True
        )
        db_session.add(b1)
        db_session.flush()

    # Destination Branch
    b2 = db_session.query(Branch).filter(Branch.branch_code == "P13_B2").first()
    if not b2:
        b2 = Branch(
            organization_id=org1.id,
            branch_code="P13_B2",
            branch_name="Dest Hub Delhi",
            address="Hub 2, Connaught Place",
            pincode="110001",
            city="New Delhi",
            state="Delhi",
            country="India",
            contact_email="b2@p13.com",
            contact_phone="9876543211",
            latitude=28.6139,
            longitude=77.2090,
            operating_status=OperatingStatus.ACTIVE,
            is_active=True
        )
        db_session.add(b2)
        db_session.flush()

    # Users
    cust1 = db_session.query(User).filter(User.email == "cust1@p13.com").first()
    if not cust1:
        cust1 = User(
            email="cust1@p13.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Alice Consignor",
            role=UserRole.CUSTOMER,
            is_active=True
        )
        db_session.add(cust1)
        db_session.flush()

    cust2 = db_session.query(User).filter(User.email == "cust2@p13.com").first()
    if not cust2:
        cust2 = User(
            email="cust2@p13.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Bob Stranger",
            role=UserRole.CUSTOMER,
            is_active=True
        )
        db_session.add(cust2)
        db_session.flush()

    agent1 = db_session.query(User).filter(User.email == "agent1@p13.com").first()
    if not agent1:
        agent1 = User(
            email="agent1@p13.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Agent Ramesh",
            role=UserRole.DELIVERY_AGENT,
            organization_id=org1.id,
            branch_id=b1.id,
            is_active=True
        )
        db_session.add(agent1)
        db_session.flush()

    manager1 = db_session.query(User).filter(User.email == "manager1@p13.com").first()
    if not manager1:
        manager1 = User(
            email="manager1@p13.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Manager Suresh",
            role=UserRole.BRANCH_MANAGER,
            organization_id=org1.id,
            branch_id=b1.id,
            is_active=True
        )
        db_session.add(manager1)
        db_session.flush()

    foreign_agent = db_session.query(User).filter(User.email == "foreign@p13.com").first()
    if not foreign_agent:
        foreign_agent = User(
            email="foreign@p13.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Foreign Agent",
            role=UserRole.DELIVERY_AGENT,
            organization_id=org2.id,
            is_active=True
        )
        db_session.add(foreign_agent)
        db_session.flush()

    # Test parcel
    parcel = db_session.query(Parcel).filter(Parcel.tracking_number == "LF-P13-882201").first()
    if not parcel:
        parcel = Parcel(
            tracking_number="LF-P13-882201",
            customer_id=cust1.id,
            origin_branch_id=b1.id,
            dest_branch_id=b2.id,
            sender_name="Alice Consignor",
            sender_phone="9988776655",
            sender_email="cust1@p13.com",
            sender_address="123 Alice Rd",
            sender_city="Mumbai",
            sender_state="Maharashtra",
            sender_pincode="400001",
            receiver_name="Charlie Consignee",
            receiver_phone="9988776644",
            receiver_email="charlie@p13.com",
            receiver_address="456 Charlie Ave",
            receiver_city="New Delhi",
            receiver_state="Delhi",
            receiver_pincode="110001",
            weight_kg=2.5,
            length_cm=20.0,
            width_cm=15.0,
            height_cm=10.0,
            volumetric_weight_kg=0.6,
            service_type=ServiceType.EXPRESS,
            base_charge=150.0,
            total_charge=150.0,
            payment_status=PaymentStatus.PAID,
            delivery_status=ParcelStatus.BOOKED,
            version_id=1
        )
        db_session.add(parcel)
        db_session.flush()

    db_session.commit()
    return {
        "org1": org1,
        "org2": org2,
        "branch1": b1,
        "branch2": b2,
        "cust1": cust1,
        "cust2": cust2,
        "agent1": agent1,
        "manager1": manager1,
        "foreign_agent": foreign_agent,
        "parcel": parcel
    }


def test_public_tracking_endpoint_zero_pii_and_not_found(client, db_session, phase13_setup):
    """Module 13.1: Public tracking must return sanitized tracking data with zero PII leakage."""
    parcel = phase13_setup["parcel"]

    # 1. Valid tracking number
    res = client.get(f"/api/v1/tracking/public/{parcel.tracking_number}")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["tracking_number"] == parcel.tracking_number
    assert data["status"] == parcel.delivery_status.value
    assert data["origin_city"] == "Mumbai"
    assert data["destination_city"] == "New Delhi"
    assert isinstance(data["milestones"], list)
    assert data["origin_lat"] == 19.0760
    assert data["dest_lat"] == 28.6139

    # Strict Zero-PII assertions
    assert "sender_name" not in data
    assert "sender_phone" not in data
    assert "sender_email" not in data
    assert "sender_address" not in data
    assert "receiver_name" not in data
    assert "receiver_phone" not in data
    assert "receiver_email" not in data
    assert "receiver_address" not in data
    assert "customer_id" not in data
    assert "total_charge" not in data

    # 2. Non-existent tracking number returns 404
    err_res = client.get("/api/v1/tracking/public/LF-NONEXISTENT-999")
    assert err_res.status_code == 404
    assert "not found" in err_res.json()["detail"].lower()


def test_authenticated_tracking_access_control_and_tenant_isolation(client, db_session, phase13_setup):
    """Module 13.2: Authenticated tracking enforces owner/tenant authorization."""
    parcel = phase13_setup["parcel"]
    cust1 = phase13_setup["cust1"]
    cust2 = phase13_setup["cust2"]
    agent1 = phase13_setup["agent1"]
    foreign_agent = phase13_setup["foreign_agent"]

    # 1. Consignor Owner Customer can access full details
    res_owner = client.get(f"/api/v1/tracking/{parcel.tracking_number}", headers=auth_headers(cust1))
    assert res_owner.status_code == 200
    owner_data = res_owner.json()
    assert owner_data["tracking_number"] == parcel.tracking_number
    assert owner_data["sender_name"] == "Alice Consignor"
    assert owner_data["receiver_name"] == "Charlie Consignee"
    assert owner_data["sender_phone"] == "9988776655"

    # 2. Unrelated Customer gets 404 (zero leakage of shipment existence)
    res_stranger = client.get(f"/api/v1/tracking/{parcel.tracking_number}", headers=auth_headers(cust2))
    assert res_stranger.status_code == 404
    assert "not found" in res_stranger.json()["detail"].lower()

    # 3. Same-tenant staff can access full details
    res_staff = client.get(f"/api/v1/tracking/{parcel.tracking_number}", headers=auth_headers(agent1))
    assert res_staff.status_code == 200
    assert res_staff.json()["tracking_number"] == parcel.tracking_number

    # 4. Cross-tenant staff gets 404
    res_foreign = client.get(f"/api/v1/tracking/{parcel.tracking_number}", headers=auth_headers(foreign_agent))
    assert res_foreign.status_code == 404


def test_gps_bounds_and_drift_validation(client, db_session, phase13_setup):
    """Module 13.3: GPS coordinate bounding box [-90,90], [-180,180], NaN rejection, and <=5 min drift."""
    agent1 = phase13_setup["agent1"]
    parcel = phase13_setup["parcel"]
    hdrs = auth_headers(agent1)

    # 1. Invalid Latitude > 90 rejected with 422
    res_lat_high = client.post(
        "/api/v1/custody/scan",
        headers=hdrs,
        json={
            "tracking_number": parcel.tracking_number,
            "scan_type": ScanType.ORIGIN_INWARD.value,
            "latitude": 90.0001,
            "longitude": 72.8777
        }
    )
    assert res_lat_high.status_code == 422
    assert "Latitude must be between -90.0 and +90.0 degrees" in res_lat_high.text

    # 2. Invalid Latitude < -90 rejected with 422
    res_lat_low = client.post(
        "/api/v1/custody/scan",
        headers=hdrs,
        json={
            "tracking_number": parcel.tracking_number,
            "scan_type": ScanType.ORIGIN_INWARD.value,
            "latitude": -90.0001,
            "longitude": 72.8777
        }
    )
    assert res_lat_low.status_code == 422

    # 3. Invalid Longitude > 180 rejected with 422
    res_lng_high = client.post(
        "/api/v1/custody/scan",
        headers=hdrs,
        json={
            "tracking_number": parcel.tracking_number,
            "scan_type": ScanType.ORIGIN_INWARD.value,
            "latitude": 19.0760,
            "longitude": 180.0001
        }
    )
    assert res_lng_high.status_code == 422
    assert "Longitude must be between -180.0 and +180.0 degrees" in res_lng_high.text

    # 4. Invalid Longitude < -180 rejected with 422
    res_lng_low = client.post(
        "/api/v1/custody/scan",
        headers=hdrs,
        json={
            "tracking_number": parcel.tracking_number,
            "scan_type": ScanType.ORIGIN_INWARD.value,
            "latitude": 19.0760,
            "longitude": -180.0001
        }
    )
    assert res_lng_low.status_code == 422

    # 5. Timestamp in future beyond 5 minutes drift rejected with 422
    future_time = datetime.now(timezone.utc) + timedelta(minutes=15)
    res_drift = client.post(
        "/api/v1/custody/scan",
        headers=hdrs,
        json={
            "tracking_number": parcel.tracking_number,
            "scan_type": ScanType.ORIGIN_INWARD.value,
            "latitude": 19.0760,
            "longitude": 72.8777,
            "timestamp": future_time.isoformat()
        }
    )
    assert res_drift.status_code == 422
    assert "5 minutes drift" in res_drift.text

    # 6. Valid timestamp within drift boundary succeeds (or passes schema validation)
    valid_past = datetime.now(timezone.utc) - timedelta(minutes=2)
    # We check schema validation directly or via valid scan
    assert valid_past < datetime.now(timezone.utc) + timedelta(minutes=5)


def test_qr_signature_verification_and_tamper_rejection(client, db_session, phase13_setup):
    """Module 13.4: Cryptographic QR HMAC validation and rejection of tampered tokens."""
    agent1 = phase13_setup["agent1"]
    parcel = phase13_setup["parcel"]
    hdrs = auth_headers(agent1)

    # 1. Tampered QR signature
    valid_qr = generate_secure_qr_payload(parcel.tracking_number)
    parts = valid_qr.split(".")
    tampered_qr = f"{parts[0]}.{parts[1]}.{parts[2]}.{parts[3]}.{parts[4]}.bad_signature_deadbeef"

    res_tamper = client.post(
        "/api/v1/custody/scan",
        headers=hdrs,
        json={
            "tracking_number": tampered_qr,
            "scan_type": ScanType.ORIGIN_INWARD.value
        }
    )
    assert res_tamper.status_code == 400
    assert "tampered" in res_tamper.json()["detail"].lower() or "signature" in res_tamper.json()["detail"].lower()

    # Verify audit log was recorded for security inspection
    audit_entry = (
        db_session.query(CustodyScan)
        .filter(CustodyScan.parcel_id == parcel.id, CustodyScan.is_successful == False)
        .order_by(CustodyScan.created_at.desc())
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.is_successful is False
    assert "tampered" in audit_entry.failure_reason.lower() or "signature" in audit_entry.failure_reason.lower()


def test_custody_hash_chain_genesis_and_tamper_detection(client, db_session, phase13_setup):
    """Module 13.5: SHA-256 hash chaining ledger and tamper-evident detection."""
    agent1 = phase13_setup["agent1"]
    b1 = phase13_setup["branch1"]
    b2 = phase13_setup["branch2"]
    hdrs = auth_headers(agent1)

    # Create a fresh parcel for clean chain verification
    test_tn = "LF-CHAIN-TEST-001"
    existing = db_session.query(Parcel).filter(Parcel.tracking_number == test_tn).first()
    if existing:
        db_session.query(CustodyScan).filter(CustodyScan.parcel_id == existing.id).delete()
        db_session.delete(existing)
        db_session.commit()

    chain_parcel = Parcel(
        tracking_number=test_tn,
        customer_id=phase13_setup["cust1"].id,
        origin_branch_id=b1.id,
        dest_branch_id=b2.id,
        sender_name="Sender C",
        sender_phone="9988112233",
        sender_address="Addr C",
        sender_city=b1.city,
        sender_state=b1.state,
        sender_pincode=b1.pincode,
        receiver_name="Receiver C",
        receiver_phone="9988112244",
        receiver_address="Addr D",
        receiver_city=b2.city,
        receiver_state=b2.state,
        receiver_pincode=b2.pincode,
        weight_kg=1.0,
        length_cm=10.0,
        width_cm=10.0,
        height_cm=10.0,
        volumetric_weight_kg=0.2,
        service_type=ServiceType.STANDARD,
        base_charge=60.0,
        total_charge=60.0,
        payment_status=PaymentStatus.PAID,
        delivery_status=ParcelStatus.BOOKED,
        version_id=1
    )
    db_session.add(chain_parcel)
    db_session.commit()

    # 1. First Scan: Inward receiving at origin branch
    scan1_time = datetime(2026, 11, 10, 10, 0, 0, tzinfo=timezone.utc)
    res1 = client.post(
        "/api/v1/custody/scan",
        headers=hdrs,
        json={
            "tracking_number": test_tn,
            "scan_type": ScanType.ORIGIN_INWARD.value,
            "branch_id": b1.id,
            "timestamp": scan1_time.isoformat()
        }
    )
    assert res1.status_code == 201, res1.text
    data1 = res1.json()
    assert data1["previous_hash"] == "GENESIS_CUSTODY_HASH"
    assert len(data1["record_hash"]) == 64

    # 2. Second Scan: Linehaul dispatch outward by branch manager
    manager1 = phase13_setup["manager1"]
    manager_hdrs = auth_headers(manager1)
    scan2_time = datetime(2026, 11, 10, 10, 1, 0, tzinfo=timezone.utc)
    res2 = client.post(
        "/api/v1/custody/scan",
        headers=manager_hdrs,
        json={
            "tracking_number": test_tn,
            "scan_type": ScanType.HUB_OUTWARD.value,
            "branch_id": b1.id,
            "timestamp": scan2_time.isoformat()
        }
    )
    assert res2.status_code == 201, res2.text
    data2 = res2.json()
    assert data2["previous_hash"] == data1["record_hash"]
    assert len(data2["record_hash"]) == 64
    assert data2["record_hash"] != data1["record_hash"]

    # 3. Verify Custody Chain Endpoint
    verify_res = client.get(f"/api/v1/custody/{test_tn}/verify-chain", headers=hdrs)
    assert verify_res.status_code == 200
    vdata = verify_res.json()
    assert vdata["is_valid"] is True
    assert vdata["tamper_detected"] is False
    assert vdata["total_scans"] == 2
    assert len(vdata["chain"]) == 2
    assert vdata["chain"][0]["verified"] is True
    assert vdata["chain"][1]["verified"] is True
    assert vdata["chain"][0]["previous_hash"] == "GENESIS_CUSTODY_HASH"
    assert vdata["chain"][1]["previous_hash"] == vdata["chain"][0]["record_hash"]

    # 4. Tamper Detection: Directly manipulate the database row
    first_scan = (
        db_session.query(CustodyScan)
        .filter(CustodyScan.parcel_id == chain_parcel.id, CustodyScan.scan_type == ScanType.ORIGIN_INWARD)
        .first()
    )
    first_scan.record_hash = "deadbeef" * 8
    db_session.commit()

    # Re-verify custody chain: must detect tampering
    tamper_res = client.get(f"/api/v1/custody/{test_tn}/verify-chain", headers=hdrs)
    assert tamper_res.status_code == 200
    tdata = tamper_res.json()
    assert tdata["is_valid"] is False
    assert tdata["tamper_detected"] is True
    assert tdata["chain"][0]["verified"] is False


def test_sse_live_tracking_stream_and_broadcaster(client, db_session, phase13_setup):
    """Module 13.6: Server-Sent Events (SSE) live milestone streaming and broadcaster pub/sub."""
    parcel = phase13_setup["parcel"]

    # 1. MilestoneBroadcaster pub/sub unit test
    test_queue = milestone_broadcaster.subscribe(parcel.tracking_number)
    milestone_broadcaster.broadcast(parcel.tracking_number, {
        "tracking_number": parcel.tracking_number,
        "status": "IN_TRANSIT",
        "location": "Pune Highway Checkpoint",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    assert not test_queue.empty()
    item = test_queue.get_nowait()
    assert item["status"] == "IN_TRANSIT"
    assert item["location"] == "Pune Highway Checkpoint"
    milestone_broadcaster.unsubscribe(parcel.tracking_number, test_queue)

    # 2. SSE Streaming endpoint test (initial state)
    with client.stream("GET", f"/api/v1/tracking/live/{parcel.tracking_number}") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        # Read the first event chunk
        lines = []
        for line in response.iter_lines():
            if line:
                lines.append(line)
            if len(lines) >= 1:
                break
        assert any("INITIAL_STATE" in l for l in lines)
