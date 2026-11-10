import pytest
from decimal import Decimal
from fastapi import status
from app.core.config import settings
from app.models.organization import Organization
from app.models.branch import Branch
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.parcel import Parcel
from app.models.assignment import DeliveryAssignment
from app.models.enums import (
    UserRole,
    OperatingStatus,
    ServiceType,
    PaymentStatus,
    ParcelStatus,
    VehicleStatus,
    VehicleType,
    AssignmentStatus,
    AssignmentType
)
from app.core.security import create_access_token, get_password_hash


def make_headers(user: User) -> dict:
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def p12_setup(db_session):
    """Provisions isolated entities for Phase 12 verification."""
    # 1. Main Org & Secondary Org
    org1 = db_session.query(Organization).filter(Organization.code == "P12_ORG1").first()
    if not org1:
        org1 = Organization(
            name="LogiFlows Express Corp",
            code="P12_ORG1",
            contact_email="ops@p12org1.com",
            contact_phone="9876500001",
            address="100 Tech Park, Bangalore",
            is_active=True
        )
        db_session.add(org1)
        db_session.flush()

    org2 = db_session.query(Organization).filter(Organization.code == "P12_ORG2").first()
    if not org2:
        org2 = Organization(
            name="Rival Courier Ltd",
            code="P12_ORG2",
            contact_email="rival@p12org2.com",
            contact_phone="9876500002",
            address="200 Freight St, Mumbai",
            is_active=True
        )
        db_session.add(org2)
        db_session.flush()

    # 2. Branches for Org 1
    br1 = db_session.query(Branch).filter(Branch.branch_code == "P12_BLR_01").first()
    if not br1:
        br1 = Branch(
            organization_id=org1.id,
            branch_code="P12_BLR_01",
            branch_name="Bangalore Central Hub",
            address="12 MG Road",
            pincode="560001",
            city="Bangalore",
            state="Karnataka",
            country="India",
            contact_email="blr@p12org1.com",
            contact_phone="9876500011",
            latitude=12.9716,
            longitude=77.5946,
            operating_status=OperatingStatus.ACTIVE,
            is_active=True
        )
        db_session.add(br1)
        db_session.flush()

    br2 = db_session.query(Branch).filter(Branch.branch_code == "P12_BOM_01").first()
    if not br2:
        br2 = Branch(
            organization_id=org1.id,
            branch_code="P12_BOM_01",
            branch_name="Mumbai Gateway Hub",
            address="45 Nariman Point",
            pincode="400021",
            city="Mumbai",
            state="Maharashtra",
            country="India",
            contact_email="bom@p12org1.com",
            contact_phone="9876500012",
            latitude=18.9220,
            longitude=72.8223,
            operating_status=OperatingStatus.ACTIVE,
            is_active=True
        )
        db_session.add(br2)
        db_session.flush()

    # 3. Users for Org 1
    org1_admin = db_session.query(User).filter(User.email == "orgadmin_p12@test.com").first()
    if not org1_admin:
        org1_admin = User(
            email="orgadmin_p12@test.com",
            hashed_password=get_password_hash("Password123!"),
            full_name="P12 Org Admin",
            role=UserRole.ORG_ADMIN,
            organization_id=org1.id,
            is_active=True
        )
        db_session.add(org1_admin)
        db_session.flush()

    mgr1 = db_session.query(User).filter(User.email == "mgr_blr_p12@test.com").first()
    if not mgr1:
        mgr1 = User(
            email="mgr_blr_p12@test.com",
            hashed_password=get_password_hash("Password123!"),
            full_name="P12 BLR Branch Manager",
            role=UserRole.BRANCH_MANAGER,
            organization_id=org1.id,
            branch_id=br1.id,
            is_active=True
        )
        db_session.add(mgr1)
        db_session.flush()

    agent1 = db_session.query(User).filter(User.email == "agent_blr_p12@test.com").first()
    if not agent1:
        agent1 = User(
            email="agent_blr_p12@test.com",
            hashed_password=get_password_hash("Password123!"),
            full_name="P12 BLR Delivery Agent",
            role=UserRole.DELIVERY_AGENT,
            organization_id=org1.id,
            branch_id=br1.id,
            is_active=True
        )
        db_session.add(agent1)
        db_session.flush()

    cust1 = db_session.query(User).filter(User.email == "cust_p12@test.com").first()
    if not cust1:
        cust1 = User(
            email="cust_p12@test.com",
            hashed_password=get_password_hash("Password123!"),
            full_name="P12 Retail Customer",
            role=UserRole.CUSTOMER,
            is_active=True
        )
        db_session.add(cust1)
        db_session.flush()

    # 4. Fleet for Org 1
    veh_van = db_session.query(Vehicle).filter(Vehicle.vehicle_number == "KA01P1201").first()
    if not veh_van:
        veh_van = Vehicle(
            organization_id=org1.id,
            branch_id=br1.id,
            vehicle_number="KA01P1201",
            vehicle_type=VehicleType.VAN,
            model="Tata Ace",
            max_weight_kg=750.0,
            max_volume_cbm=4.5,
            status=VehicleStatus.AVAILABLE,
            is_active=True
        )
        db_session.add(veh_van)
        db_session.flush()

    db_session.commit()

    return {
        "org1": org1,
        "org2": org2,
        "br1": br1,
        "br2": br2,
        "org1_admin": org1_admin,
        "mgr1": mgr1,
        "agent1": agent1,
        "cust1": cust1,
        "veh_van": veh_van,
    }


