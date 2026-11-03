from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.enums import ScanType, ParcelStatus


class CustodyScanRequest(BaseModel):
    tracking_number: str = Field(..., min_length=5)
    scan_type: ScanType
    branch_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None


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

