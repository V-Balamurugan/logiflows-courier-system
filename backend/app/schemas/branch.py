import math
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
from app.models.enums import OperatingStatus


class BranchBase(BaseModel):
    branch_code: str = Field(..., min_length=2, max_length=50)
    branch_name: str = Field(..., min_length=2, max_length=255)
    address: str = Field(..., min_length=5)
    pincode: str = Field(..., min_length=3, max_length=20)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    country: str = "India"
    contact_email: EmailStr
    contact_phone: str = Field(..., min_length=5, max_length=50)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    operating_status: OperatingStatus = OperatingStatus.ACTIVE
    is_active: bool = True

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if math.isnan(v) or math.isinf(v):
                raise ValueError("Latitude must be a finite number")
            if not (-90.0 <= v <= 90.0):
                raise ValueError("Latitude must be between -90.0 and 90.0 degrees")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if math.isnan(v) or math.isinf(v):
                raise ValueError("Longitude must be a finite number")
            if not (-180.0 <= v <= 180.0):
                raise ValueError("Longitude must be between -180.0 and 180.0 degrees")
        return v


class BranchCreate(BranchBase):
    organization_id: Optional[int] = None


class BranchUpdate(BaseModel):
    branch_name: Optional[str] = None
    address: Optional[str] = None
    pincode: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    operating_status: Optional[OperatingStatus] = None
    is_active: Optional[bool] = None

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if math.isnan(v) or math.isinf(v):
                raise ValueError("Latitude must be a finite number")
            if not (-90.0 <= v <= 90.0):
                raise ValueError("Latitude must be between -90.0 and 90.0 degrees")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if math.isnan(v) or math.isinf(v):
                raise ValueError("Longitude must be a finite number")
            if not (-180.0 <= v <= 180.0):
                raise ValueError("Longitude must be between -180.0 and 180.0 degrees")
        return v


class BranchResponse(BranchBase):
    id: int
    organization_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BranchDashboardResponse(BaseModel):
    branch_id: int
    branch_code: str
    branch_name: str
    city: str
    operating_status: OperatingStatus
    is_active: bool
    total_assigned_employees: int
    stationed_vehicles: int
    active_inbound_parcels: int
    active_outbound_parcels: int
