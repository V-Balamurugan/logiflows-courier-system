from pydantic import BaseModel, EmailStr, Field
from typing import Optional
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
    password: str = Field(..., min_length=6)
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

