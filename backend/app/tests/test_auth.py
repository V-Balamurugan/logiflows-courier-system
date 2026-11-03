from app.core.config import settings


def test_customer_registration(client):
    payload = {
        "email": "newuser@test.com",
        "password": "SecretPassword123!",
        "full_name": "Test Customer",
        "phone": "+91 9988776655",
        "company_name": "Test Logistics LLC",
        "default_address": "456 Test Boulevard, Mumbai"
    }
    response = client.post(f"{settings.API_V1_STR}/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@test.com"
    assert data["role"] == "CUSTOMER"
    assert data["full_name"] == "Test Customer"


def test_login_success(client):
    payload = {
        "email": settings.FIRST_SUPERADMIN_EMAIL,
        "password": settings.FIRST_SUPERADMIN_PASSWORD
    }
    response = client.post(f"{settings.API_V1_STR}/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["role"] == "SUPER_ADMIN"


def test_login_invalid_password(client):
    payload = {
        "email": settings.FIRST_SUPERADMIN_EMAIL,
        "password": "WrongPassword123!"
    }
    response = client.post(f"{settings.API_V1_STR}/auth/login", json=payload)
    assert response.status_code == 401


def test_get_current_profile(client, superadmin_headers):
    response = client.get(f"{settings.API_V1_STR}/auth/me", headers=superadmin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == settings.FIRST_SUPERADMIN_EMAIL.lower()
    assert data["role"] == "SUPER_ADMIN"


def test_token_refresh(client):
    login_resp = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={
            "email": settings.FIRST_SUPERADMIN_EMAIL,
            "password": settings.FIRST_SUPERADMIN_PASSWORD
        }
    )
    refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()

