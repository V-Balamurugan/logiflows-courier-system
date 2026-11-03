from pydantic import BaseModel, EmailStr, Field
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


class BranchResponse(BranchBase):
    id: int
    organization_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

