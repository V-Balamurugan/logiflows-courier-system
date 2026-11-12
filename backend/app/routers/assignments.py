from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentStatusUpdate,
    AssignmentResponse,
    AssignmentCancelRequest,
    DispatchSuggestionsResponse
)
from app.models.user import User
from app.models.enums import AssignmentStatus
from app.services.assignment_service import AssignmentService
from app.dependencies.auth_deps import require_branch_manager_or_higher, require_staff, get_current_user

router = APIRouter(prefix="/assignments", tags=["Delivery Assignments"])


@router.post("", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
def create_assignment(
    data: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher)
):
    """Assigns a parcel to a delivery agent and optional vehicle."""
    assignment = AssignmentService.create_assignment(db, current_user, data)
    return AssignmentResponse(
        id=assignment.id,
        parcel_id=assignment.parcel_id,
        employee_id=assignment.employee_id,
        vehicle_id=assignment.vehicle_id,
        assignment_type=assignment.assignment_type,
        status=assignment.status,
        notes=assignment.notes,
        assigned_at=assignment.assigned_at,
        completed_at=assignment.completed_at,
        created_at=assignment.created_at,
        employee_name=assignment.employee.full_name if assignment.employee else None,
        tracking_number=assignment.parcel.tracking_number if assignment.parcel else None,
        vehicle_number=assignment.vehicle.vehicle_number if assignment.vehicle else None
    )


@router.get("", response_model=List[AssignmentResponse])
def list_assignments(
    employee_id: Optional[int] = Query(None),
    status: Optional[AssignmentStatus] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Lists assignments for staff or delivery personnel."""
    return AssignmentService.list_assignments(
        db, current_user, employee_id=employee_id, status=status
    )


@router.get("/suggestions/{parcel_id}", response_model=DispatchSuggestionsResponse)
def get_dispatch_suggestions(
    parcel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher)
):
    """
    Returns explainable dispatch recommendations for a parcel, showing candidate agents'
    workload utilization and vehicles' payload capacity compatibility.
    """
    return AssignmentService.get_dispatch_suggestions(db, current_user, parcel_id)


@router.get("/{assignment_id}", response_model=AssignmentResponse)
def get_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Retrieves assignment details with tenant isolation."""
    assignment = AssignmentService.get_assignment(db, current_user, assignment_id)
    return AssignmentResponse(
        id=assignment.id,
        parcel_id=assignment.parcel_id,
        employee_id=assignment.employee_id,
        vehicle_id=assignment.vehicle_id,
        assignment_type=assignment.assignment_type,
        status=assignment.status,
        notes=assignment.notes,
        assigned_at=assignment.assigned_at,
        completed_at=assignment.completed_at,
        created_at=assignment.created_at,
        employee_name=assignment.employee.full_name if assignment.employee else None,
        tracking_number=assignment.parcel.tracking_number if assignment.parcel else None,
        vehicle_number=assignment.vehicle.vehicle_number if assignment.vehicle else None
    )


@router.put("/{assignment_id}/status", response_model=AssignmentResponse)
def update_assignment_status(
    assignment_id: int,
    req: AssignmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Updates assignment status (e.g. IN_PROGRESS, COMPLETED)."""
    assignment = AssignmentService.update_assignment_status(db, current_user, assignment_id, req)
    return AssignmentResponse(
        id=assignment.id,
        parcel_id=assignment.parcel_id,
        employee_id=assignment.employee_id,
        vehicle_id=assignment.vehicle_id,
        assignment_type=assignment.assignment_type,
        status=assignment.status,
        notes=assignment.notes,
        assigned_at=assignment.assigned_at,
        completed_at=assignment.completed_at,
        created_at=assignment.created_at,
        employee_name=assignment.employee.full_name if assignment.employee else None,
        tracking_number=assignment.parcel.tracking_number if assignment.parcel else None,
        vehicle_number=assignment.vehicle.vehicle_number if assignment.vehicle else None
    )


@router.post("/{assignment_id}/cancel", response_model=AssignmentResponse)
def cancel_assignment(
    assignment_id: int,
    req: AssignmentCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher)
):
    """Cancels an active delivery assignment, restores vehicle availability, and logs state transition."""
    assignment = AssignmentService.cancel_assignment(db, current_user, assignment_id, req.reason)
    return AssignmentResponse(
        id=assignment.id,
        parcel_id=assignment.parcel_id,
        employee_id=assignment.employee_id,
        vehicle_id=assignment.vehicle_id,
        assignment_type=assignment.assignment_type,
        status=assignment.status,
        notes=assignment.notes,
        assigned_at=assignment.assigned_at,
        completed_at=assignment.completed_at,
        created_at=assignment.created_at,
        employee_name=assignment.employee.full_name if assignment.employee else None,
        tracking_number=assignment.parcel.tracking_number if assignment.parcel else None,
        vehicle_number=assignment.vehicle.vehicle_number if assignment.vehicle else None
    )
