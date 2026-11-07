import math
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from app.models.enums import ScanType, ParcelStatus


class CustodyScanRequest(BaseModel):
    tracking_number: str = Field(..., min_length=5)
    scan_type: ScanType
    branch_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None

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


class CustodyScanResponse(BaseModel):
    id: int
    parcel_id: int
    tracking_number: str
    scan_type: ScanType
    new_parcel_status: ParcelStatus
    scanned_by_id: int
    scanned_by_name: str
    branch_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
