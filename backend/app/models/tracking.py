from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SQLEnum, Text, Index
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.models.enums import ParcelStatus


class TrackingHistory(Base):
    __tablename__ = "tracking_history"
    __table_args__ = (
        Index("ix_tracking_history_parcel_created_id", "parcel_id", "created_at", "id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    parcel_id = Column(Integer, ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status = Column(SQLEnum(ParcelStatus), nullable=True)
    status = Column(SQLEnum(ParcelStatus), nullable=False)
    source = Column(String(50), default="API", nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    employee_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    location_name = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    parcel = relationship("Parcel", back_populates="tracking_history")
    branch = relationship("Branch")
    employee = relationship("User")

