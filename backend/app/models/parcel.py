from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.models.enums import ServiceType, PaymentStatus, ParcelStatus


class Parcel(Base):
    __tablename__ = "parcels"

    id = Column(Integer, primary_key=True, index=True)
    tracking_number = Column(String(50), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    origin_branch_id = Column(Integer, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True)
    dest_branch_id = Column(Integer, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Sender Information
    sender_name = Column(String(255), nullable=False)
    sender_phone = Column(String(50), nullable=False)
    sender_email = Column(String(255), nullable=True)
    sender_address = Column(Text, nullable=False)
    sender_city = Column(String(100), nullable=False)
    sender_state = Column(String(100), nullable=False)
    sender_pincode = Column(String(20), nullable=False)

    # Receiver Information
    receiver_name = Column(String(255), nullable=False)
    receiver_phone = Column(String(50), nullable=False)
    receiver_email = Column(String(255), nullable=True)
    receiver_address = Column(Text, nullable=False)
    receiver_city = Column(String(100), nullable=False)
    receiver_state = Column(String(100), nullable=False)
    receiver_pincode = Column(String(20), nullable=False)

    # Physical Attributes
    weight_kg = Column(Float, nullable=False)
    length_cm = Column(Float, nullable=False)
    width_cm = Column(Float, nullable=False)
    height_cm = Column(Float, nullable=False)
    volumetric_weight_kg = Column(Float, nullable=False)

    # Logistics & Service
    service_type = Column(SQLEnum(ServiceType), default=ServiceType.STANDARD, nullable=False)
    base_charge = Column(Float, default=50.0, nullable=False)
    weight_charge = Column(Float, default=0.0, nullable=False)
    service_charge = Column(Float, default=0.0, nullable=False)
    tax_amount = Column(Float, default=0.0, nullable=False)
    total_charge = Column(Float, nullable=False)
    payment_status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PAID, nullable=False)

    # Current Status & Tracking
    delivery_status = Column(SQLEnum(ParcelStatus), default=ParcelStatus.BOOKED, nullable=False, index=True)
    version_id = Column(Integer, default=1, nullable=False)
    current_location = Column(String(255), nullable=True)
    qr_code_data = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    booking_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expected_delivery_date = Column(DateTime, nullable=True)
    actual_delivery_date = Column(DateTime, nullable=True)
    cancellation_reason = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    customer = relationship("User", back_populates="booked_parcels", foreign_keys=[customer_id])
    origin_branch = relationship("Branch", foreign_keys=[origin_branch_id], back_populates="origin_parcels")
    dest_branch = relationship("Branch", foreign_keys=[dest_branch_id], back_populates="dest_parcels")
    tracking_history = relationship("TrackingHistory", back_populates="parcel", cascade="all, delete-orphan", order_by="TrackingHistory.created_at.asc()")
    custody_scans = relationship("CustodyScan", back_populates="parcel", cascade="all, delete-orphan", order_by="CustodyScan.created_at.desc()")
    assignments = relationship("DeliveryAssignment", back_populates="parcel", cascade="all, delete-orphan")

