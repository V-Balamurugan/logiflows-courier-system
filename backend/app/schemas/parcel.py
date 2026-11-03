from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from app.models.enums import ServiceType, PaymentStatus, ParcelStatus


class ParcelQuoteRequest(BaseModel):
    weight_kg: float = Field(..., gt=0)
    length_cm: float = Field(..., gt=0)
    width_cm: float = Field(..., gt=0)
    height_cm: float = Field(..., gt=0)
    service_type: ServiceType = ServiceType.STANDARD
    origin_pincode: Optional[str] = None
    dest_pincode: Optional[str] = None


class ParcelQuoteResponse(BaseModel):
    weight_kg: float
    volumetric_weight_kg: float
    chargeable_weight_kg: float
    base_charge: float
    weight_charge: float
    service_charge: float
    tax_amount: float
    total_charge: float
    estimated_delivery_days: int


class ParcelCreate(BaseModel):
    origin_branch_id: int
    dest_branch_id: int

    sender_name: str = Field(..., min_length=2, max_length=255)
    sender_phone: str = Field(..., min_length=5, max_length=50)
    sender_email: Optional[EmailStr] = None
    sender_address: str = Field(..., min_length=5)
    sender_city: str = Field(..., min_length=2)
    sender_state: str = Field(..., min_length=2)
    sender_pincode: str = Field(..., min_length=3)

    receiver_name: str = Field(..., min_length=2, max_length=255)
    receiver_phone: str = Field(..., min_length=5, max_length=50)
    receiver_email: Optional[EmailStr] = None
    receiver_address: str = Field(..., min_length=5)
    receiver_city: str = Field(..., min_length=2)
    receiver_state: str = Field(..., min_length=2)
    receiver_pincode: str = Field(..., min_length=3)

    weight_kg: float = Field(..., gt=0)
    length_cm: float = Field(..., gt=0)
    width_cm: float = Field(..., gt=0)
    height_cm: float = Field(..., gt=0)
    service_type: ServiceType = ServiceType.STANDARD
    notes: Optional[str] = None


class ParcelUpdate(BaseModel):
    dest_branch_id: Optional[int] = None
    receiver_name: Optional[str] = None
    receiver_phone: Optional[str] = None
    receiver_address: Optional[str] = None
    notes: Optional[str] = None
    payment_status: Optional[PaymentStatus] = None


class ParcelCancelRequest(BaseModel):
    cancellation_reason: str = Field(..., min_length=3, max_length=500)


class TrackingEventResponse(BaseModel):
    id: int
    status: ParcelStatus
    location_name: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ParcelResponse(BaseModel):
    id: int
    tracking_number: str
    customer_id: Optional[int] = None
    origin_branch_id: int
    dest_branch_id: int

    sender_name: str
    sender_phone: str
    sender_email: Optional[str] = None
    sender_address: str
    sender_city: str
    sender_state: str
    sender_pincode: str

    receiver_name: str
    receiver_phone: str
    receiver_email: Optional[str] = None
    receiver_address: str
    receiver_city: str
    receiver_state: str
    receiver_pincode: str

    weight_kg: float
    length_cm: float
    width_cm: float
    height_cm: float
    volumetric_weight_kg: float

    service_type: ServiceType
    base_charge: float
    weight_charge: float
    service_charge: float
    tax_amount: float
    total_charge: float
    payment_status: PaymentStatus

    delivery_status: ParcelStatus
    current_location: Optional[str] = None
    qr_code_data: Optional[str] = None
    notes: Optional[str] = None

    booking_date: datetime
    expected_delivery_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None
    cancellation_reason: Optional[str] = None

    created_at: datetime
    updated_at: Optional[datetime] = None
    tracking_history: Optional[List[TrackingEventResponse]] = []

    class Config:
        from_attributes = True


class PublicParcelResponse(BaseModel):
    tracking_number: str
    origin_city: str
    dest_city: str
    service_type: ServiceType
    delivery_status: ParcelStatus
    current_location: Optional[str] = None
    booking_date: datetime
    expected_delivery_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None
    tracking_history: List[TrackingEventResponse] = []

