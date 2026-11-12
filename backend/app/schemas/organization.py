from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime


class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    code: str = Field(..., min_length=2, max_length=50)
    contact_email: EmailStr
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = True


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Organization legal entity name")
    code: str = Field(..., min_length=2, max_length=50, description="Unique tenant slug / code")
    contact_email: EmailStr
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    admin_full_name: str = Field(..., min_length=2, max_length=255, description="First Org Admin full name")
    admin_email: EmailStr = Field(..., description="First Org Admin login email")
    admin_password: str = Field(..., min_length=6, description="First Org Admin password")
    admin_phone: Optional[str] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None


class OrganizationStatusUpdate(BaseModel):
    is_active: bool = Field(..., description="True to activate, False to suspend organization")
    reason: Optional[str] = Field(None, max_length=255, description="Audit reason for status change")


class OrganizationResponse(OrganizationBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrganizationRegisterResponse(BaseModel):
    organization: OrganizationResponse
    admin_user_id: int
    admin_email: str
    admin_full_name: str
    message: str = "Organization and primary administrator created successfully"


class OrganizationDashboardResponse(BaseModel):
    organization_id: int
    organization_name: str
    organization_code: str
    is_active: bool
    total_branches: int
    total_employees: int
    total_vehicles: int
    total_parcels: int
    active_assignments: int


