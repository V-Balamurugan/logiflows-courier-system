import math
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from app.models.enums import ScanType, ParcelStatus


class CustodyScanRequest(BaseModel):
    tracking_number: str = Field(..., min_length=5)
    scan_type: ScanType
    branch_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None
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
                raise ValueError("Scan timestamp cannot be in the future beyond 5 minutes drift")
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
    previous_hash: Optional[str] = None
    record_hash: Optional[str] = None
    created_at: datetime


class ChainVerificationRecord(BaseModel):
    id: int
    scan_type: ScanType
    is_successful: bool
    failure_reason: Optional[str] = None
    scanned_by_id: int
    scanned_by_name: Optional[str] = None
    branch_id: Optional[int] = None
    created_at: datetime
    previous_hash: Optional[str] = None
    record_hash: Optional[str] = None
    computed_hash: Optional[str] = None
    verified: bool


class CustodyChainVerificationResponse(BaseModel):
    tracking_number: str
    parcel_id: int
    total_scans: int
    is_valid: bool
    tamper_detected: bool
    chain: List[ChainVerificationRecord]
