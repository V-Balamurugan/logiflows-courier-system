import math
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

from app.models.enums import ParcelStatus


class TrackingUpdateRequest(BaseModel):
    status: ParcelStatus
    expected_version: Optional[int] = None
    branch_id: Optional[int] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    remarks: Optional[str] = None
    timestamp: Optional[datetime] = None

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if math.isnan(v) or math.isinf(v):
                raise ValueError("Latitude cannot be NaN or Infinite")
            if not (-90.0 <= v <= 90.0):
                raise ValueError("Latitude must be between -90.0 and +90.0 degrees")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if math.isnan(v) or math.isinf(v):
                raise ValueError("Longitude cannot be NaN or Infinite")
            if not (-180.0 <= v <= 180.0):
                raise ValueError("Longitude must be between -180.0 and +180.0 degrees")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None:
            now = datetime.now(timezone.utc)
            ts = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
            if ts > now + timedelta(minutes=5):
                raise ValueError("Tracking timestamp cannot be in the future beyond 5 minutes drift")
        return v


class TrackingHistoryResponse(BaseModel):
    id: int
    parcel_id: int
    status: ParcelStatus
    branch_id: Optional[int] = None
    employee_id: Optional[int] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    remarks: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PublicTrackingMilestone(BaseModel):
    status: ParcelStatus
    location: Optional[str] = None
    remarks: Optional[str] = None
    timestamp: datetime


class PublicTrackingResponse(BaseModel):
    tracking_number: str
    status: ParcelStatus
    origin_city: str
    destination_city: str
    booking_date: datetime
    expected_delivery_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None
    dest_lat: Optional[float] = None
    dest_lng: Optional[float] = None
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    current_location: Optional[str] = None
    milestones: List[PublicTrackingMilestone]


class AuthenticatedTrackingDetailResponse(BaseModel):
    tracking_number: str
    status: ParcelStatus
    version_id: int
    sender_name: str
    sender_phone: str
    sender_address: str
    sender_city: str
    sender_state: str
    sender_pincode: str
    receiver_name: str
    receiver_phone: str
    receiver_address: str
    receiver_city: str
    receiver_state: str
    receiver_pincode: str
    weight_kg: float
    service_type: str
    booking_date: datetime
    expected_delivery_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None
    dest_lat: Optional[float] = None
    dest_lng: Optional[float] = None
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    current_location: Optional[str] = None
    history: List[TrackingHistoryResponse]

    class Config:
        from_attributes = True
