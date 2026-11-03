from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.user import EmployeeCreate, EmployeeUpdate, UserResponse, EmployeeWorkloadResponse
from app.models.user import User
from app.models.enums import UserRole
from app.services.employee_service import EmployeeService
from app.dependencies.auth_deps import require_branch_manager_or_higher, require_org_admin, get_current_user

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.get("", response_model=List[UserResponse])
def list_employees(
    branch_id: Optional[int] = Query(None),
    role: Optional[UserRole] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher)
):
    """Lists employees within the current user's management scope."""
    return EmployeeService.list_employees(
        db, current_user, branch_id=branch_id, role=role, is_active=is_active
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_employee(
    data: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher)
):
    """Creates a new employee (Org Admin / Branch Manager)."""
    return EmployeeService.create_employee(db, current_user, data)


@router.get("/{employee_id}", response_model=UserResponse)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher)
):
    """Retrieves specific employee profile."""
    return EmployeeService.get_employee(db, current_user, employee_id)


@router.put("/{employee_id}", response_model=UserResponse)
def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher)
):
    """Updates employee profile or role."""
    return EmployeeService.update_employee(db, current_user, employee_id, data)


@router.get("/{employee_id}/workload", response_model=EmployeeWorkloadResponse)
def get_employee_workload(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher)
):
    """Retrieves delivery assignments and workload counters for an employee."""
    return EmployeeService.get_employee_workload(db, employee_id)

