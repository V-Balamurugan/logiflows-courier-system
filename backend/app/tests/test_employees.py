from app.core.config import settings


def test_list_employees(client, branchmanager_headers):
    response = client.get(f"{settings.API_V1_STR}/employees", headers=branchmanager_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(emp["role"] == "DELIVERY_AGENT" for emp in data)


def test_create_delivery_agent(client, branchmanager_headers):
    payload = {
        "email": "agent.amit@logiflows.com",
        "password": "Password@123",
        "full_name": "Amit Kumar",
        "phone": "+91 91234 56789",
        "role": "DELIVERY_AGENT"
    }
    response = client.post(f"{settings.API_V1_STR}/employees", json=payload, headers=branchmanager_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "agent.amit@logiflows.com"
    assert data["role"] == "DELIVERY_AGENT"


def test_employee_workload(client, branchmanager_headers):
    # Fetch existing agent
    emps = client.get(f"{settings.API_V1_STR}/employees", headers=branchmanager_headers).json()
    agent = next(e for e in emps if e["role"] == "DELIVERY_AGENT")

    response = client.get(f"{settings.API_V1_STR}/employees/{agent['id']}/workload", headers=branchmanager_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["employee_id"] == agent["id"]
    assert "active_assignments_count" in data

