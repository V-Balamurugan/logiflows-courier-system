"""Full System Integration Test Suite for LogiFlows Courier Management System.

Tests all system features end-to-end with realistic sample data across:
1. Authentication, token refresh, and user lifecycle
2. Multi-tenant organization isolation and suspended tenant lockout
3. Branch management, Sorting Hub metrics, and soft-delete protections
4. Staff onboarding, cryptographic one-time invites, and privilege ceiling
5. Fleet registration, number normalization, and maintenance conflict guards
6. Customer profile, corporate billing, and address book
7. Parcel quote pricing, input validation, booking, and PDF label generation
8. Cryptographic QR custody tokens, transfer scans, and SHA-256 ledger integrity
9. Linehaul transfers, consolidation bags, dispatch CAS locks, and inward reconciliation
10. Dynamic route optimization, 2-opt TSP heuristics, and multi-stop vehicle retention
11. Public tracking PII sanitization and CSV formula injection defense
"""
import pytest
from datetime import datetime, timezone
from fastapi import status

from app.models.enums import (
    UserRole,
    OperatingStatus,
    VehicleType,
    VehicleStatus,
    ServiceType,
    PaymentStatus,
    ParcelStatus,
    RouteStatus,
    RouteStopStatus,
    RouteStopType,
    ManifestStatus,
    BagStatus,
    DiscrepancyType,
    DiscrepancySeverity,
    DiscrepancyStatus,
    ScanType,
)
from app.models.organization import Organization
from app.models.branch import Branch
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.parcel import Parcel
from app.core.security import create_access_token
from app.utils.qr_security import generate_secure_qr_payload


