from fastapi import FastAPI, Depends, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from contextlib import asynccontextmanager

from app.core.config import settings
from app.database.session import engine, Base, SessionLocal, get_db
from app.database.init_db import init_db
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import (
    auth,
    organizations,
    branches,
    employees,
    customers,
    parcels,
    assignments,
    vehicles,
    tracking,
    custody,
    analytics,
    linehaul,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema lifecycle is managed via Alembic migrations.
    # Demo seeding is executed via CLI: python -m app.cli seed-demo
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Courier & Logistics Management System API supporting multi-tenant organizations, parcel booking, QR custody, fleet management, and real-time shipment tracking.",
    version="1.0.0",
    lifespan=lifespan,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Rate Limiting Middleware
app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.RATE_LIMIT_MAX_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(organizations.router, prefix=settings.API_V1_STR)
app.include_router(branches.router, prefix=settings.API_V1_STR)
app.include_router(employees.router, prefix=settings.API_V1_STR)
app.include_router(customers.router, prefix=settings.API_V1_STR)
app.include_router(parcels.router, prefix=settings.API_V1_STR)
app.include_router(assignments.router, prefix=settings.API_V1_STR)
app.include_router(vehicles.router, prefix=settings.API_V1_STR)
app.include_router(tracking.router, prefix=settings.API_V1_STR)
app.include_router(custody.router, prefix=settings.API_V1_STR)
app.include_router(analytics.router, prefix=settings.API_V1_STR)
app.include_router(linehaul.router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Health"])
def root_status():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "docs_url": "/docs"
    }


@app.get("/health", tags=["Health"])
def health_check(response: Response, db: Session = Depends(get_db)):
    """Active deep health check validating database connectivity."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": settings.PROJECT_NAME,
        "database": db_status,
        "environment": settings.ENVIRONMENT
    }
