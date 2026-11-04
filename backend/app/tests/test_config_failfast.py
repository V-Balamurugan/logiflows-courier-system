import pytest
from app.core.config import Settings


def test_production_fails_with_default_secret():
    """AC5: In production, default development secret must fail fast."""
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="logiflows-production-super-secret-key-32-chars-minimum-needed-for-jwt-signing",
            DATABASE_URL="postgresql://user:pass@localhost:5432/db",
            CORS_ORIGINS=["https://logiflows.com"]
        )


def test_production_fails_with_short_secret():
    """AC5: In production, secret shorter than 32 characters must fail fast."""
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="too-short-secret",
            DATABASE_URL="postgresql://user:pass@localhost:5432/db",
            CORS_ORIGINS=["https://logiflows.com"]
        )


def test_production_fails_with_wildcard_cors():
    """AC7: In production, wildcard CORS origin must fail fast."""
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a-very-strong-production-secret-key-32-chars-min",
            DATABASE_URL="postgresql://user:pass@localhost:5432/db",
            CORS_ORIGINS=["*"]
        )


def test_production_fails_with_sqlite():
    """AC6: In production, SQLite database URL must fail fast."""
    with pytest.raises(ValueError, match="SQLite"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a-very-strong-production-secret-key-32-chars-min",
            DATABASE_URL="sqlite:///./prod.db",
            CORS_ORIGINS=["https://logiflows.com"]
        )


def test_production_succeeds_with_valid_settings():
    """Production mode succeeds when all security and database criteria are satisfied."""
    cfg = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a-very-strong-production-secret-key-32-chars-min",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        CORS_ORIGINS=["https://logiflows.com"]
    )
    assert cfg.ENVIRONMENT == "production"
    assert "https://logiflows.com" in cfg.CORS_ORIGINS
