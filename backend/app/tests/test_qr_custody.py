import pytest
from app.models.organization import Organization
from app.models.branch import Branch
from app.models.user import User
from app.models.parcel import Parcel
from app.models.custody import CustodyScan
from app.models.enums import UserRole, OperatingStatus, ServiceType, PaymentStatus, ParcelStatus, ScanType
from app.core.security import create_access_token, get_password_hash
from app.utils.qr_security import generate_secure_qr_payload


def auth_headers(user):
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def qr_test_setup(db_session):
    # Org 1
    org1 = db_session.query(Organization).filter(Organization.code == "QR_ORG1").first()
    if not org1:
        org1 = Organization(name="QR Org 1", code="QR_ORG1", contact_email="q1@org.com", is_active=True)
        db_session.add(org1)
        db_session.flush()

    # Org 2
    org2 = db_session.query(Organization).filter(Organization.code == "QR_ORG2").first()
    if not org2:
        org2 = Organization(name="QR Org 2", code="QR_ORG2", contact_email="q2@org.com", is_active=True)
        db_session.add(org2)
        db_session.flush()

    # Branches
    b1 = db_session.query(Branch).filter(Branch.branch_code == "QR_B1").first()
    if not b1:
        b1 = Branch(
            organization_id=org1.id,
            branch_code="QR_B1",
            branch_name="Branch QR 1",
            address="Addr QR1",
            pincode="110001",
            city="City QR1",
            state="State QR1",
            country="India",
            contact_email="b1@qr.com",
            contact_phone="9876543201",
            operating_status=OperatingStatus.ACTIVE,
            is_active=True
        )
        db_session.add(b1)
        db_session.flush()

    b2 = db_session.query(Branch).filter(Branch.branch_code == "QR_B2").first()
    if not b2:
        b2 = Branch(
            organization_id=org2.id,
            branch_code="QR_B2",
            branch_name="Branch QR 2",
            address="Addr QR2",
            pincode="110002",
            city="City QR2",
            state="State QR2",
            country="India",
            contact_email="b2@qr.com",
            contact_phone="9876543202",
            operating_status=OperatingStatus.ACTIVE,
            is_active=True
        )
        db_session.add(b2)
        db_session.flush()

    # Users
    agent1 = db_session.query(User).filter(User.email == "agent1@qr.com").first()
    if not agent1:
        agent1 = User(
            email="agent1@qr.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Agent QR 1",
            role=UserRole.DELIVERY_AGENT,
            organization_id=org1.id,
            branch_id=b1.id,
            is_active=True
        )
        db_session.add(agent1)
        db_session.flush()

    agent2 = db_session.query(User).filter(User.email == "agent2@qr.com").first()
    if not agent2:
        agent2 = User(
            email="agent2@qr.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Agent QR 2",
            role=UserRole.DELIVERY_AGENT,
            organization_id=org2.id,
            branch_id=b2.id,
            is_active=True
        )
        db_session.add(agent2)
        db_session.flush()

    # Parcel in Org 1
    parcel = db_session.query(Parcel).filter(Parcel.tracking_number == "LF-QR-TEST-001").first()
    if not parcel:
        parcel = Parcel(
            tracking_number="LF-QR-TEST-001",
            origin_branch_id=b1.id,
            dest_branch_id=b1.id,
            sender_name="Sender QR",
            sender_phone="9988112233",
            sender_address="Addr 1",
            sender_city=b1.city,
            sender_state=b1.state,
            sender_pincode=b1.pincode,
            receiver_name="Receiver QR",
            receiver_phone="9988112234",
            receiver_address="Addr 2",
            receiver_city=b1.city,
            receiver_state=b1.state,
            receiver_pincode=b1.pincode,
            weight_kg=1.0,
            length_cm=10.0,
            width_cm=10.0,
            height_cm=10.0,
            volumetric_weight_kg=0.2,
            service_type=ServiceType.STANDARD,
            base_charge=50.0,
            total_charge=50.0,
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
        "agent1": agent1,
        "agent2": agent2,
        "parcel": parcel
    }