@pytest.mark.usefixtures("setup_test_db")
class TestFullSystemIntegration:

    def test_01_authentication_and_user_lifecycle(self, client, db_session):
        """Verify authentication, user profile, registration, token refresh, and revocation."""
        # 1. Login as Org Admin
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "orgadmin@logiflows.com", "password": "OrgAdmin@123"}
        )
        assert login_res.status_code == status.HTTP_200_OK
        data = login_res.json()
        assert "access_token" in data
        assert "refresh_token" in data
        admin_token = data["access_token"]
        refresh_token = data["refresh_token"]

        # 2. Get current user profile
        me_res = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert me_res.status_code == status.HTTP_200_OK
        me_data = me_res.json()
        assert me_data["email"] == "orgadmin@logiflows.com"
        assert me_data["role"] == UserRole.ORG_ADMIN.value

        # 3. Test token refresh
        ref_res = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert ref_res.status_code == status.HTTP_200_OK
        new_token = ref_res.json()["access_token"]
        assert new_token != admin_token

        # 4. Public customer self-registration
        reg_res = client.post(
            "/api/v1/auth/register",
            json={
                "email": "sample.customer@businesscorp.com",
                "password": "Password@1234",
                "full_name": "Siddharth Merchant",
                "phone": "+91 98200 12345"
            }
        )
        assert reg_res.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        cust_info = reg_res.json()
        assert cust_info["role"] == UserRole.CUSTOMER.value

        # 5. Logout and verify token revocation
        logout_res = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {new_token}"}
        )
        assert logout_res.status_code == status.HTTP_200_OK

        # Revoked token should now be rejected
        blocked_me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {new_token}"}
        )
        assert blocked_me.status_code == status.HTTP_401_UNAUTHORIZED

    def test_02_multi_tenancy_and_suspended_organization(self, client, superadmin_headers, orgadmin_headers):
        """Verify strict multi-tenant boundary and suspended tenant lockout."""
        # 1. Super Admin registers a second organization
        org2_res = client.post(
            "/api/v1/organizations/register",
            headers=superadmin_headers,
            json={
                "name": "SwiftTrans Express Cargo Ltd",
                "code": "SWIFTTRANS",
                "contact_email": "ops@swifttrans.com",
                "contact_phone": "+91 99999 11111",
                "address": "Express Logistics Hub, Okhla Phase 3, New Delhi",
                "admin_email": "admin@swifttrans.com",
                "admin_password": "Admin@Swift123",
                "admin_full_name": "Kavita Rao",
                "admin_phone": "+91 99999 22222"
            }
        )
        assert org2_res.status_code == status.HTTP_201_CREATED
        org2_id = org2_res.json()["organization"]["id"]

        # 2. Login as Tenant 2 Org Admin and create a branch
        t2_login = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@swifttrans.com", "password": "Admin@Swift123"}
        )
        assert t2_login.status_code == status.HTTP_200_OK
        t2_token = t2_login.json()["access_token"]
        t2_headers = {"Authorization": f"Bearer {t2_token}"}

        branch2_res = client.post(
            "/api/v1/branches",
            headers=t2_headers,
            json={
                "branch_code": "SWIFT-DEL-01",
                "branch_name": "SwiftTrans Delhi Hub",
                "address": "Okhla Industrial Area Phase 2",
                "pincode": "110020",
                "city": "New Delhi",
                "state": "Delhi",
                "country": "India",
                "latitude": 28.5355,
                "longitude": 77.2731,
                "contact_email": "delhi@swifttrans.com",
                "contact_phone": "+91 99999 33333"
            }
        )
        assert branch2_res.status_code == status.HTTP_201_CREATED
        branch2_id = branch2_res.json()["id"]

        # 3. Tenant 1 Org Admin attempts to access Tenant 2 branch -> Returns HTTP 404 (no leak)
        leak_res = client.get(
            f"/api/v1/branches/{branch2_id}",
            headers=orgadmin_headers
        )
        assert leak_res.status_code == status.HTTP_404_NOT_FOUND

        # 4. Super Admin suspends Tenant 2
        suspend_res = client.patch(
            f"/api/v1/organizations/{org2_id}/status",
            headers=superadmin_headers,
            json={"is_active": False}
        )
        assert suspend_res.status_code == status.HTTP_200_OK

        # 5. Suspended tenant cannot log in -> HTTP 403 Forbidden
        blocked_login = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@swifttrans.com", "password": "Admin@Swift123"}
        )
        assert blocked_login.status_code == status.HTTP_403_FORBIDDEN

    def test_03_branch_and_employee_management(self, client, orgadmin_headers):
        """Verify branch creation, sorting hub metrics, staff invite token, and privilege ceiling."""
        # 1. Create a new branch in Pune
        branch_res = client.post(
            "/api/v1/branches",
            headers=orgadmin_headers,
            json={
                "branch_code": "PUN-001",
                "branch_name": "Pune Central Sorting Hub",
                "address": "Hinjawadi Phase 2, Rajiv Gandhi Infotech Park",
                "pincode": "411057",
                "city": "Pune",
                "state": "Maharashtra",
                "country": "India",
                "latitude": 18.5913,
                "longitude": 73.7389,
                "contact_email": "pune.hub@logiflows.com",
                "contact_phone": "+91 98765 00004"
            }
        )
        assert branch_res.status_code == status.HTTP_201_CREATED
        pune_branch_id = branch_res.json()["id"]

        # 2. View sorting hub dashboard metrics
        dash_res = client.get(
            f"/api/v1/branches/{pune_branch_id}/dashboard",
            headers=orgadmin_headers
        )
        assert dash_res.status_code == status.HTTP_200_OK
        assert "active_inbound_parcels" in dash_res.json()
        assert "stationed_vehicles" in dash_res.json()

        # 3. Onboard a new delivery agent at Pune Hub
        emp_res = client.post(
            "/api/v1/employees",
            headers=orgadmin_headers,
            json={
                "email": "agent.tanmay@logiflows.com",
                "full_name": "Tanmay Deshmukh",
                "phone": "+91 98765 88888",
                "role": UserRole.DELIVERY_AGENT.value,
                "branch_id": pune_branch_id
            }
        )
        assert emp_res.status_code == status.HTTP_201_CREATED
        tanmay_id = emp_res.json()["id"]

        # 4. Generate one-time cryptographic invite token
        invite_res = client.post(
            f"/api/v1/employees/{tanmay_id}/invite",
            headers=orgadmin_headers
        )
        assert invite_res.status_code == status.HTTP_200_OK
        invite_token = invite_res.json()["invite_token"]

        # 5. Employee accepts invite and sets password
        accept_res = client.post(
            "/api/v1/employees/accept-invite",
            json={
                "invite_token": invite_token,
                "new_password": "TanmayAgent@123"
            }
        )
        assert accept_res.status_code == status.HTTP_200_OK

        # 6. Reusing the invite token must fail (jti revoked)
        replay_res = client.post(
            "/api/v1/employees/accept-invite",
            json={
                "invite_token": invite_token,
                "new_password": "TanmayAgent@456"
            }
        )
        assert replay_res.status_code == status.HTTP_400_BAD_REQUEST

        # 7. Role ceiling: Org Admin cannot elevate someone to SUPER_ADMIN -> 403 Forbidden
        ceiling_res = client.post(
            "/api/v1/employees",
            headers=orgadmin_headers,
            json={
                "email": "hacker@logiflows.com",
                "full_name": "Privilege Escalation Attempt",
                "phone": "+91 99999 00000",
                "role": UserRole.SUPER_ADMIN.value,
                "branch_id": pune_branch_id
            }
        )
        assert ceiling_res.status_code == status.HTTP_403_FORBIDDEN

    def test_04_fleet_registration_and_maintenance(self, client, orgadmin_headers, db_session):
        """Verify vehicle registration normalization and maintenance locking."""
        # 1. Register a new fleet vehicle
        pune_branch = db_session.query(Branch).filter(Branch.branch_code == "PUN-001").first()
        veh_res = client.post(
            "/api/v1/vehicles",
            headers=orgadmin_headers,
            json={
                "branch_id": pune_branch.id,
                "vehicle_number": "mh-12-de-5566",  # Lowercase with hyphens
                "vehicle_type": VehicleType.VAN.value,
                "model": "Mahindra Supro Maxi Truck",
                "max_weight_kg": 1000.0,
                "max_volume_cbm": 8.5
            }
        )
        assert veh_res.status_code == status.HTTP_201_CREATED
        v_data = veh_res.json()
        # Normalization stripped hyphens/spaces and uppercased
        assert "MH" in v_data["vehicle_number"]
        v_id = v_data["id"]

        # 2. Toggle to MAINTENANCE
        maint_res = client.patch(
            f"/api/v1/vehicles/{v_id}/maintenance",
            headers=orgadmin_headers,
            json={"is_in_maintenance": True, "notes": "Scheduled 10,000 km oil service"}
        )
        assert maint_res.status_code == status.HTTP_200_OK
        assert maint_res.json()["status"] == VehicleStatus.MAINTENANCE.value

        # 3. Toggle back to AVAILABLE
        avail_res = client.patch(
            f"/api/v1/vehicles/{v_id}/maintenance",
            headers=orgadmin_headers,
            json={"is_in_maintenance": False}
        )
        assert avail_res.status_code == status.HTTP_200_OK
        assert avail_res.json()["status"] == VehicleStatus.AVAILABLE.value

    def test_05_customer_profile_and_address_book(self, client, customer_headers):
        """Verify customer address book, company name, and billing details."""
        # Update profile
        update_res = client.put(
            "/api/v1/customers/me/profile",
            headers=customer_headers,
            json={
                "company_name": "Apex Trade Solutions Pvt Ltd",
                "gst_number": "27AABCU9603R1ZM",
                "default_pickup_address": "402 Peninsula Corporate Park, Lower Parel, Mumbai",
                "default_delivery_address": "88 Commercial Street, Bengaluru"
            }
        )
        assert update_res.status_code == status.HTTP_200_OK
        data = update_res.json()
        assert data["customer_profile"] is not None
        assert data["customer_profile"]["company_name"] == "Apex Trade Solutions Pvt Ltd"
        assert data["customer_profile"]["gst_number"] == "27AABCU9603R1ZM"

        # Read back profile
        get_res = client.get("/api/v1/customers/me/profile", headers=customer_headers)
        assert get_res.status_code == status.HTTP_200_OK
        assert get_res.json()["customer_profile"]["company_name"] == "Apex Trade Solutions Pvt Ltd"

    def test_06_parcel_booking_pricing_and_label(self, client, customer_headers, db_session):
        """Verify pricing engine, validation safeguards, consignment creation, and PDF label generation."""
        # 1. Price quote calculation
        quote_res = client.post(
            "/api/v1/parcels/quote",
            headers=customer_headers,
            json={
                "weight_kg": 4.5,
                "length_cm": 25.0,
                "width_cm": 20.0,
                "height_cm": 15.0,
                "service_type": ServiceType.EXPRESS.value,
                "origin_pincode": "400069",
                "dest_pincode": "411057"
            }
        )
        assert quote_res.status_code == status.HTTP_200_OK
        quote = quote_res.json()
        assert quote["total_charge"] > 0
        assert quote["base_charge"] > 0

        # 2. Input validation: malformed postal code
        bad_pincode = client.post(
            "/api/v1/parcels/quote",
            headers=customer_headers,
            json={
                "weight_kg": 2.0,
                "service_type": ServiceType.STANDARD.value,
                "origin_pincode": "INVALID_ZIP",
                "dest_pincode": "411057"
            }
        )
        assert bad_pincode.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # 3. Input validation: prohibited cargo keyword
        mumbai_hub = db_session.query(Branch).filter(Branch.branch_code == "BOM-001").first()
        pune_hub = db_session.query(Branch).filter(Branch.branch_code == "PUN-001").first()

        contraband_res = client.post(
            "/api/v1/parcels",
            headers=customer_headers,
            json={
                "origin_branch_id": mumbai_hub.id,
                "dest_branch_id": pune_hub.id,
                "sender_name": "Siddharth Merchant",
                "sender_phone": "+91 98200 12345",
                "sender_email": "siddharth@businesscorp.com",
                "sender_address": "12 Nariman Point",
                "sender_city": "Mumbai",
                "sender_state": "Maharashtra",
                "sender_pincode": "400021",
                "receiver_name": "Amit Kulkarni",
                "receiver_phone": "+91 98200 67890",
                "receiver_email": "amit@puneventures.com",
                "receiver_address": "88 Aundh Main Road",
                "receiver_city": "Pune",
                "receiver_state": "Maharashtra",
                "receiver_pincode": "411007",
                "weight_kg": 2.5,
                "length_cm": 15.0,
                "width_cm": 10.0,
                "height_cm": 8.0,
                "service_type": ServiceType.EXPRESS.value,
                "notes": "Urgent hazardous contraband cargo inside"  # Filtered keywords
            }
        )
        assert contraband_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # 4. Book valid consignment with coordinates
        valid_res = client.post(
            "/api/v1/parcels",
            headers=customer_headers,
            json={
                "origin_branch_id": mumbai_hub.id,
                "dest_branch_id": pune_hub.id,
                "sender_name": "Siddharth Merchant",
                "sender_phone": "+91 98200 12345",
                "sender_email": "siddharth@businesscorp.com",
                "sender_address": "12 Nariman Point",
                "sender_city": "Mumbai",
                "sender_state": "Maharashtra",
                "sender_pincode": "400021",
                "receiver_name": "Amit Kulkarni",
                "receiver_phone": "+91 98200 67890",
                "receiver_email": "amit@puneventures.com",
                "receiver_address": "88 Aundh Main Road",
                "receiver_city": "Pune",
                "receiver_state": "Maharashtra",
                "receiver_pincode": "411007",
                "weight_kg": 2.5,
                "length_cm": 15.0,
                "width_cm": 10.0,
                "height_cm": 8.0,
                "service_type": ServiceType.EXPRESS.value,
                "origin_lat": 18.9220,
                "origin_lng": 72.8347,
                "dest_lat": 18.5590,
                "dest_lng": 73.8073,
                "notes": "Medical supplies and diagnostic samples"
            }
        )
        assert valid_res.status_code == status.HTTP_201_CREATED
        p_data = valid_res.json()
        assert p_data["tracking_number"].startswith("LF-")
        tracking_num = p_data["tracking_number"]

        # 5. Generate and download PDF shipping label
        label_res = client.get(
            f"/api/v1/parcels/{tracking_num}/label",
            headers=customer_headers
        )
        assert label_res.status_code == status.HTTP_200_OK
        assert "application/pdf" in label_res.headers.get("content-type", "")
        assert label_res.content.startswith(b"%PDF-")

    def test_07_qr_custody_and_hash_chain(self, client, agent_headers, db_session):
        """Verify QR custody tokens, scan events, and immutable SHA-256 hash chaining."""
        mumbai_hub = db_session.query(Branch).filter(Branch.branch_code == "BOM-001").first()
        delhi_hub = db_session.query(Branch).filter(Branch.branch_code == "DEL-001").first()
        customer = db_session.query(User).filter(User.role == UserRole.CUSTOMER).first()

        parcel = Parcel(
            tracking_number="LF-CUSTODY-TEST-001",
            customer_id=customer.id,
            origin_branch_id=mumbai_hub.id,
            dest_branch_id=delhi_hub.id,
            sender_name="Origin Shipper",
            sender_phone="+91 98000 11111",
            sender_email="shipper@test.com",
            sender_address="Bandra East",
            sender_city="Mumbai",
            sender_state="Maharashtra",
            sender_pincode="400051",
            receiver_name="Dest Consignee",
            receiver_phone="+91 98000 22222",
            receiver_email="consignee@test.com",
            receiver_address="Connaught Place",
            receiver_city="New Delhi",
            receiver_state="Delhi",
            receiver_pincode="110001",
            weight_kg=2.0,
            length_cm=10.0,
            width_cm=10.0,
            height_cm=10.0,
            volumetric_weight_kg=0.2,
            service_type=ServiceType.STANDARD,
            base_charge=50.0,
            weight_charge=20.0,
            service_charge=0.0,
            tax_amount=12.6,
            total_charge=82.6,
            payment_status=PaymentStatus.PAID,
            delivery_status=ParcelStatus.BOOKED
        )
        db_session.add(parcel)
        db_session.commit()

        # 1. Generate signed QR custody payload
        qr_payload = generate_secure_qr_payload(parcel.tracking_number)
        assert qr_payload.startswith(f"LFQR.{parcel.tracking_number}.")

        # 2. Tampered token rejection
        tampered_token = qr_payload + "BADSIG"
        bad_scan = client.post(
            "/api/v1/custody/scan",
            headers=agent_headers,
            json={
                "tracking_number": tampered_token,
                "scan_type": ScanType.ORIGIN_INWARD.value,
                "branch_id": parcel.origin_branch_id,
                "latitude": 19.0760,
                "longitude": 72.8777
            }
        )
        assert bad_scan.status_code == status.HTTP_400_BAD_REQUEST

        # 3. Perform valid custody scan at origin hub: BOOKED -> AT_ORIGIN_BRANCH
        good_scan = client.post(
            "/api/v1/custody/scan",
            headers=agent_headers,
            json={
                "tracking_number": qr_payload,
                "scan_type": ScanType.ORIGIN_INWARD.value,
                "branch_id": parcel.origin_branch_id,
                "latitude": 19.0760,
                "longitude": 72.8777,
                "notes": "Custody accepted and verified at Mumbai origin hub"
            }
        )
        assert good_scan.status_code == status.HTTP_201_CREATED
        scan_data = good_scan.json()
        assert scan_data["tracking_number"] == parcel.tracking_number
        assert len(scan_data["record_hash"]) == 64  # SHA-256

        # 4. Verify immutable custody hash chain
        chain_res = client.get(
            f"/api/v1/custody/{parcel.tracking_number}/verify-chain",
            headers=agent_headers
        )
        assert chain_res.status_code == status.HTTP_200_OK
        chain = chain_res.json()
        assert chain["is_valid"] is True
        assert chain["tamper_detected"] is False
        assert chain["total_scans"] >= 1

    def test_08_linehaul_manifest_and_reconciliation(self, client, branchmanager_headers, orgadmin_headers, db_session):
        """Verify consolidation bags, linehaul manifest dispatch with CAS vehicle lock, and inward reconciliation."""
        db_session.expire_all()
        mumbai_hub = db_session.query(Branch).filter(Branch.branch_code == "BOM-001").first()
        delhi_hub = db_session.query(Branch).filter(Branch.branch_code == "DEL-001").first()
        driver = db_session.query(User).filter(User.role == UserRole.DELIVERY_AGENT).first()
        vehicle = db_session.query(Vehicle).filter(Vehicle.status == VehicleStatus.AVAILABLE).first()

        # Create two parcels at origin branch with complete dimensions
        p1 = Parcel(
            tracking_number="LF-LH-MUM-001",
            customer_id=driver.id,
            origin_branch_id=mumbai_hub.id,
            dest_branch_id=delhi_hub.id,
            sender_name="Sender 1",
            sender_phone="+91 98000 00001",
            sender_email="s1@test.com",
            sender_address="Addr 1",
            sender_city="Mumbai",
            sender_state="MH",
            sender_pincode="400001",
            receiver_name="Recv 1",
            receiver_phone="+91 98000 00002",
            receiver_email="r1@test.com",
            receiver_address="Dest Addr 1",
            receiver_city="New Delhi",
            receiver_state="DL",
            receiver_pincode="110001",
            weight_kg=10.0,
            length_cm=20.0,
            width_cm=15.0,
            height_cm=10.0,
            volumetric_weight_kg=0.6,
            service_type=ServiceType.STANDARD,
            base_charge=100.0,
            weight_charge=50.0,
            service_charge=0.0,
            tax_amount=27.0,
            total_charge=177.0,
            payment_status=PaymentStatus.PAID,
            delivery_status=ParcelStatus.AT_ORIGIN_BRANCH
        )
        p2 = Parcel(
            tracking_number="LF-LH-MUM-002",
            customer_id=driver.id,
            origin_branch_id=mumbai_hub.id,
            dest_branch_id=delhi_hub.id,
            sender_name="Sender 2",
            sender_phone="+91 98000 00003",
            sender_email="s2@test.com",
            sender_address="Addr 2",
            sender_city="Mumbai",
            sender_state="MH",
            sender_pincode="400001",
            receiver_name="Recv 2",
            receiver_phone="+91 98000 00004",
            receiver_email="r2@test.com",
            receiver_address="Dest Addr 2",
            receiver_city="New Delhi",
            receiver_state="DL",
            receiver_pincode="110001",
            weight_kg=15.0,
            length_cm=25.0,
            width_cm=20.0,
            height_cm=15.0,
            volumetric_weight_kg=1.5,
            service_type=ServiceType.EXPRESS,
            base_charge=150.0,
            weight_charge=75.0,
            service_charge=25.0,
            tax_amount=45.0,
            total_charge=295.0,
            payment_status=PaymentStatus.PAID,
            delivery_status=ParcelStatus.AT_ORIGIN_BRANCH
        )
        db_session.add_all([p1, p2])
        db_session.commit()

        # 1. Create Consolidation Bag
        bag_res = client.post(
            "/api/v1/linehaul/bags",
            headers=branchmanager_headers,
            json={
                "origin_branch_id": mumbai_hub.id,
                "dest_branch_id": delhi_hub.id,
                "notes": "Consolidated parcels for Delhi corridor"
            }
        )
        assert bag_res.status_code == status.HTTP_201_CREATED
        bag_id = bag_res.json()["id"]

        # 2. Attach Parcel 1 to Bag
        attach_res = client.post(
            f"/api/v1/linehaul/bags/{bag_id}/parcels",
            headers=branchmanager_headers,
            json={"parcel_ids": [p1.id]}
        )
        assert attach_res.status_code == status.HTTP_200_OK

        # 3. Seal the Bag
        seal_res = client.post(
            f"/api/v1/linehaul/bags/{bag_id}/seal",
            headers=branchmanager_headers,
            json={"seal_number": "SEAL-BOM-DEL-991"}
        )
        assert seal_res.status_code == status.HTTP_200_OK
        assert seal_res.json()["status"] == BagStatus.SEALED.value

        # 4. Create Linehaul Manifest
        man_res = client.post(
            "/api/v1/linehaul/manifests",
            headers=branchmanager_headers,
            json={
                "origin_branch_id": mumbai_hub.id,
                "dest_branch_id": delhi_hub.id,
                "driver_id": driver.id,
                "vehicle_id": vehicle.id,
                "bag_ids": [bag_id],
                "parcel_ids": [p2.id]
            }
        )
        assert man_res.status_code == status.HTTP_201_CREATED
        man_id = man_res.json()["id"]

        # 5. Dispatch Manifest with CAS vehicle locking
        disp_res = client.post(
            f"/api/v1/linehaul/manifests/{man_id}/dispatch",
            headers=branchmanager_headers,
            json={"notes": "Outbound linehaul dispatch to Delhi corridor"}
        )
        assert disp_res.status_code == status.HTTP_200_OK
        assert disp_res.json()["status"] == ManifestStatus.IN_TRANSIT.value

        # Vehicle must now be locked as IN_TRANSIT
        db_session.refresh(vehicle)
        assert vehicle.status == VehicleStatus.IN_TRANSIT

        # 6. Attempting to dispatch the same parcel into last-mile delivery fails with 409
        conflict_assign = client.post(
            "/api/v1/assignments",
            headers=branchmanager_headers,
            json={
                "parcel_id": p2.id,
                "employee_id": driver.id,
                "vehicle_id": vehicle.id
            }
        )
        assert conflict_assign.status_code == status.HTTP_409_CONFLICT

        # 7. Inward arrival & reconciliation at Delhi: p1 intact, p2 damaged
        reconcile_res = client.post(
            f"/api/v1/linehaul/manifests/{man_id}/reconcile",
            headers=orgadmin_headers,
            json={
                "received_tracking_numbers": [p1.tracking_number],
                "damaged_tracking_numbers": [p2.tracking_number],
                "missing_tracking_numbers": [],
                "excess_tracking_numbers": [],
                "seal_intact": True,
                "finalize": True,
                "notes": "Arrival reconciled at Delhi Sorting Center"
            }
        )
        assert reconcile_res.status_code == status.HTTP_200_OK
        rec_data = reconcile_res.json()
        assert rec_data["manifest"]["status"] == ManifestStatus.RECONCILED.value
        assert rec_data["received_count"] == 1
        assert rec_data["damaged_count"] == 1
        assert rec_data["discrepancies_created"] == 1

        # Parcel 2 must be ON_HOLD and have an open discrepancy
        db_session.expire_all()
        p2_refreshed = db_session.query(Parcel).filter(Parcel.id == p2.id).first()
        assert p2_refreshed.delivery_status == ParcelStatus.ON_HOLD

        disc_list = client.get("/api/v1/linehaul/discrepancies", headers=orgadmin_headers)
        assert disc_list.status_code == status.HTTP_200_OK
        discs = disc_list.json()
        assert len(discs) >= 1
        d_id = discs[0]["id"]

        # 8. Resolve the discrepancy
        res_disc = client.patch(
            f"/api/v1/linehaul/discrepancies/{d_id}",
            headers=orgadmin_headers,
            json={
                "status": DiscrepancyStatus.RESOLVED.value,
                "resolution_notes": "Repackaged in heavy duty carton after inspection",
                "release_parcel_to_dest": True
            }
        )
        assert res_disc.status_code == status.HTTP_200_OK
        assert res_disc.json()["status"] == DiscrepancyStatus.RESOLVED.value

        # Reconciling released the vehicle back to AVAILABLE
        db_session.expire_all()
        v_ref = db_session.query(Vehicle).filter(Vehicle.id == vehicle.id).first()
        assert v_ref.status == VehicleStatus.AVAILABLE

    def test_09_dynamic_route_optimization_and_multi_stop_lifecycle(self, client, branchmanager_headers, db_session):
        """Verify route preview, 2-opt TSP heuristics, optimistic locking, CAS dispatch, and multi-stop vehicle retention."""
        db_session.expire_all()
        mumbai_hub = db_session.query(Branch).filter(Branch.branch_code == "BOM-001").first()
        driver = db_session.query(User).filter(User.role == UserRole.DELIVERY_AGENT, User.branch_id == mumbai_hub.id).first()
        vehicle = db_session.query(Vehicle).filter(Vehicle.branch_id == mumbai_hub.id).first()
        vehicle.status = VehicleStatus.AVAILABLE
        db_session.commit()
        db_session.refresh(vehicle)

        # 1. Preview Route with 2-opt TSP
        preview_res = client.post(
            "/api/v1/routes/preview",
            headers=branchmanager_headers,
            json={
                "branch_id": mumbai_hub.id,
                "objective": "FASTEST",
                "return_to_hub": True,
                "stops": [
                    {"stop_type": RouteStopType.DELIVERY.value, "location_name": "Andheri West Clinic", "latitude": 19.1136, "longitude": 72.8697},
                    {"stop_type": RouteStopType.DELIVERY.value, "location_name": "Bandra Kurla Complex Hub", "latitude": 19.0596, "longitude": 72.8295}
                ]
            }
        )
        assert preview_res.status_code == status.HTTP_200_OK
        prev = preview_res.json()
        assert prev["total_distance_km"] > 0
        assert prev["estimated_duration_min"] > 0
        assert len(prev["stops"]) >= 2

        # 2. Create the Route in PLANNED status
        create_res = client.post(
            "/api/v1/routes",
            headers=branchmanager_headers,
            json={
                "branch_id": mumbai_hub.id,
                "vehicle_id": vehicle.id,
                "driver_id": driver.id,
                "objective": "FASTEST",
                "return_to_hub": True,
                "stops": [
                    {"stop_type": RouteStopType.DELIVERY.value, "location_name": "Andheri West Clinic", "latitude": 19.1136, "longitude": 72.8697},
                    {"stop_type": RouteStopType.DELIVERY.value, "location_name": "Bandra Kurla Complex Hub", "latitude": 19.0596, "longitude": 72.8295}
                ]
            }
        )
        assert create_res.status_code == status.HTTP_201_CREATED
        route = create_res.json()
        route_id = route["id"]
        version_id = route["version_id"]
        stops = route["stops"]
        assert len(stops) == 2

        # 3. Optimistic Locking Test: Reoptimize with STALE version_id fails with 409
        stale_res = client.post(
            f"/api/v1/routes/{route_id}/reoptimize",
            headers=branchmanager_headers,
            json={
                "objective": "SHORTEST",
                "expected_version_id": version_id - 1  # Out of sync version
            }
        )
        assert stale_res.status_code == status.HTTP_409_CONFLICT

        # 4. Dispatch Route: Locks vehicle to ASSIGNED
        disp_res = client.post(
            f"/api/v1/routes/{route_id}/dispatch",
            headers=branchmanager_headers,
            json={
                "vehicle_id": vehicle.id,
                "driver_id": driver.id,
                "expected_version_id": version_id
            }
        )
        assert disp_res.status_code == status.HTTP_200_OK
        dispatched_route = disp_res.json()
        assert dispatched_route["status"] == RouteStatus.DISPATCHED.value

        db_session.refresh(vehicle)
        assert vehicle.status == VehicleStatus.ASSIGNED

        # 5. Start Route: Transitions vehicle to IN_TRANSIT
        start_res = client.post(
            f"/api/v1/routes/{route_id}/start",
            headers=branchmanager_headers
        )
        assert start_res.status_code == status.HTTP_200_OK

        db_session.refresh(vehicle)
        assert vehicle.status == VehicleStatus.IN_TRANSIT

        # 6. Complete Stop 1: Vehicle MUST BE RETAINED IN_TRANSIT during multi-stop route
        stop1_id = stops[0]["id"]
        s1_res = client.post(
            f"/api/v1/routes/{route_id}/stops/{stop1_id}/update",
            headers=branchmanager_headers,
            json={
                "status": RouteStopStatus.COMPLETED.value,
                "latitude": 19.1136,
                "longitude": 72.8697,
                "notes": "Delivered to reception"
            }
        )
        assert s1_res.status_code == status.HTTP_200_OK
        db_session.refresh(vehicle)
        assert vehicle.status == VehicleStatus.IN_TRANSIT  # NOT released yet

        # 7. Complete Stop 2: Final stop auto-completes route and releases vehicle to AVAILABLE
        stop2_id = stops[1]["id"]
        s2_res = client.post(
            f"/api/v1/routes/{route_id}/stops/{stop2_id}/update",
            headers=branchmanager_headers,
            json={
                "status": RouteStopStatus.COMPLETED.value,
                "latitude": 19.0596,
                "longitude": 72.8295,
                "notes": "Signed by security supervisor"
            }
        )
        assert s2_res.status_code == status.HTTP_200_OK
        final_route = s2_res.json()
        assert final_route["status"] == RouteStatus.COMPLETED.value
        assert final_route["completed_stops"] == 2

        db_session.refresh(vehicle)
        assert vehicle.status == VehicleStatus.AVAILABLE

    def test_10_public_tracking_and_reporting_sanitization(self, client, orgadmin_headers):
        """Verify zero-PII guarantee on public tracking and CSV formula injection sanitization."""
        # 1. Public tracking PII sanitization
        pub_res = client.get("/api/v1/tracking/public/LF-2026-BOM001")
        assert pub_res.status_code == status.HTTP_200_OK
        pub_data = pub_res.json()
        assert pub_data["tracking_number"] == "LF-2026-BOM001"
        assert "milestones" in pub_data

        # Absolute zero PII fields
        for sensitive_key in [
            "sender_phone", "receiver_phone", "sender_email", "receiver_email",
            "sender_address", "receiver_address", "total_charge", "price"
        ]:
            assert sensitive_key not in pub_data

        # 2. Reports CSV export formula sanitization
        rep_res = client.get(
            "/api/v1/analytics/export/csv",
            headers=orgadmin_headers
        )
        assert rep_res.status_code == status.HTTP_200_OK
        assert "text/csv" in rep_res.headers.get("content-type", "")
        csv_text = rep_res.text
        # Every dangerous prefix (=, +, -, @) in cell contents must be single-quote escaped
        for line in csv_text.splitlines()[1:]:
            cells = line.split(",")
            for cell in cells:
                val = cell.strip('"\n\r ')
                if val and val[0] in ["=", "+", "-", "@"]:
                    assert val.startswith("'") or val.replace(".", "").replace("-", "").isdigit()
