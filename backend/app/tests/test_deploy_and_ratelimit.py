import pytest
from app.core.config import settings
from app.middleware.rate_limit import RateLimitMiddleware
from fastapi import FastAPI, Request
from starlette.testclient import TestClient
from starlette.responses import JSONResponse


def test_deep_health_check_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "service" in data


def test_rate_limiter_middleware_blocks_after_threshold():
    # Create isolated test app with active rate limiter (max 3 requests)
    test_app = FastAPI()
    test_app.add_middleware(RateLimitMiddleware, max_requests=3, window_seconds=60)

    @test_app.post(f"{settings.API_V1_STR}/auth/login")
    def dummy_login():
        return {"msg": "ok"}

    # Temporarily set environment to production to activate limiter
    orig_env = settings.ENVIRONMENT
    settings.ENVIRONMENT = "production"
    try:
        with TestClient(test_app) as tc:
            # 3 allowed requests
            for _ in range(3):
                r = tc.post(f"{settings.API_V1_STR}/auth/login")
                assert r.status_code == 200

            # 4th request must be throttled with 429 Too Many Requests
            r_blocked = tc.post(f"{settings.API_V1_STR}/auth/login")
            assert r_blocked.status_code == 429
            assert "Retry-After" in r_blocked.headers
            assert "Too many requests" in r_blocked.json()["detail"]
    finally:
        settings.ENVIRONMENT = orig_env
