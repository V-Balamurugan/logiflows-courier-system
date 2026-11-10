import pytest
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from app.core.config import settings
from app.models.user import User
from app.models.organization import Organization
from app.models.branch import Branch
from app.models.parcel import Parcel
from app.models.enums import UserRole, ParcelStatus, OperatingStatus
from app.core.security import create_access_token


def _get_same_org_branch_pair(client, headers):
    branches = client.get(f"{settings.API_V1_STR}/branches", headers=headers).json()
    by_org = defaultdict(list)
    for b in branches:
        by_org[b["organization_id"]].append(b)
    # Find an organization with at least 2 branches
    for org_id, org_branches in by_org.items():
        if len(org_branches) >= 2:
            return org_branches[0]["id"], org_branches[1]["id"]
    raise RuntimeError("No organization with at least 2 branches found in test database")


def test_gps_coordinate_validation_bounds_and_nan(client, orgadmin_headers):
    # Retrieve a parcel with origin and dest in same organization
    b1, b2 = _get_same_org_branch_pair(client, orgadmin_headers)

    booking_payload = {
        "origin_branch_id": b1,
        "dest_branch_id": b2,
        "sender_name": "GPS Sender",
        "sender_phone": "+91 91111 22222",
        "sender_address": "GPS Origin Full Address",
        "sender_city": "Mumbai",
        "sender_state": "Maharashtra",
        "sender_pincode": "400001",
        "receiver_name": "GPS Receiver",
        "receiver_phone": "+91 93333 44444",
        "receiver_address": "GPS Destination Full Address",
        "receiver_city": "Delhi",
        "receiver_state": "Delhi",
        "receiver_pincode": "110001",
        "weight_kg": 2.5,
        "length_cm": 15.0,
        "width_cm": 15.0,
        "height_cm": 10.0,
        "service_type": "STANDARD"
    }
    res = client.post(f"{settings.API_V1_STR}/parcels", json=booking_payload, headers=orgadmin_headers)
    assert res.status_code == 201, res.text
    booking = res.json()
    tracking_no = booking["tracking_number"]

    # 1. Invalid latitude > 90
    bad_lat = {
        "status": "AT_ORIGIN_BRANCH",
        "latitude": 95.5,
        "longitude": 72.87,
        "location_name": "Invalid North"
    }
    r = client.post(f"{settings.API_V1_STR}/tracking/{tracking_no}/update", json=bad_lat, headers=orgadmin_headers)
    assert r.status_code == 422, r.text

    # 2. Invalid latitude < -90
    bad_lat_neg = {
        "status": "AT_ORIGIN_BRANCH",
        "latitude": -91.0,
        "longitude": 72.87,
        "location_name": "Invalid South"
    }
    r = client.post(f"{settings.API_V1_STR}/tracking/{tracking_no}/update", json=bad_lat_neg, headers=orgadmin_headers)
    assert r.status_code == 422, r.text

    # 3. Invalid longitude > 180
    bad_lng = {
        "status": "AT_ORIGIN_BRANCH",
        "latitude": 19.07,
        "longitude": 185.0,
        "location_name": "Invalid East"
    }
    r = client.post(f"{settings.API_V1_STR}/tracking/{tracking_no}/update", json=bad_lng, headers=orgadmin_headers)
    assert r.status_code == 422, r.text

    # 4. Invalid longitude < -180
    bad_lng_neg = {
        "status": "AT_ORIGIN_BRANCH",
        "latitude": 19.07,
        "longitude": -185.0,
        "location_name": "Invalid West"
    }
    r = client.post(f"{settings.API_V1_STR}/tracking/{tracking_no}/update", json=bad_lng_neg, headers=orgadmin_headers)
    assert r.status_code == 422, r.text

    # 5. Custody scan coordinate bounds
    bad_scan = {
        "tracking_number": tracking_no,
        "scan_type": "HUB_ARRIVAL",
        "latitude": 120.0,
        "longitude": 72.87
    }
    r = client.post(f"{settings.API_V1_STR}/custody/scan", json=bad_scan, headers=orgadmin_headers)
    assert r.status_code == 422, r.text

    # 6. Valid coordinates succeed
    good_update = {
        "status": "AT_ORIGIN_BRANCH",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "location_name": "Mumbai Central Hub"
    }
    r = client.post(f"{settings.API_V1_STR}/tracking/{tracking_no}/update", json=good_update, headers=orgadmin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["latitude"] == 19.0760
    assert data["longitude"] == 72.8777


def test_gps_timestamp_future_drift_validation(client, orgadmin_headers):
    b1, b2 = _get_same_org_branch_pair(client, orgadmin_headers)
    booking_payload = {
        "origin_branch_id": b1,
        "dest_branch_id": b2,
        "sender_name": "Timestamp Sender",
        "sender_phone": "+91 91111 22222",
        "sender_address": "Origin Full Address 101",
        "sender_city": "Mumbai",
        "sender_state": "Maharashtra",
        "sender_pincode": "400001",
        "receiver_name": "Timestamp Receiver",
        "receiver_phone": "+91 93333 44444",
        "receiver_address": "Dest Full Address 202",
        "receiver_city": "Delhi",
        "receiver_state": "Delhi",
        "receiver_pincode": "110001",
        "weight_kg": 1.0,
        "length_cm": 10.0,
        "width_cm": 10.0,
        "height_cm": 10.0,
        "service_type": "STANDARD"
    }
    res = client.post(f"{settings.API_V1_STR}/parcels", json=booking_payload, headers=orgadmin_headers)
    assert res.status_code == 201, res.text
    booking = res.json()
    tracking_no = booking["tracking_number"]

    # Timestamp 1 hour in the future should be rejected with 422
    future_time = datetime.now(timezone.utc) + timedelta(hours=1)
    future_payload = {
        "status": "AT_ORIGIN_BRANCH",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "timestamp": future_time.isoformat()
    }
    r = client.post(f"{settings.API_V1_STR}/tracking/{tracking_no}/update", json=future_payload, headers=orgadmin_headers)
    assert r.status_code == 422, r.text


def test_deterministic_latest_location_and_chronology(client, orgadmin_headers):
    b1, b2 = _get_same_org_branch_pair(client, orgadmin_headers)
    booking_payload = {
        "origin_branch_id": b1,
        "dest_branch_id": b2,
        "sender_name": "Timeline Sender",
        "sender_phone": "+91 91111 22222",
        "sender_address": "Origin Road Number 1",
        "sender_city": "Mumbai",
        "sender_state": "MH",
        "sender_pincode": "400001",
        "receiver_name": "Timeline Receiver",
        "receiver_phone": "+91 93333 44444",
        "receiver_address": "Destination Road Number 2",
        "receiver_city": "Delhi",
        "receiver_state": "DL",
        "receiver_pincode": "110001",
        "weight_kg": 1.5,
        "length_cm": 15.0,
        "width_cm": 10.0,
        "height_cm": 10.0,
        "service_type": "STANDARD"
    }
    res = client.post(f"{settings.API_V1_STR}/parcels", json=booking_payload, headers=orgadmin_headers)
    assert res.status_code == 201, res.text
    booking = res.json()
    tracking_no = booking["tracking_number"]

    # 1. Update 1: AT_ORIGIN_BRANCH with coords
    r1 = client.post(
        f"{settings.API_V1_STR}/tracking/{tracking_no}/update",
        json={"status": "AT_ORIGIN_BRANCH", "latitude": 19.0760, "longitude": 72.8777, "location_name": "Checkpoint 1"},
        headers=orgadmin_headers
    )
    assert r1.status_code == 200

    # 2. Update 2: IN_TRANSIT with coords
    r2 = client.post(
        f"{settings.API_V1_STR}/tracking/{tracking_no}/update",
        json={"status": "IN_TRANSIT", "latitude": 23.0225, "longitude": 72.5714, "location_name": "Checkpoint 2 (Ahmedabad Transit)"},
        headers=orgadmin_headers
    )
    assert r2.status_code == 200

    # 3. Update 3: AT_DESTINATION_BRANCH with coords
    r3 = client.post(
        f"{settings.API_V1_STR}/tracking/{tracking_no}/update",
        json={"status": "AT_DESTINATION_BRANCH", "latitude": 28.6139, "longitude": 77.2090, "location_name": "Checkpoint 3 (Delhi Hub)"},
        headers=orgadmin_headers
    )
    assert r3.status_code == 200

    # Query public tracking
    pub = client.get(f"{settings.API_V1_STR}/tracking/public/{tracking_no}").json()

    # Milestones must be chronological
    statuses = [m["status"] for m in pub["milestones"]]
    assert statuses == ["BOOKED", "AT_ORIGIN_BRANCH", "IN_TRANSIT", "AT_DESTINATION_BRANCH"]

    # Latest location must exactly match Checkpoint 3 (latest by created_at DESC, id DESC)
    assert pub["current_lat"] == 28.6139
    assert pub["current_lng"] == 77.2090
    assert pub["current_location"] == "Checkpoint 3 (Delhi Hub)"


def test_public_tracking_redaction_zero_pii(client, customer_headers):
    b1, b2 = _get_same_org_branch_pair(client, customer_headers)

    secret_phone = "+91 99999 88888"
    secret_address = "Secret Flat 402, Private Residency, Confidential Road"
    booking_payload = {
        "origin_branch_id": b1,
        "dest_branch_id": b2,
        "sender_name": "Sensitive Sender",
        "sender_phone": secret_phone,
        "sender_address": secret_address,
        "sender_city": "Mumbai",
        "sender_state": "MH",
        "sender_pincode": "400001",
        "receiver_name": "Sensitive Receiver",
        "receiver_phone": "+91 77777 66666",
        "receiver_address": "Private Receiver Street",
        "receiver_city": "Delhi",
        "receiver_state": "DL",
        "receiver_pincode": "110001",
        "weight_kg": 3.0,
        "length_cm": 20.0,
        "width_cm": 20.0,
        "height_cm": 15.0,
        "service_type": "STANDARD"
    }
    res = client.post(f"{settings.API_V1_STR}/parcels", json=booking_payload, headers=customer_headers)
    assert res.status_code == 201, res.text
    booking = res.json()
    tracking_no = booking["tracking_number"]

    # Fetch public tracking
    pub_resp = client.get(f"{settings.API_V1_STR}/tracking/public/{tracking_no}")
    assert pub_resp.status_code == 200
    pub_data = pub_resp.json()

    # Verify complete PII redaction
    assert "sender_phone" not in pub_data
    assert "sender_address" not in pub_data
    assert "receiver_phone" not in pub_data
    assert "receiver_address" not in pub_data
    assert "customer_id" not in pub_data
    assert "sender_email" not in pub_data

    # Verify string search on raw response body
    raw_text = pub_resp.text
    assert secret_phone not in raw_text
    assert "Confidential Road" not in raw_text

    # Verify safe fields are present
    assert pub_data["tracking_number"] == tracking_no
    assert pub_data["status"] == "BOOKED"
    assert pub_data["origin_city"] == "Mumbai"
    assert pub_data["destination_city"] == "Delhi"

    # Non-existent tracking number returns uniform 404
    missing_resp = client.get(f"{settings.API_V1_STR}/tracking/public/NON_EXISTENT_TRACK_123")
    assert missing_resp.status_code == 404
    assert missing_resp.json()["detail"] == "Shipment tracking number not found"


def test_authenticated_tracking_authorization_and_tenant_isolation(client, db_session, customer_headers, orgadmin_headers, superadmin_headers):
    # Customer 1 books a parcel in Org Admin's organization
    b1, b2 = _get_same_org_branch_pair(client, orgadmin_headers)
    booking_payload = {
        "origin_branch_id": b1,
        "dest_branch_id": b2,
        "sender_name": "Auth Sender",
        "sender_phone": "+91 91111 22222",
        "sender_address": "Auth Address Here",
        "sender_city": "Mumbai",
        "sender_state": "MH",
        "sender_pincode": "400001",
        "receiver_name": "Auth Receiver",
        "receiver_phone": "+91 93333 44444",
        "receiver_address": "Auth Address There",
        "receiver_city": "Delhi",
        "receiver_state": "DL",
        "receiver_pincode": "110001",
        "weight_kg": 1.0,
        "length_cm": 10.0,
        "width_cm": 10.0,
        "height_cm": 10.0,
        "service_type": "STANDARD"
    }
    res = client.post(f"{settings.API_V1_STR}/parcels", json=booking_payload, headers=customer_headers)
    assert res.status_code == 201, res.text
    booking = res.json()
    tracking_no = booking["tracking_number"]

    # 1. Owner customer can view full details
    r_cust1 = client.get(f"{settings.API_V1_STR}/tracking/{tracking_no}", headers=customer_headers)
    assert r_cust1.status_code == 200
    assert r_cust1.json()["sender_phone"] == "+91 91111 22222"

    # 2. Create another customer (Customer 2)
    cust2 = db_session.query(User).filter(User.email == "other.customer@example.com").first()
    if not cust2:
        cust2 = User(
            email="other.customer@example.com",
            hashed_password="hash",
            full_name="Other Customer",
            phone="+91 99999 00000",
            role=UserRole.CUSTOMER,
            is_active=True
        )
        db_session.add(cust2)
        db_session.commit()
        db_session.refresh(cust2)
    cust2_token = create_access_token(subject=cust2.id, role=UserRole.CUSTOMER.value)
    cust2_headers = {"Authorization": f"Bearer {cust2_token}"}

    # Customer 2 attempting to view Customer 1's detailed tracking gets 404 (anti-enumeration)
    r_cust2 = client.get(f"{settings.API_V1_STR}/tracking/{tracking_no}", headers=cust2_headers)
    assert r_cust2.status_code == 404

    # 3. Super Admin can view full details
    r_super = client.get(f"{settings.API_V1_STR}/tracking/{tracking_no}", headers=superadmin_headers)
    assert r_super.status_code == 200

    # 4. Org Admin within same organization can view full details
    r_org = client.get(f"{settings.API_V1_STR}/tracking/{tracking_no}", headers=orgadmin_headers)
    assert r_org.status_code == 200

    # 5. Staff from a different organization gets 404
    other_org = db_session.query(Organization).filter(Organization.code == "ALIEN-LOG").first()
    if not other_org:
        other_org = Organization(
            name="Alien Logistics Ltd",
            code="ALIEN-LOG",
            contact_email="alien@example.com",
            contact_phone="+91 00000 11111",
            address="Alien Corp",
            is_active=True
        )
        db_session.add(other_org)
        db_session.commit()
        db_session.refresh(other_org)

    alien_staff = db_session.query(User).filter(User.email == "staff@alien.com").first()
    if not alien_staff:
        alien_staff = User(
            email="staff@alien.com",
            hashed_password="hash",
            full_name="Alien Staff",
            phone="+91 00000 22222",
            role=UserRole.ORG_ADMIN,
            organization_id=other_org.id,
            is_active=True
        )
        db_session.add(alien_staff)
        db_session.commit()
        db_session.refresh(alien_staff)
    alien_token = create_access_token(subject=alien_staff.id, role=UserRole.ORG_ADMIN.value)
    alien_headers = {"Authorization": f"Bearer {alien_token}"}

    r_alien = client.get(f"{settings.API_V1_STR}/tracking/{tracking_no}", headers=alien_headers)
    assert r_alien.status_code == 404
