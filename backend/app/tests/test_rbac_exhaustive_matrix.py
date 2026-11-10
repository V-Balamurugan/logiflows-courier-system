import pytest
from app.core.config import settings
from app.core.security import create_access_token
from app.models.enums import UserRole
from app.models.user import User


@pytest.fixture
def agent_headers(db_session):
    agent = db_session.query(User).filter(User.role == UserRole.DELIVERY_AGENT).first()
    assert agent is not None
    token = create_access_token(subject=agent.id, role=agent.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def manager_headers(db_session):
    mgr = db_session.query(User).filter(User.role == UserRole.BRANCH_MANAGER).first()
    assert mgr is not None
    token = create_access_token(subject=mgr.id, role=mgr.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def customer_headers(db_session):
    cust = db_session.query(User).filter(User.role == UserRole.CUSTOMER).first()
    assert cust is not None
    token = create_access_token(subject=cust.id, role=cust.role.value)
    return {"Authorization": f"Bearer {token}"}


# Sample valid payloads to avoid 422 Unprocessable Entity during RBAC check
SAMPLE_ORG = {"name": "Audit Org", "code": "AUDIT-ORG-01", "contact_email": "audit@org.com"}
SAMPLE_BRANCH = {
    "organization_id": 1,
    "branch_code": "AUD-BR-01",
    "branch_name": "Audit Branch",
    "address": "123 Street",
    "pincode": "400001",
    "city": "Mumbai",
    "state": "Maharashtra",
    "country": "India",
    "contact_email": "br@audit.com",
    "contact_phone": "9876543210"
}
SAMPLE_EMPLOYEE = {
    "email": "audit.emp@logiflows.com",
    "password": "Password@Audit123",
    "full_name": "Audit Employee",
    "role": "DELIVERY_AGENT",
    "branch_id": 1
}
SAMPLE_VEHICLE = {
    "organization_id": 1,
    "vehicle_number": "MH01AU9999",
    "vehicle_type": "VAN",
    "max_weight_kg": 500.0
}
SAMPLE_ASSIGNMENT = {
    "parcel_id": 1,
    "employee_id": 1,
    "assignment_type": "LAST_MILE"
}
SAMPLE_SCAN = {
    "parcel_id": 1,
    "scan_type": "ORIGIN_INWARD",
    "qr_token": "audit-token"
}
SAMPLE_TRACKING = {
    "status": "IN_TRANSIT",
    "location_name": "Audit Hub"
}


def test_unauthenticated_requests_receive_401(client):
    """Verify that unauthenticated requests to protected endpoints return 401 Unauthorized."""
    get_endpoints = [
        f"{settings.API_V1_STR}/auth/me",
        f"{settings.API_V1_STR}/organizations",
        f"{settings.API_V1_STR}/employees",
        f"{settings.API_V1_STR}/customers",
        f"{settings.API_V1_STR}/vehicles",
        f"{settings.API_V1_STR}/parcels",
        f"{settings.API_V1_STR}/assignments",
        f"{settings.API_V1_STR}/analytics/dashboard",
        f"{settings.API_V1_STR}/analytics/export/csv",
    ]
    for path in get_endpoints:
        res = client.get(path)
        assert res.status_code == 401, f"Expected 401 for GET {path}, got {res.status_code}"

    post_endpoints = [
        (f"{settings.API_V1_STR}/auth/logout", {}),
        (f"{settings.API_V1_STR}/organizations", SAMPLE_ORG),
        (f"{settings.API_V1_STR}/branches", SAMPLE_BRANCH),
        (f"{settings.API_V1_STR}/employees", SAMPLE_EMPLOYEE),
        (f"{settings.API_V1_STR}/vehicles", SAMPLE_VEHICLE),
        (f"{settings.API_V1_STR}/assignments", SAMPLE_ASSIGNMENT),
        (f"{settings.API_V1_STR}/custody/scan", SAMPLE_SCAN),
        (f"{settings.API_V1_STR}/tracking/LOGI-TEST/update", SAMPLE_TRACKING),
    ]
    for path, payload in post_endpoints:
        res = client.post(path, json=payload)
        assert res.status_code == 401, f"Expected 401 for POST {path}, got {res.status_code}"


def test_customer_denied_from_all_staff_and_admin_endpoints(client, customer_headers):
    """Verify that customers receive 403 Forbidden for staff, manager, and admin operations."""
    forbidden_gets = [
        f"{settings.API_V1_STR}/organizations",
        f"{settings.API_V1_STR}/employees",
        f"{settings.API_V1_STR}/employees/1/workload",
        f"{settings.API_V1_STR}/customers",
        f"{settings.API_V1_STR}/vehicles",
        f"{settings.API_V1_STR}/assignments",
        f"{settings.API_V1_STR}/custody/LOGI-12345/history",
        f"{settings.API_V1_STR}/analytics/export/csv",
    ]
    for path in forbidden_gets:
        res = client.get(path, headers=customer_headers)
        assert res.status_code == 403, f"Expected 403 for CUSTOMER on GET {path}, got {res.status_code}"

    forbidden_posts = [
        (f"{settings.API_V1_STR}/organizations", SAMPLE_ORG),
        (f"{settings.API_V1_STR}/branches", SAMPLE_BRANCH),
        (f"{settings.API_V1_STR}/employees", SAMPLE_EMPLOYEE),
        (f"{settings.API_V1_STR}/vehicles", SAMPLE_VEHICLE),
        (f"{settings.API_V1_STR}/assignments", SAMPLE_ASSIGNMENT),
        (f"{settings.API_V1_STR}/custody/scan", SAMPLE_SCAN),
        (f"{settings.API_V1_STR}/tracking/LOGI-TEST/update", SAMPLE_TRACKING),
    ]
    for path, payload in forbidden_posts:
        res = client.post(path, json=payload, headers=customer_headers)
        assert res.status_code == 403, f"Expected 403 for CUSTOMER on POST {path}, got {res.status_code}"

    # PUT branch
    res = client.put(f"{settings.API_V1_STR}/branches/1", json={"branch_name": "X"}, headers=customer_headers)
    assert res.status_code == 403


def test_delivery_agent_denied_from_administrative_endpoints(client, agent_headers):
    """Verify that Delivery Agents receive 403 Forbidden for manager and admin endpoints."""
    forbidden_gets = [
        f"{settings.API_V1_STR}/organizations",
        f"{settings.API_V1_STR}/employees",
        f"{settings.API_V1_STR}/employees/1/workload",
    ]
    for path in forbidden_gets:
        res = client.get(path, headers=agent_headers)
        assert res.status_code == 403, f"Expected 403 for DELIVERY_AGENT on GET {path}, got {res.status_code}"

    forbidden_posts = [
        (f"{settings.API_V1_STR}/organizations", SAMPLE_ORG),
        (f"{settings.API_V1_STR}/branches", SAMPLE_BRANCH),
        (f"{settings.API_V1_STR}/employees", SAMPLE_EMPLOYEE),
        (f"{settings.API_V1_STR}/vehicles", SAMPLE_VEHICLE),
        (f"{settings.API_V1_STR}/assignments", SAMPLE_ASSIGNMENT),
    ]
    for path, payload in forbidden_posts:
        res = client.post(path, json=payload, headers=agent_headers)
        assert res.status_code == 403, f"Expected 403 for DELIVERY_AGENT on POST {path}, got {res.status_code}"

    res = client.put(f"{settings.API_V1_STR}/branches/1", json={"branch_name": "X"}, headers=agent_headers)
    assert res.status_code == 403


def test_branch_manager_denied_from_orgadmin_and_superadmin_endpoints(client, manager_headers):
    """Verify that Branch Managers cannot execute Org Admin or Super Admin actions."""
    forbidden_gets = [
        f"{settings.API_V1_STR}/organizations",
    ]
    for path in forbidden_gets:
        res = client.get(path, headers=manager_headers)
        assert res.status_code == 403, f"Expected 403 for BRANCH_MANAGER on GET {path}, got {res.status_code}"

    forbidden_posts = [
        (f"{settings.API_V1_STR}/organizations", SAMPLE_ORG),
        (f"{settings.API_V1_STR}/branches", SAMPLE_BRANCH),
    ]
    for path, payload in forbidden_posts:
        res = client.post(path, json=payload, headers=manager_headers)
        assert res.status_code == 403, f"Expected 403 for BRANCH_MANAGER on POST {path}, got {res.status_code}"

    res = client.put(f"{settings.API_V1_STR}/branches/1", json={"branch_name": "X"}, headers=manager_headers)
    assert res.status_code == 403


def test_org_admin_denied_from_superadmin_endpoints(client, orgadmin_headers):
    """Verify that Org Admins cannot manage system organizations (Super Admin only)."""
    res_get = client.get(f"{settings.API_V1_STR}/organizations", headers=orgadmin_headers)
    assert res_get.status_code == 403, f"Expected 403 for ORG_ADMIN on GET /organizations, got {res_get.status_code}"

    res_post = client.post(f"{settings.API_V1_STR}/organizations", json=SAMPLE_ORG, headers=orgadmin_headers)
    assert res_post.status_code == 403, f"Expected 403 for ORG_ADMIN on POST /organizations, got {res_post.status_code}"
