from app.core.config import settings


def test_list_branches(client, customer_headers):
    response = client.get(f"{settings.API_V1_STR}/branches", headers=customer_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    branch_codes = [b["branch_code"] for b in data]
    assert "BOM-001" in branch_codes


def test_create_branch_as_orgadmin(client, orgadmin_headers):
    payload = {
        "branch_code": "HYD-001",
        "branch_name": "Hyderabad Aero Hub",
        "address": "Gachibowli Logistics Park",
        "pincode": "500032",
        "city": "Hyderabad",
        "state": "Telangana",
        "country": "India",
        "contact_email": "hyd.hub@logiflows.com",
        "contact_phone": "+91 98765 88888",
        "latitude": 17.3850,
        "longitude": 78.4867,
        "operating_status": "ACTIVE",
        "is_active": True
    }
    response = client.post(f"{settings.API_V1_STR}/branches", json=payload, headers=orgadmin_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["branch_code"] == "HYD-001"
    assert data["city"] == "Hyderabad"


def test_customer_cannot_create_branch(client, customer_headers):
    payload = {
        "branch_code": "PUN-001",
        "branch_name": "Pune Hub",
        "address": "Hinjewadi Phase 2",
        "pincode": "411057",
        "city": "Pune",
        "state": "Maharashtra",
        "contact_email": "pune@test.com",
        "contact_phone": "12345678"
    }
    response = client.post(f"{settings.API_V1_STR}/branches", json=payload, headers=customer_headers)
    assert response.status_code == 403

