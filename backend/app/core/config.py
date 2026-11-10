from typing import List, Union
from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


class Settings(BaseSettings):
    PROJECT_NAME: str = "LogiFlows Courier Management System"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    
    SECRET_KEY: str = "logiflows-production-super-secret-key-32-chars-minimum-needed-for-jwt-signing"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    DATABASE_URL: str = "sqlite:///./logiflows.db"
    
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]
    
    FIRST_SUPERADMIN_EMAIL: str = "superadmin@logiflows.com"
    FIRST_SUPERADMIN_PASSWORD: str = "SuperAdmin@LogiFlows2026!"
    
    RATE_LIMIT_MAX_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        elif isinstance(v, list):
            return v
        return []

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        env = (self.ENVIRONMENT or "").strip().lower()
        if env == "production":
            insecure_defaults = [
                "logiflows-production-super-secret-key-32-chars-minimum-needed-for-jwt-signing",
                "secret",
                "changeme",
                "admin",
                "password",
                "12345678",
                "default",
                "<SET_ME>",
            ]
            if not self.SECRET_KEY or self.SECRET_KEY in insecure_defaults or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "Production environment requires an explicit, secure SECRET_KEY of at least 32 characters set via environment."
                )
            if "*" in self.CORS_ORIGINS:
                raise ValueError("Production environment does not allow wildcard '*' in CORS_ORIGINS.")
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError("Production environment requires PostgreSQL; SQLite is not allowed.")
        return self


settings = Settings()