# ============================================================================
# MODULE 12.1: ORGANIZATION MANAGEMENT TESTS
# ============================================================================

def test_atomic_org_registration_creates_org_and_admin(client, db_session):
    """12.1 Acceptance: Atomic org registration creates exactly one org plus its first admin."""
    payload = {
        "name": "Swift Logistics Pvt",
        "code": "SWIFT_P12",
        "contact_email": "contact@swiftlog.com",
        "contact_phone": "9900112233",
        "address": "Electronic City, Bangalore",
        "admin_full_name": "Swift Admin",
        "admin_email": "admin@swiftlog.com",
        "admin_password": "StrongSecretPass123!",
        "admin_phone": "9900112234"
    }

    res = client.post(f"{settings.API_V1_STR}/organizations/register", json=payload)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["organization"]["code"] == "SWIFT_P12"
    assert data["admin_email"] == "admin@swiftlog.com"

    # Verify both records exist in DB
    created_org = db_session.query(Organization).filter(Organization.code == "SWIFT_P12").first()
    assert created_org is not None
    created_admin = db_session.query(User).filter(User.email == "admin@swiftlog.com").first()
    assert created_admin is not None
    assert created_admin.role == UserRole.ORG_ADMIN
    assert created_admin.organization_id == created_org.id


def test_atomic_org_registration_rolls_back_on_admin_email_conflict(client, db_session, p12_setup):
    """12.1 Acceptance: Rollback on failure guarantees zero orphaned organization records."""
    existing_admin_email = p12_setup["org1_admin"].email

    payload = {
        "name": "Failed Org Test",
        "code": "FAIL_ORG_99",
        "contact_email": "failed@test.com",
        "admin_full_name": "Failed Admin",
        "admin_email": existing_admin_email,  # Conflict!
        "admin_password": "Pass123456Secret!"
    }

    res = client.post(f"{settings.API_V1_STR}/organizations/register", json=payload)
    assert res.status_code == status.HTTP_409_CONFLICT

    # Verify that NO organization was created
    orphaned_org = db_session.query(Organization).filter(Organization.code == "FAIL_ORG_99").first()
    assert orphaned_org is None


