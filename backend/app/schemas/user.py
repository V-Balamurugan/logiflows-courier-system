from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from app.models.enums import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = None
    role: UserRole = UserRole.CUSTOMER
    is_active: bool = True
    organization_id: Optional[int] = None
    branch_id: Optional[int] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    branch_id: Optional[int] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class EmployeeCreate(BaseModel):
    email: EmailStr
    password: Optional[str] = Field(None, min_length=6, description="Optional initial password; if omitted, secure invite link is used")
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = None
    role: UserRole = Field(..., description="ORG_ADMIN, BRANCH_MANAGER, or DELIVERY_AGENT")
    branch_id: Optional[int] = None
    organization_id: Optional[int] = None


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    branch_id: Optional[int] = None
    is_active: Optional[bool] = None


class EmployeeInviteResponse(BaseModel):
    employee_id: int
    email: str
    invite_token: str
    invite_url: str
    expires_at: datetime
    message: str = "One-time invitation token generated. Send this link to the employee to set their credentials."


class AcceptInviteRequest(BaseModel):
    invite_token: str = Field(..., description="One-time invitation JWT token")
    new_password: str = Field(..., min_length=6, description="New secret password")


class CustomerProfileResponse(BaseModel):
    company_name: Optional[str] = None
    gst_number: Optional[str] = None
    default_pickup_address: Optional[str] = None
    default_delivery_address: Optional[str] = None

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    role: UserRole
    is_active: bool
    organization_id: Optional[int] = None
    branch_id: Optional[int] = None
    customer_profile: Optional[CustomerProfileResponse] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmployeeWorkloadResponse(BaseModel):
    employee_id: int
    full_name: str
    role: UserRole
    active_assignments_count: int
    completed_assignments_count: int


class EmployeeDashboardResponse(BaseModel):
    employee_id: int
    full_name: str
    email: str
    role: UserRole
    branch_id: Optional[int] = None
    is_active: bool
    active_assignments_count: int
    completed_assignments_count: int
    failed_assignments_count: int
