import pytest
from app.models.organization import Organization
from app.models.branch import Branch
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.parcel import Parcel
from app.models.enums import UserRole, OperatingStatus, VehicleType, VehicleStatus, ServiceType, PaymentStatus, ParcelStatus
from app.core.security import create_access_token, get_password_hash


@pytest.fixture
def multi_tenant_data(db_session):
    # Org 1
    org1 = db_session.query(Organization).filter(Organization.code == "ORG1").first()
    if not org1:
        org1 = Organization(name="Organization One", code="ORG1", contact_email="contact@org1.com", is_active=True)
        db_session.add(org1)
        db_session.flush()

    # Org 2
    org2 = db_session.query(Organization).filter(Organization.code == "ORG2").first()
    if not org2:
        org2 = Organization(name="Organization Two", code="ORG2", contact_email="contact@org2.com", is_active=True)
        db_session.add(org2)
        db_session.flush()

    # Branches in Org 1
    branch1a = db_session.query(Branch).filter(Branch.branch_code == "BR1A").first()
    if not branch1a:
        branch1a = Branch(
            organization_id=org1.id,
            branch_code="BR1A",
            branch_name="Branch 1A",
            address="100 Org1 St",
            pincode="100001",
            city="City One",
            state="State One",
            country="India",
            contact_email="branch1a@org1.com",
            contact_phone="9988771122",
            operating_status=OperatingStatus.ACTIVE,
            is_active=True
        )
        db_session.add(branch1a)
        db_session.flush()

    branch1b = db_session.query(Branch).filter(Branch.branch_code == "BR1B").first()
    if not branch1b:
        branch1b = Branch(
            organization_id=org1.id,
            branch_code="BR1B",
            branch_name="Branch 1B",
            address="101 Org1 St",
            pincode="100002",
            city="City One B",
            state="State One",
            country="India",
            contact_email="branch1b@org1.com",
            contact_phone="9988771123",
            operating_status=OperatingStatus.ACTIVE,
            is_active=True
        )
        db_session.add(branch1b)
        db_session.flush()

    # Branches in Org 2
    branch2a = db_session.query(Branch).filter(Branch.branch_code == "BR2A").first()
    if not branch2a:
        branch2a = Branch(
            organization_id=org2.id,
            branch_code="BR2A",
            branch_name="Branch 2A",
            address="200 Org2 Ave",
            pincode="200001",
            city="City Two",
            state="State Two",
            country="India",
            contact_email="branch2a@org2.com",
            contact_phone="9988772211",
            operating_status=OperatingStatus.ACTIVE,
            is_active=True
        )
        db_session.add(branch2a)
        db_session.flush()

    # Users in Org 1
    admin1 = db_session.query(User).filter(User.email == "admin@org1.com").first()
    if not admin1:
        admin1 = User(
            email="admin@org1.com",
            hashed_password=get_password_hash("Org1Password123!"),
            full_name="Org1 Admin",
            role=UserRole.ORG_ADMIN,
            organization_id=org1.id,
            is_active=True
        )
        db_session.add(admin1)
        db_session.flush()

    agent1 = db_session.query(User).filter(User.email == "agent@org1.com").first()
    if not agent1:
        agent1 = User(
            email="agent@org1.com",
            hashed_password=get_password_hash("Agent1Password123!"),
            full_name="Org1 Agent",
            role=UserRole.DELIVERY_AGENT,
            organization_id=org1.id,
            branch_id=branch1a.id,
            is_active=True
        )
        db_session.add(agent1)
        db_session.flush()

    # Users in Org 2
    admin2 = db_session.query(User).filter(User.email == "admin@org2.com").first()
    if not admin2:
        admin2 = User(
            email="admin@org2.com",
            hashed_password=get_password_hash("Org2Password123!"),
            full_name="Org2 Admin",
            role=UserRole.ORG_ADMIN,
            organization_id=org2.id,
            is_active=True
        )
        db_session.add(admin2)
        db_session.flush()

    agent2 = db_session.query(User).filter(User.email == "agent@org2.com").first()
    if not agent2:
        agent2 = User(
            email="agent@org2.com",
            hashed_password=get_password_hash("Agent2Password123!"),
            full_name="Org2 Agent",
            role=UserRole.DELIVERY_AGENT,
            organization_id=org2.id,
            branch_id=branch2a.id,
            is_active=True
        )
        db_session.add(agent2)
        db_session.flush()

    # Customers
    cust1 = db_session.query(User).filter(User.email == "cust1@customer.com").first()
    if not cust1:
        cust1 = User(
            email="cust1@customer.com",
            hashed_password=get_password_hash("Cust1Password123!"),
            full_name="Customer One",
            role=UserRole.CUSTOMER,
            is_active=True
        )
        db_session.add(cust1)
        db_session.flush()

    cust2 = db_session.query(User).filter(User.email == "cust2@customer.com").first()
    if not cust2:
        cust2 = User(
            email="cust2@customer.com",
            hashed_password=get_password_hash("Cust2Password123!"),
            full_name="Customer Two",
            role=UserRole.CUSTOMER,
            is_active=True
        )
        db_session.add(cust2)
        db_session.flush()

    # Vehicle in Org 1
    veh1 = db_session.query(Vehicle).filter(Vehicle.vehicle_number == "ORG1-VAN-01").first()
    if not veh1:
        veh1 = Vehicle(
            organization_id=org1.id,
            branch_id=branch1a.id,
            vehicle_number="ORG1-VAN-01",
            vehicle_type=VehicleType.VAN,
            status=VehicleStatus.AVAILABLE,
            is_active=True
        )
        db_session.add(veh1)
        db_session.flush()

    # Parcel in Org 1
    p1 = db_session.query(Parcel).filter(Parcel.tracking_number == "LF-2026-ORG1-01").first()
    if not p1:
        p1 = Parcel(
            tracking_number="LF-2026-ORG1-01",
            customer_id=cust1.id,
            origin_branch_id=branch1a.id,
            dest_branch_id=branch1b.id,
            sender_name="Sender 1",
            sender_phone="9876543210",
            sender_address="Addr 1",
            sender_city="City One",
            sender_state="State One",
            sender_pincode="100001",
            receiver_name="Receiver 1",
            receiver_phone="9876543211",
            receiver_address="Addr 1B",
            receiver_city="City One B",
            receiver_state="State One",
            receiver_pincode="100002",
            weight_kg=2.5,
            length_cm=10.0,
            width_cm=10.0,
            height_cm=10.0,
            volumetric_weight_kg=0.2,
            service_type=ServiceType.STANDARD,
            base_charge=50.0,
            total_charge=100.0,
            payment_status=PaymentStatus.PAID,
            delivery_status=ParcelStatus.BOOKED
        )
        db_session.add(p1)
        db_session.flush()

    db_session.commit()

    return {
        "org1": org1,
        "org2": org2,
        "branch1a": branch1a,
        "branch2a": branch2a,
        "admin1": admin1,
        "admin2": admin2,
        "agent1": agent1,
        "agent2": agent2,
        "cust1": cust1,
        "cust2": cust2,
        "veh1": veh1,
        "parcel1": p1,
    }


