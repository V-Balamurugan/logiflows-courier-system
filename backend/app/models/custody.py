from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SQLEnum, Text, Boolean
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.models.enums import ScanType


class CustodyScan(Base):
    __tablename__ = "custody_scans"

    id = Column(Integer, primary_key=True, index=True)
    parcel_id = Column(Integer, ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False, index=True)
    scanned_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    scan_type = Column(SQLEnum(ScanType), nullable=False)
    is_successful = Column(Boolean, default=True, nullable=False)
    failure_reason = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    parcel = relationship("Parcel", back_populates="custody_scans")
    scanned_by = relationship("User")
    branch = relationship("Branch")

