import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from app.models.enums import VehicleType, VehicleStatus


def normalize_reg_number(v: str) -> str:
    cleaned = re.sub(r'[\s\-]+', '', v).upper()
    if len(cleaned) < 3:
        raise ValueError("Vehicle registration number must be at least 3 alphanumeric characters")
    return cleaned


class VehicleBase(BaseModel):
    vehicle_number: str = Field(..., min_length=2, max_length=50)
    vehicle_type: VehicleType = VehicleType.VAN
    model: Optional[str] = None
    max_weight_kg: float = Field(..., gt=0, description="Payload weight capacity in kg")
    max_volume_cbm: Optional[float] = Field(None, gt=0, description="Payload volume capacity in cubic meters")
    status: VehicleStatus = VehicleStatus.AVAILABLE
    branch_id: Optional[int] = None
    assigned_employee_id: Optional[int] = None
    is_active: bool = True

    @field_validator("vehicle_number")
    @classmethod
    def validate_vehicle_number(cls, v: str) -> str:
        return normalize_reg_number(v)


class VehicleCreate(VehicleBase):
    organization_id: Optional[int] = None


class VehicleUpdate(BaseModel):
    vehicle_type: Optional[VehicleType] = None
    model: Optional[str] = None
    max_weight_kg: Optional[float] = None
    max_volume_cbm: Optional[float] = None
    status: Optional[VehicleStatus] = None
    branch_id: Optional[int] = None
    assigned_employee_id: Optional[int] = None
    is_active: Optional[bool] = None


class VehicleMaintenanceRequest(BaseModel):
    is_in_maintenance: bool = Field(..., description="True to place vehicle into maintenance; False to mark available")
    notes: Optional[str] = Field(None, max_length=500, description="Reason for maintenance or service work performed")


class VehicleResponse(VehicleBase):
    id: int
    organization_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
