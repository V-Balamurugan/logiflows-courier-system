from datetime import timedelta
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User
from app.models.enums import UserRole


def test_reject_refresh_token_as_access_token(client, db_session):
    """AC4: Using a refresh token for authenticated endpoint must return 401."""
    admin = db_session.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
    refresh_token = create_refresh_token(subject=admin.id)
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert response.status_code == 401


def test_reject_expired_access_token(client, db_session):
    """AC4: Expired access token must return 401."""
    admin = db_session.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
    expired_token = create_access_token(
        subject=admin.id,
        role=admin.role.value,
        expires_delta=timedelta(seconds=-10)
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401


def test_reject_tampered_token(client, db_session):
    """AC4: Tampered signature or invalid token string must return 401."""
    admin = db_session.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
    valid_token = create_access_token(subject=admin.id, role=admin.role.value)
    tampered_token = valid_token[:-4] + "abcd"
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"}
    )
    assert response.status_code == 401


def test_logout_revokes_access_token(client, db_session):
    """AC4: Logging out must blacklist the token in the revocation store."""
    admin = db_session.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
    token = create_access_token(subject=admin.id, role=admin.role.value)
    
    # Verify token works initially
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200

    # Call logout
    logout_resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_resp.status_code == 200
    assert "revoked" in logout_resp.json()["message"].lower()

    # Calling /me with revoked token must now be rejected
    revoked_check = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert revoked_check.status_code == 401
    assert "revoked" in revoked_check.json()["detail"].lower()


def test_refresh_token_rotation_and_single_use(client, db_session):
    """AC4: Refresh token rotation ensures single-use. Replay returns 401."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin@logiflows.com", "password": "SuperAdmin@LogiFlows2026!"}
    )
    assert login_resp.status_code == 200
    initial_tokens = login_resp.json()
    first_refresh = initial_tokens["refresh_token"]

    # First exchange succeeds and rotates refresh token
    rotate_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh}
    )
    assert rotate_resp.status_code == 200
    rotated_tokens = rotate_resp.json()
    assert rotated_tokens["access_token"] != initial_tokens["access_token"]
    assert rotated_tokens["refresh_token"] != first_refresh

    # Attempting to replay the old refresh token must be rejected with 401
    replay_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh}
    )
    assert replay_resp.status_code == 401
    assert "already been used or revoked" in replay_resp.json()["detail"].lower()
