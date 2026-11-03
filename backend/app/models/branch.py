from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.models.enums import OperatingStatus


class Branch(Base):
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_code = Column(String(50), unique=True, index=True, nullable=False)
    branch_name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=False)
    pincode = Column(String(20), nullable=False, index=True)
    city = Column(String(100), nullable=False, index=True)
    state = Column(String(100), nullable=False)
    country = Column(String(100), default="India", nullable=False)
    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(50), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    operating_status = Column(SQLEnum(OperatingStatus), default=OperatingStatus.ACTIVE, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="branches")
    employees = relationship("User", back_populates="branch", foreign_keys="User.branch_id")
    origin_parcels = relationship("Parcel", foreign_keys="Parcel.origin_branch_id", back_populates="origin_branch")
    dest_parcels = relationship("Parcel", foreign_keys="Parcel.dest_branch_id", back_populates="dest_branch")
    vehicles = relationship("Vehicle", back_populates="branch")

