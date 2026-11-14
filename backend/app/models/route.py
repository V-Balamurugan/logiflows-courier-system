"""SQLAlchemy models for Phase 15 dynamic route plans and ordered stops."""
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship

from app.database.session import Base
from app.models.enums import RouteObjective, RouteStatus, RouteStopStatus, RouteStopType


class DeliveryRoute(Base):
    """Optimized multi-stop delivery/pickup route anchored to a branch depot."""

    __tablename__ = "delivery_routes"
    __table_args__ = (
        Index(
            "uq_active_vehicle_route",
            "vehicle_id",
            unique=True,
            postgresql_where=text("vehicle_id IS NOT NULL AND is_active_dispatch IS TRUE"),
            sqlite_where=text("vehicle_id IS NOT NULL AND is_active_dispatch = 1"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    route_code = Column(String(64), unique=True, index=True, nullable=False)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id = Column(
        Integer, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    vehicle_id = Column(
        Integer, ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    driver_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status = Column(SQLEnum(RouteStatus), default=RouteStatus.PLANNED, nullable=False, index=True)
    is_active_dispatch = Column(Boolean, default=False, nullable=False)
    optimization_objective = Column(
        SQLEnum(RouteObjective), default=RouteObjective.FASTEST, nullable=False
    )
    provider_used = Column(String(50), default="local_fallback", nullable=False)
    is_fallback = Column(Boolean, default=False, nullable=False)
    fallback_reason = Column(String(255), nullable=True)
    return_to_hub = Column(Boolean, default=True, nullable=False)

    start_latitude = Column(Float, nullable=True)
    start_longitude = Column(Float, nullable=True)
    total_distance_km = Column(Float, default=0.0, nullable=False)
    baseline_distance_km = Column(Float, default=0.0, nullable=False)
    distance_saved_km = Column(Float, default=0.0, nullable=False)
    estimated_duration_min = Column(Float, default=0.0, nullable=False)
    total_weight_kg = Column(Float, default=0.0, nullable=False)
    total_stops = Column(Integer, default=0, nullable=False)
    completed_stops = Column(Integer, default=0, nullable=False)
    route_geometry = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    version_id = Column(Integer, default=1, nullable=False)

    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    dispatched_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __mapper_args__ = {"version_id_col": version_id}

    organization = relationship("Organization")
    branch = relationship("Branch")
    vehicle = relationship("Vehicle")
    driver = relationship("User", foreign_keys=[driver_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    stops = relationship(
        "RouteStop",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="RouteStop.sequence_order.asc()",
    )


class RouteStop(Base):
    """Individual stop along a DeliveryRoute with sequence order, coordinates, and ETA."""

    __tablename__ = "route_stops"
    __table_args__ = (
        Index(
            "uq_active_parcel_on_route",
            "parcel_id",
            unique=True,
            postgresql_where=text("parcel_id IS NOT NULL AND is_active IS TRUE"),
            sqlite_where=text("parcel_id IS NOT NULL AND is_active = 1"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(
        Integer, ForeignKey("delivery_routes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parcel_id = Column(
        Integer, ForeignKey("parcels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assignment_id = Column(
        Integer,
        ForeignKey("delivery_assignments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sequence_order = Column(Integer, nullable=False)
    stop_type = Column(SQLEnum(RouteStopType), default=RouteStopType.DELIVERY, nullable=False)
    status = Column(
        SQLEnum(RouteStopStatus), default=RouteStopStatus.PENDING, nullable=False, index=True
    )
    is_active = Column(Boolean, default=True, nullable=False)

    location_name = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    coords_source = Column(String(40), default="EXPLICIT", nullable=False)
    distance_from_prev_km = Column(Float, default=0.0, nullable=False)
    eta_minutes_from_start = Column(Float, default=0.0, nullable=False)
    estimated_arrival_at = Column(DateTime, nullable=True)
    arrived_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failure_reason = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    route = relationship("DeliveryRoute", back_populates="stops")
    parcel = relationship("Parcel", back_populates="route_stops")
    assignment = relationship("DeliveryAssignment")