def test_suspended_organization_users_locked_out(client, db_session, p12_setup, superadmin_headers):
    """12.1 Acceptance: A suspended org's users cannot authenticate or call APIs."""
    org1 = p12_setup["org1"]
    org_admin = p12_setup["org1_admin"]

    # 1. Suspend Organization via Super Admin
    suspend_res = client.patch(
        f"{settings.API_V1_STR}/organizations/{org1.id}/status",
        json={"is_active": False, "reason": "Audit review compliance hold"},
        headers=superadmin_headers
    )
    assert suspend_res.status_code == 200
    assert suspend_res.json()["is_active"] is False

    # 2. Existing org user login must be rejected with 403 Forbidden
    login_res = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": org_admin.email, "password": "Password123!"}
    )
    assert login_res.status_code == status.HTTP_403_FORBIDDEN
    assert "suspended or deactivated" in login_res.json()["detail"].lower()

    # 3. Existing token API calls from that org user must be rejected with 403 Forbidden
    admin_headers = make_headers(org_admin)
    api_res = client.get(f"{settings.API_V1_STR}/branches", headers=admin_headers)
    assert api_res.status_code == status.HTTP_403_FORBIDDEN

    # 4. Super Admin remains unaffected
    sa_res = client.get(f"{settings.API_V1_STR}/organizations", headers=superadmin_headers)
    assert sa_res.status_code == 200

    # Restore organization active state for subsequent tests
    client.patch(
        f"{settings.API_V1_STR}/organizations/{org1.id}/status",
        json={"is_active": True},
        headers=superadmin_headers
    )


