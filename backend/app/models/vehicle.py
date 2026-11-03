from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.models.enums import VehicleType, VehicleStatus


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    vehicle_number = Column(String(50), unique=True, index=True, nullable=False)
    vehicle_type = Column(SQLEnum(VehicleType), default=VehicleType.VAN, nullable=False)
    model = Column(String(100), nullable=True)
    max_weight_kg = Column(Float, default=500.0, nullable=False)
    max_volume_cbm = Column(Float, default=5.0, nullable=True)
    status = Column(SQLEnum(VehicleStatus), default=VehicleStatus.AVAILABLE, nullable=False, index=True)
    assigned_employee_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="vehicles")
    branch = relationship("Branch", back_populates="vehicles")
    assignments = relationship("DeliveryAssignment", back_populates="vehicle")

