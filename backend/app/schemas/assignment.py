from pydantic import BaseModel, Field
from typing import Optional
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