def test_tenant_settings_validation_and_scoping(client, p12_setup):
    """12.1 Acceptance: Settings are validated and tenant-scoped."""
    org1_admin = p12_setup["org1_admin"]
    org2 = p12_setup["org2"]
    admin_headers = make_headers(org1_admin)

    # 1. Get my-org settings
    res = client.get(f"{settings.API_V1_STR}/organizations/my-org", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["code"] == "P12_ORG1"

    # 2. Attempt to view or modify other org's settings returns 404 (no existence leak)
    cross_res = client.get(f"{settings.API_V1_STR}/organizations/{org2.id}", headers=admin_headers)
    assert cross_res.status_code == status.HTTP_404_NOT_FOUND

    # 3. Update my-org profile
    update_res = client.patch(
        f"{settings.API_V1_STR}/organizations/my-org",
        json={"contact_phone": "9112233445", "address": "Updated HQ, Bangalore"},
        headers=admin_headers
    )
    assert update_res.status_code == 200
    assert update_res.json()["contact_phone"] == "9112233445"


# ============================================================================
# MODULE 12.2: BRANCH MANAGEMENT TESTS
# ============================================================================

def test_branch_cannot_be_deactivated_with_active_parcels(client, db_session, p12_setup):
    """12.2 Acceptance: A branch with active parcels cannot be deactivated (409 with clear reason)."""
    br1 = p12_setup["br1"]
    br2 = p12_setup["br2"]
    org_admin = p12_setup["org1_admin"]
    admin_headers = make_headers(org_admin)

    # Create active parcel on br1
    active_parcel = Parcel(
        tracking_number="LF-2026-P12ACT01",
        origin_branch_id=br1.id,
        dest_branch_id=br2.id,
        sender_name="Sender", sender_phone="9988776655", sender_address="S1", sender_city="BLR", sender_state="KA", sender_pincode="560001",
        receiver_name="Receiver", receiver_phone="9988776654", receiver_address="R1", receiver_city="BOM", receiver_state="MH", receiver_pincode="400021",
        weight_kg=3.0, length_cm=15.0, width_cm=15.0, height_cm=15.0, volumetric_weight_kg=0.68,
        service_type=ServiceType.STANDARD,
        base_charge=50.0, weight_charge=75.0, service_charge=0.0, tax_amount=22.5, total_charge=147.5,
        payment_status=PaymentStatus.PAID,
        delivery_status=ParcelStatus.AT_ORIGIN_BRANCH,
        booking_date=db_session.query(Branch).first().created_at
    )
    db_session.add(active_parcel)
    db_session.commit()

    # Attempt to deactivate br1
    res = client.delete(f"{settings.API_V1_STR}/branches/{br1.id}", headers=admin_headers)
    assert res.status_code == status.HTTP_409_CONFLICT
    assert "active parcel(s) are currently in progress" in res.json()["detail"]


def test_branch_manager_sees_only_assigned_branch(client, p12_setup):
    """12.2 Acceptance: Branch Manager sees only their branch."""
    mgr1 = p12_setup["mgr1"]
    br1 = p12_setup["br1"]
    mgr_headers = make_headers(mgr1)

    res = client.get(f"{settings.API_V1_STR}/branches", headers=mgr_headers)
    assert res.status_code == 200
    branches = res.json()
    assert len(branches) == 1
    assert branches[0]["id"] == br1.id
    assert branches[0]["branch_code"] == br1.branch_code


def test_branch_code_uniqueness_per_organization(client, p12_setup):
    """12.2 Acceptance: Branch codes are unique per organization."""
    org1_admin = p12_setup["org1_admin"]
    br1 = p12_setup["br1"]
    admin_headers = make_headers(org1_admin)

    payload = {
        "branch_code": br1.branch_code,  # Duplicate!
        "branch_name": "Duplicate Branch Code Hub",
        "address": "Road 99",
        "pincode": "560099",
        "city": "Bangalore",
        "state": "Karnataka",
        "country": "India",
        "contact_email": "dup@test.com",
        "contact_phone": "9900112200"
    }
    res = client.post(f"{settings.API_V1_STR}/branches", json=payload, headers=admin_headers)
    assert res.status_code == status.HTTP_409_CONFLICT


# ============================================================================
# MODULE 12.3: EMPLOYEE MANAGEMENT TESTS
# ============================================================================

def test_privilege_ceiling_enforcement_on_role_assignment(client, p12_setup):
    """12.3 Acceptance: Only authorized roles can assign roles, never above or equal to own level."""
    org1_admin = p12_setup["org1_admin"]  # Rank 3
    mgr1 = p12_setup["mgr1"]              # Rank 2
    admin_headers = make_headers(org1_admin)
    mgr_headers = make_headers(mgr1)

    # 1. Org Admin cannot onboard a Super Admin or another Org Admin
    payload_sa = {
        "email": "rogue_sa@test.com",
        "full_name": "Rogue SA",
        "role": "SUPER_ADMIN"
    }
    res_sa = client.post(f"{settings.API_V1_STR}/employees", json=payload_sa, headers=admin_headers)
    assert res_sa.status_code == status.HTTP_403_FORBIDDEN
    assert "privilege ceiling" in res_sa.json()["detail"].lower()

    payload_oa = {
        "email": "rogue_oa@test.com",
        "full_name": "Rogue OA",
        "role": "ORG_ADMIN"
    }
    res_oa = client.post(f"{settings.API_V1_STR}/employees", json=payload_oa, headers=admin_headers)
    assert res_oa.status_code == status.HTTP_403_FORBIDDEN

    # 2. Branch Manager can only onboard DELIVERY_AGENT, not BRANCH_MANAGER
    payload_bm = {
        "email": "rogue_bm@test.com",
        "full_name": "Rogue BM",
        "role": "BRANCH_MANAGER"
    }
    res_bm = client.post(f"{settings.API_V1_STR}/employees", json=payload_bm, headers=mgr_headers)
    assert res_bm.status_code == status.HTTP_403_FORBIDDEN


def test_secure_credential_provisioning_one_time_invite(client, p12_setup):
    """12.3 Acceptance: Secure credential provisioning via one-time invite link; single-use enforced."""
    org1_admin = p12_setup["org1_admin"]
    agent1 = p12_setup["agent1"]
    admin_headers = make_headers(org1_admin)

    # 1. Generate one-time invite token
    invite_res = client.post(f"{settings.API_V1_STR}/employees/{agent1.id}/invite", headers=admin_headers)
    assert invite_res.status_code == 200
    data = invite_res.json()
    invite_token = data["invite_token"]
    assert invite_token is not None

    # 2. Accept invite to set password
    accept_res = client.post(
        f"{settings.API_V1_STR}/employees/accept-invite",
        json={"invite_token": invite_token, "new_password": "NewAgentSecretPassword123!"}
    )
    assert accept_res.status_code == 200
    assert "Password configured successfully" in accept_res.json()["message"]

    # 3. Re-using the same invite token must be rejected (single-use via RevokedToken)
    reuse_res = client.post(
        f"{settings.API_V1_STR}/employees/accept-invite",
        json={"invite_token": invite_token, "new_password": "AnotherPassword123!"}
    )
    assert reuse_res.status_code == status.HTTP_400_BAD_REQUEST
    assert "already been used" in reuse_res.json()["detail"].lower()


def test_deactivated_employee_locked_out_immediately(client, p12_setup):
    """12.3 Acceptance: Deactivated employees are locked out immediately."""
    org1_admin = p12_setup["org1_admin"]
    agent1 = p12_setup["agent1"]
    admin_headers = make_headers(org1_admin)
    agent_headers = make_headers(agent1)

    # Deactivate employee
    client.put(
        f"{settings.API_V1_STR}/employees/{agent1.id}",
        json={"is_active": False},
        headers=admin_headers
    )

    # Immediate API lockout
    res = client.get(f"{settings.API_V1_STR}/assignments", headers=agent_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # Reactivate for subsequent test isolation
    client.put(
        f"{settings.API_V1_STR}/employees/{agent1.id}",
        json={"is_active": True},
        headers=admin_headers
    )


# ============================================================================
# MODULE 12.4: VEHICLE MANAGEMENT TESTS
# ============================================================================

def test_vehicle_in_maintenance_cannot_be_assigned(client, db_session, p12_setup):
    """12.4 Acceptance: A vehicle in maintenance cannot be assigned."""
    veh_van = p12_setup["veh_van"]
    br1 = p12_setup["br1"]
    br2 = p12_setup["br2"]
    mgr1 = p12_setup["mgr1"]
    agent1 = p12_setup["agent1"]
    mgr_headers = make_headers(mgr1)

    # 1. Place vehicle into maintenance
    maint_res = client.patch(
        f"{settings.API_V1_STR}/vehicles/{veh_van.id}/maintenance",
        json={"is_in_maintenance": True, "notes": "Engine oil and tire rotation"},
        headers=mgr_headers
    )
    assert maint_res.status_code == 200
    assert maint_res.json()["status"] == "MAINTENANCE"

    # 2. Create parcel
    parcel = Parcel(
        tracking_number="LF-2026-P12VEH01",
        origin_branch_id=br1.id, dest_branch_id=br2.id,
        sender_name="S", sender_phone="9988776655", sender_address="S1", sender_city="BLR", sender_state="KA", sender_pincode="560001",
        receiver_name="R", receiver_phone="9988776654", receiver_address="R1", receiver_city="BOM", receiver_state="MH", receiver_pincode="400021",
        weight_kg=2.0, length_cm=10.0, width_cm=10.0, height_cm=10.0, volumetric_weight_kg=0.2,
        service_type=ServiceType.STANDARD, total_charge=100.0,
        payment_status=PaymentStatus.PAID, delivery_status=ParcelStatus.BOOKED,
        booking_date=br1.created_at
    )
    db_session.add(parcel)
    db_session.commit()

    # 3. Attempt to assign vehicle in maintenance -> Conflict 409
    assign_payload = {
        "parcel_id": parcel.id,
        "employee_id": agent1.id,
        "vehicle_id": veh_van.id,
        "assignment_type": "PICKUP"
    }
    assign_res = client.post(f"{settings.API_V1_STR}/assignments", json=assign_payload, headers=mgr_headers)
    assert assign_res.status_code == status.HTTP_409_CONFLICT
    assert "unavailable" in assign_res.json()["detail"].lower()

    # Restore vehicle to available
    client.patch(
        f"{settings.API_V1_STR}/vehicles/{veh_van.id}/maintenance",
        json={"is_in_maintenance": False},
        headers=mgr_headers
    )


def test_vehicle_registration_number_normalized(client, p12_setup):
    """12.4 Acceptance: Vehicle registration numbers are normalized and unique."""
    org1_admin = p12_setup["org1_admin"]
    br1 = p12_setup["br1"]
    admin_headers = make_headers(org1_admin)

    # Create vehicle with hyphenated lowercase registration
    payload = {
        "vehicle_number": "ka-05-xy-9988",
        "vehicle_type": "BIKE",
        "max_weight_kg": 40.0,
        "branch_id": br1.id
    }
    res = client.post(f"{settings.API_V1_STR}/vehicles", json=payload, headers=admin_headers)
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["vehicle_number"] == "KA05XY9988"  # Canonical uppercase normalized

    # Duplicate attempt with spaces
    dup_payload = {
        "vehicle_number": "KA 05 XY 9988",
        "vehicle_type": "BIKE",
        "max_weight_kg": 40.0,
        "branch_id": br1.id
    }
    dup_res = client.post(f"{settings.API_V1_STR}/vehicles", json=dup_payload, headers=admin_headers)
    assert dup_res.status_code == status.HTTP_409_CONFLICT


# ============================================================================
# MODULE 12.5: CUSTOMER MANAGEMENT TESTS
# ============================================================================

def test_public_registration_strictly_yields_customer_role(client):
    """12.5 Acceptance: Public registration always yields role CUSTOMER; privileged role attempts rejected/ignored."""
    payload_exploit = {
        "email": "exploit_user@test.com",
        "password": "SecretPassword123!",
        "full_name": "Privilege Escalation Tester",
        "role": "SUPER_ADMIN"  # Malicious injection
    }
    # Request body with extra field 'role' must be rejected with 422 Unprocessable Entity
    res = client.post(f"{settings.API_V1_STR}/auth/register", json=payload_exploit)
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Valid registration strictly yields CUSTOMER
    payload_valid = {
        "email": "legit_customer@test.com",
        "password": "SecretPassword123!",
        "full_name": "Legit Customer",
        "phone": "+91 9988776655"
    }
    res_valid = client.post(f"{settings.API_V1_STR}/auth/register", json=payload_valid)
    assert res_valid.status_code == status.HTTP_201_CREATED
    assert res_valid.json()["role"] == "CUSTOMER"


def test_customer_address_book_and_profile_isolation(client, p12_setup):
    """12.5 Acceptance: Customer sees only their own data and can manage their address book."""
    cust1 = p12_setup["cust1"]
    cust_headers = make_headers(cust1)

    # 1. Update customer profile with saved default addresses
    update_payload = {
        "company_name": "Acme Retailers",
        "gst_number": "29ABCDE1234F1Z5",
        "default_pickup_address": "Warehouse 4, Electronic City, Bangalore",
        "default_delivery_address": "Suite 500, Cyber Towers, Hyderabad"
    }
    put_res = client.put(f"{settings.API_V1_STR}/customers/me/profile", json=update_payload, headers=cust_headers)
    assert put_res.status_code == 200
    data = put_res.json()
    assert data["customer_profile"]["company_name"] == "Acme Retailers"
    assert "Warehouse 4" in data["customer_profile"]["default_pickup_address"]

    # 2. Get my profile
    get_res = client.get(f"{settings.API_V1_STR}/customers/me/profile", headers=cust_headers)
    assert get_res.status_code == 200
    assert get_res.json()["email"] == cust1.email


# ============================================================================
# MODULE 12.6: PARCEL BOOKING TESTS
# ============================================================================

def test_invalid_postal_codes_and_prohibited_parcels_rejected(client, p12_setup):
    """12.6 Acceptance: Invalid postal codes, prohibited items, and oversized parcels return 422."""
    cust1 = p12_setup["cust1"]
    br1 = p12_setup["br1"]
    br2 = p12_setup["br2"]
    cust_headers = make_headers(cust1)

    base_payload = {
        "origin_branch_id": br1.id,
        "dest_branch_id": br2.id,
        "sender_name": "S", "sender_phone": "9988776655", "sender_address": "S1", "sender_city": "BLR", "sender_state": "KA", "sender_pincode": "560001",
        "receiver_name": "R", "receiver_phone": "9988776654", "receiver_address": "R1", "receiver_city": "BOM", "receiver_state": "MH", "receiver_pincode": "400021",
        "weight_kg": 2.0, "length_cm": 20.0, "width_cm": 20.0, "height_cm": 20.0,
        "service_type": "STANDARD"
    }

    # 1. Invalid sender pincode (non-numeric)
    p_invalid_pin = dict(base_payload)
    p_invalid_pin["sender_pincode"] = "INVALID_PIN"
    res1 = client.post(f"{settings.API_V1_STR}/parcels", json=p_invalid_pin, headers=cust_headers)
    assert res1.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. Prohibited cargo keyword in notes
    p_prohibited = dict(base_payload)
    p_prohibited["notes"] = "Handle with care, contains explosive materials"
    res2 = client.post(f"{settings.API_V1_STR}/parcels", json=p_prohibited, headers=cust_headers)
    assert res2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 3. Oversized parcel (weight > 500kg)
    p_oversized = dict(base_payload)
    p_oversized["weight_kg"] = 800.0
    res3 = client.post(f"{settings.API_V1_STR}/parcels", json=p_oversized, headers=cust_headers)
    assert res3.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ============================================================================
# MODULE 12.7: DELIVERY ASSIGNMENT TESTS
# ============================================================================

def test_explainable_dispatch_suggestions(client, db_session, p12_setup):
    """12.7 Acceptance: Suggestions are explainable (showing workload and capacity inputs)."""
    br1 = p12_setup["br1"]
    br2 = p12_setup["br2"]
    mgr1 = p12_setup["mgr1"]
    mgr_headers = make_headers(mgr1)

    # Create parcel at destination hub ready for last-mile delivery
    parcel = Parcel(
        tracking_number="LF-2026-P12SUG01",
        origin_branch_id=br2.id, dest_branch_id=br1.id,
        sender_name="S", sender_phone="9988776655", sender_address="S1", sender_city="BOM", sender_state="MH", sender_pincode="400021",
        receiver_name="R", receiver_phone="9988776654", receiver_address="R1", receiver_city="BLR", receiver_state="KA", receiver_pincode="560001",
        weight_kg=15.0, length_cm=30.0, width_cm=30.0, height_cm=30.0, volumetric_weight_kg=5.4,
        service_type=ServiceType.STANDARD, total_charge=450.0,
        payment_status=PaymentStatus.PAID, delivery_status=ParcelStatus.AT_DESTINATION_BRANCH,
        booking_date=br1.created_at
    )
    db_session.add(parcel)
    db_session.commit()

    res = client.get(f"{settings.API_V1_STR}/assignments/suggestions/{parcel.id}", headers=mgr_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["parcel_id"] == parcel.id
    assert len(data["suggested_employees"]) > 0
    assert len(data["suggested_vehicles"]) > 0
    assert "explanation" in data["suggested_employees"][0]
    assert "explanation" in data["suggested_vehicles"][0]
    assert data["suggested_vehicles"][0]["fits_capacity"] is True


def test_assignment_cancellation_restores_resources(client, db_session, p12_setup):
    """12.7 Acceptance: Cancellation restores resources and records history."""
    br1 = p12_setup["br1"]
    br2 = p12_setup["br2"]
    mgr1 = p12_setup["mgr1"]
    agent1 = p12_setup["agent1"]
    veh_van = p12_setup["veh_van"]
    mgr_headers = make_headers(mgr1)

    # 1. Create parcel and assignment
    parcel = Parcel(
        tracking_number="LF-2026-P12CAN01",
        origin_branch_id=br1.id, dest_branch_id=br2.id,
        sender_name="S", sender_phone="9988776655", sender_address="S1", sender_city="BLR", sender_state="KA", sender_pincode="560001",
        receiver_name="R", receiver_phone="9988776654", receiver_address="R1", receiver_city="BOM", receiver_state="MH", receiver_pincode="400021",
        weight_kg=5.0, length_cm=20.0, width_cm=20.0, height_cm=20.0, volumetric_weight_kg=1.6,
        service_type=ServiceType.STANDARD, total_charge=200.0,
        payment_status=PaymentStatus.PAID, delivery_status=ParcelStatus.BOOKED,
        booking_date=br1.created_at
    )
    db_session.add(parcel)
    db_session.commit()

    assign_res = client.post(
        f"{settings.API_V1_STR}/assignments",
        json={
            "parcel_id": parcel.id,
            "employee_id": agent1.id,
            "vehicle_id": veh_van.id,
            "assignment_type": "PICKUP"
        },
        headers=mgr_headers
    )
    assert assign_res.status_code == 201
    assignment_id = assign_res.json()["id"]

    # Verify vehicle status is ASSIGNED
    db_session.refresh(veh_van)
    assert veh_van.status == VehicleStatus.ASSIGNED

    # 2. Cancel assignment
    cancel_res = client.post(
        f"{settings.API_V1_STR}/assignments/{assignment_id}/cancel",
        json={"reason": "Customer requested delivery schedule modification"},
        headers=mgr_headers
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    # 3. Verify vehicle restored to AVAILABLE
    db_session.refresh(veh_van)
    assert veh_van.status == VehicleStatus.AVAILABLE
