from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.enums import AssignmentType, AssignmentStatus


class AssignmentCreate(BaseModel):
    parcel_id: int
    employee_id: int
    vehicle_id: Optional[int] = None
    assignment_type: AssignmentType = AssignmentType.LAST_MILE
    notes: Optional[str] = None


class AssignmentStatusUpdate(BaseModel):
    status: AssignmentStatus
    notes: Optional[str] = None


class AssignmentCancelRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500, description="Reason for assignment cancellation")


class EmployeeSuggestion(BaseModel):
    employee_id: int
    full_name: str
    active_assignments: int
    max_capacity: int = 10
    workload_utilization_pct: float
    is_available: bool
    score: float
    explanation: str


class VehicleSuggestion(BaseModel):
    vehicle_id: int
    vehicle_number: str
    vehicle_type: str
    max_weight_kg: float
    max_volume_cbm: Optional[float] = None
    parcel_weight_kg: float
    weight_utilization_pct: float
    fits_capacity: bool
    score: float
    explanation: str


class DispatchSuggestionsResponse(BaseModel):
    parcel_id: int
    tracking_number: str
    parcel_weight_kg: float
    parcel_volume_cbm: float
    branch_id: int
    branch_name: str
    suggested_employees: List[EmployeeSuggestion]
    suggested_vehicles: List[VehicleSuggestion]
    summary_recommendation: str


class AssignmentResponse(BaseModel):
    id: int
    parcel_id: int
    employee_id: int
    vehicle_id: Optional[int] = None
    assignment_type: AssignmentType
    status: AssignmentStatus
    notes: Optional[str] = None
    assigned_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime

    # Additional info populated in response
    employee_name: Optional[str] = None
    tracking_number: Optional[str] = None
    vehicle_number: Optional[str] = None

    class Config:
        from_attributes = True
