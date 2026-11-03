from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.branch import BranchCreate, BranchUpdate, BranchResponse
from app.models.user import User
from app.services.branch_service import BranchService
from app.dependencies.auth_deps import require_org_admin, get_current_user

router = APIRouter(prefix="/branches", tags=["Branches"])


@router.get("", response_model=List[BranchResponse])
def list_branches(
    search: Optional[str] = Query(None, description="Search by name, code or city"),
    city: Optional[str] = Query(None, description="Filter by city"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists branches accessible to the current user."""
    return BranchService.list_branches(db, current_user, search=search, city=city, is_active=is_active)


@router.post("", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
def create_branch(
    data: BranchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_admin)
):
    """Creates a new branch under current user's organization."""
    return BranchService.create_branch(db, current_user, data)


@router.get("/{branch_id}", response_model=BranchResponse)
def get_branch(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves specific branch details by ID."""
    return BranchService.get_branch_by_id(db, branch_id)


@router.put("/{branch_id}", response_model=BranchResponse)
def update_branch(
    branch_id: int,
    data: BranchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_admin)
):
    """Updates branch metadata and operating status."""
    return BranchService.update_branch(db, branch_id, data)


@router.delete("/{branch_id}")
def delete_branch(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_admin)
):
    """Soft deletes/deactivates a branch."""
    BranchService.delete_branch(db, branch_id)
    return {"message": "Branch deactivated successfully"}

