from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.enums import ParcelStatus


class TrackingUpdateRequest(BaseModel):
    status: ParcelStatus
    branch_id: Optional[int] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    remarks: Optional[str] = None


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