def test_valid_signed_qr_payload_scan_succeeds(client, db_session, qr_test_setup):
    """AC5: Valid signed QR payload successfully verifies and updates custody."""
    parcel = qr_test_setup["parcel"]
    agent1 = qr_test_setup["agent1"]
    hdrs = auth_headers(agent1)

    qr_payload = generate_secure_qr_payload(parcel.tracking_number)
    assert qr_payload.startswith(f"LFQR.{parcel.tracking_number}.")

    res = client.post(
        "/api/v1/custody/scan",
        json={
            "tracking_number": qr_payload,
            "scan_type": ScanType.ORIGIN_INWARD.value,
            "branch_id": qr_test_setup["branch1"].id,
            "notes": "Inward scan test"
        },
        headers=hdrs
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["tracking_number"] == parcel.tracking_number
    assert data["new_parcel_status"] == ParcelStatus.AT_ORIGIN_BRANCH.value

    # Verify audit record in custody_scans
    scan = db_session.query(CustodyScan).filter(
        CustodyScan.parcel_id == parcel.id,
        CustodyScan.scan_type == ScanType.ORIGIN_INWARD
    ).order_by(CustodyScan.id.desc()).first()
    assert scan is not None
    assert scan.is_successful is True
    assert scan.failure_reason is None


def test_tampered_qr_signature_fails_and_audited(client, db_session, qr_test_setup):
    """AC5: Tampered QR signature is rejected with 400 and logged in custody_scans."""
    parcel = qr_test_setup["parcel"]
    agent1 = qr_test_setup["agent1"]
    hdrs = auth_headers(agent1)

    valid_payload = generate_secure_qr_payload(parcel.tracking_number)
    # Tamper the last 4 characters of the HMAC signature
    tampered_payload = valid_payload[:-4] + "ffff"

    res = client.post(
        "/api/v1/custody/scan",
        json={
            "tracking_number": tampered_payload,
            "scan_type": ScanType.ORIGIN_INWARD.value,
            "branch_id": qr_test_setup["branch1"].id
        },
        headers=hdrs
    )
    assert res.status_code == 400
    assert "tampering" in res.json()["detail"].lower()

    # Verify failed scan audit record
    failed_scan = db_session.query(CustodyScan).filter(
        CustodyScan.scanned_by_id == agent1.id,
        CustodyScan.is_successful == False
    ).order_by(CustodyScan.id.desc()).first()
    assert failed_scan is not None
    assert "tampering" in failed_scan.failure_reason.lower()


def test_expired_qr_code_fails_and_audited(client, db_session, qr_test_setup):
    """AC5: Expired QR code is rejected with 400 and logged in custody_scans."""
    parcel = qr_test_setup["parcel"]
    agent1 = qr_test_setup["agent1"]
    hdrs = auth_headers(agent1)

    # Generate payload expired in the past
    expired_payload = generate_secure_qr_payload(parcel.tracking_number, expires_in_days=-1)

    res = client.post(
        "/api/v1/custody/scan",
        json={
            "tracking_number": expired_payload,
            "scan_type": ScanType.ORIGIN_INWARD.value,
            "branch_id": qr_test_setup["branch1"].id
        },
        headers=hdrs
    )
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()

    # Verify failed scan audit record
    failed_scan = db_session.query(CustodyScan).filter(
        CustodyScan.scanned_by_id == agent1.id,
        CustodyScan.is_successful == False
    ).order_by(CustodyScan.id.desc()).first()
    assert failed_scan is not None
    assert "expired" in failed_scan.failure_reason.lower()


def test_cross_tenant_qr_scan_rejected_and_audited(client, db_session, qr_test_setup):
    """AC5: Scanning a parcel from another organization returns 404 anti-leakage and logs failed audit."""
    parcel = qr_test_setup["parcel"]
    agent2 = qr_test_setup["agent2"]  # Org 2 agent attempting to scan Org 1 parcel
    hdrs = auth_headers(agent2)

    valid_payload = generate_secure_qr_payload(parcel.tracking_number)

    res = client.post(
        "/api/v1/custody/scan",
        json={
            "tracking_number": valid_payload,
            "scan_type": ScanType.ORIGIN_INWARD.value,
            "branch_id": qr_test_setup["branch2"].id
        },
        headers=hdrs
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Parcel not found"

    # Verify failed scan audit record with cross-tenant failure reason
    failed_scan = db_session.query(CustodyScan).filter(
        CustodyScan.scanned_by_id == agent2.id,
        CustodyScan.parcel_id == parcel.id,
        CustodyScan.is_successful == False
    ).order_by(CustodyScan.id.desc()).first()
    assert failed_scan is not None
    assert "cross-tenant" in failed_scan.failure_reason.lower()


def test_invalid_state_transition_via_scan_rejected_and_audited(client, db_session, qr_test_setup):
    """AC5: Scan triggering an invalid state transition (e.g. delivery confirmation on booked parcel) is rejected and logged."""
    parcel = qr_test_setup["parcel"]
    agent1 = qr_test_setup["agent1"]
    hdrs = auth_headers(agent1)

    # Reset parcel status to BOOKED
    parcel.delivery_status = ParcelStatus.BOOKED
    parcel.version_id = 1
    db_session.commit()

    valid_payload = generate_secure_qr_payload(parcel.tracking_number)

    # Scan DELIVERY_CONFIRMATION directly on a BOOKED parcel
    res = client.post(
        "/api/v1/custody/scan",
        json={
            "tracking_number": valid_payload,
            "scan_type": ScanType.DELIVERY_CONFIRMATION.value,
            "branch_id": qr_test_setup["branch1"].id
        },
        headers=hdrs
    )
    assert res.status_code == 400
    assert "illegal state transition" in res.json()["detail"].lower()

    # Verify failed scan audit record
    failed_scan = db_session.query(CustodyScan).filter(
        CustodyScan.scanned_by_id == agent1.id,
        CustodyScan.parcel_id == parcel.id,
        CustodyScan.is_successful == False
    ).order_by(CustodyScan.id.desc()).first()
    assert failed_scan is not None
    assert "illegal state transition" in failed_scan.failure_reason.lower()