def auth_headers(user):
    tok = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {tok}"}


def test_cross_tenant_branch_isolation_returns_404(client, multi_tenant_data):
    """AC1: Org Admin B accessing Branch A must receive 404 (anti-leakage)."""
    admin2_hdrs = auth_headers(multi_tenant_data["admin2"])
    branch1_id = multi_tenant_data["branch1a"].id

    # GET
    res_get = client.get(f"/api/v1/branches/{branch1_id}", headers=admin2_hdrs)
    assert res_get.status_code == 404

    # PUT
    res_put = client.put(f"/api/v1/branches/{branch1_id}", json={"branch_name": "Hacked Branch"}, headers=admin2_hdrs)
    assert res_put.status_code == 404

    # DELETE
    res_del = client.delete(f"/api/v1/branches/{branch1_id}", headers=admin2_hdrs)
    assert res_del.status_code == 404


def test_cross_tenant_parcel_isolation_returns_404(client, multi_tenant_data):
    """AC1: Org Admin B or Customer B accessing Parcel A must receive 404."""
    admin2_hdrs = auth_headers(multi_tenant_data["admin2"])
    cust2_hdrs = auth_headers(multi_tenant_data["cust2"])
    tracking_no = multi_tenant_data["parcel1"].tracking_number

    # Org Admin 2 cannot read Parcel 1
    res_admin = client.get(f"/api/v1/parcels/{tracking_no}", headers=admin2_hdrs)
    assert res_admin.status_code == 404

    # Org Admin 2 cannot download label for Parcel 1
    res_label = client.get(f"/api/v1/parcels/{tracking_no}/label", headers=admin2_hdrs)
    assert res_label.status_code == 404

    # Customer 2 cannot read Customer 1's parcel
    res_cust = client.get(f"/api/v1/parcels/{tracking_no}", headers=cust2_hdrs)
    assert res_cust.status_code == 404

    # Customer 2 cannot cancel Customer 1's parcel
    res_cancel = client.post(
        f"/api/v1/parcels/{tracking_no}/cancel",
        json={"cancellation_reason": "Malicious cancellation"},
        headers=cust2_hdrs
    )
    assert res_cancel.status_code == 404


