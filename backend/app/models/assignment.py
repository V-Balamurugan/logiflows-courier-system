from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.models.enums import AssignmentType, AssignmentStatus


class DeliveryAssignment(Base):
    __tablename__ = "delivery_assignments"

    id = Column(Integer, primary_key=True, index=True)
    parcel_id = Column(Integer, ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True)
    assignment_type = Column(SQLEnum(AssignmentType), default=AssignmentType.LAST_MILE, nullable=False)
    status = Column(SQLEnum(AssignmentStatus), default=AssignmentStatus.ASSIGNED, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    assigned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    parcel = relationship("Parcel", back_populates="assignments")
    employee = relationship("User", back_populates="assignments", foreign_keys=[employee_id])
    vehicle = relationship("Vehicle", back_populates="assignments")

