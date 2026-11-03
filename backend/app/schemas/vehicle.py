from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.enums import VehicleType, VehicleStatus


class VehicleBase(BaseModel):
    vehicle_number: str = Field(..., min_length=2, max_length=50)
    vehicle_type: VehicleType = VehicleType.VAN
    model: Optional[str] = None
    max_weight_kg: float = Field(..., gt=0)
    max_volume_cbm: Optional[float] = Field(None, gt=0)
    status: VehicleStatus = VehicleStatus.AVAILABLE
    branch_id: Optional[int] = None
    assigned_employee_id: Optional[int] = None
    is_active: bool = True


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


class VehicleResponse(VehicleBase):
    id: int
    organization_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