def test_cross_tenant_vehicle_isolation_returns_404(client, multi_tenant_data):
    """AC1: Org Admin B accessing Vehicle A must receive 404."""
    admin2_hdrs = auth_headers(multi_tenant_data["admin2"])
    veh1_id = multi_tenant_data["veh1"].id

    # GET
    res_get = client.get(f"/api/v1/vehicles/{veh1_id}", headers=admin2_hdrs)
    assert res_get.status_code == 404

    # PUT
    res_put = client.put(f"/api/v1/vehicles/{veh1_id}", json={"model": "Tampered Model"}, headers=admin2_hdrs)
    assert res_put.status_code == 404


def test_cross_tenant_employee_isolation_returns_404(client, multi_tenant_data):
    """AC1: Org Admin B accessing Employee A must receive 404."""
    admin2_hdrs = auth_headers(multi_tenant_data["admin2"])
    agent1_id = multi_tenant_data["agent1"].id

    # GET employee profile
    res_emp = client.get(f"/api/v1/employees/{agent1_id}", headers=admin2_hdrs)
    assert res_emp.status_code == 404

    # GET employee workload
    res_workload = client.get(f"/api/v1/employees/{agent1_id}/workload", headers=admin2_hdrs)
    assert res_workload.status_code == 404


def test_cross_tenant_custody_and_tracking_returns_404(client, multi_tenant_data):
    """AC1: Agent B cannot scan, update, or view custody history of Parcel A."""
    agent2_hdrs = auth_headers(multi_tenant_data["agent2"])
    tracking_no = multi_tenant_data["parcel1"].tracking_number

    # Scan parcel from another tenant
    res_scan = client.post(
        "/api/v1/custody/scan",
        json={"tracking_number": tracking_no, "scan_type": "ORIGIN_INWARD"},
        headers=agent2_hdrs
    )
    assert res_scan.status_code == 404

    # View custody history
    res_history = client.get(f"/api/v1/custody/{tracking_no}/history", headers=agent2_hdrs)
    assert res_history.status_code == 404

    # Update tracking event
    res_update = client.post(
        f"/api/v1/tracking/{tracking_no}/update",
        json={"status": "IN_TRANSIT", "location_name": "Unauthorized Location"},
        headers=agent2_hdrs
    )
    assert res_update.status_code == 404


def test_cross_tenant_analytics_export_isolation(client, multi_tenant_data):
    """AC1 & DEF-C1: CSV export by Org Admin 2 must NOT include Org 1 parcels."""
    admin2_hdrs = auth_headers(multi_tenant_data["admin2"])
    tracking_no = multi_tenant_data["parcel1"].tracking_number

    res_csv = client.get("/api/v1/analytics/export/csv", headers=admin2_hdrs)
    assert res_csv.status_code == 200
    assert tracking_no not in res_csv.text


def test_customer_isolation_on_customer_endpoints(client, multi_tenant_data):
    """AC1 & DEF-M2: Customer 2 accessing Customer 1 profile returns 404."""
    cust2_hdrs = auth_headers(multi_tenant_data["cust2"])
    cust1_id = multi_tenant_data["cust1"].id

    res_cust = client.get(f"/api/v1/customers/{cust1_id}", headers=cust2_hdrs)
    assert res_cust.status_code == 404
