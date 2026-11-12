from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from app.models.enums import UserRole


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    full_name: str
    role: UserRole
    organization_id: Optional[int] = None
    branch_id: Optional[int] = None


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class RegisterCustomerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = None
    company_name: Optional[str] = None
    gst_number: Optional[str] = None
    default_address: Optional[str] = None


class CustomerProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = None
    company_name: Optional[str] = None
    gst_number: Optional[str] = None
    default_pickup_address: Optional[str] = None
    default_delivery_address: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None
