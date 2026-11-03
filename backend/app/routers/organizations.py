from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.organization import OrganizationCreate, OrganizationUpdate, OrganizationResponse
from app.models.user import User
from app.services.branch_service import BranchService
from app.dependencies.auth_deps import require_super_admin, get_current_user

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("", response_model=List[OrganizationResponse])
def list_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Lists all organizations (Super Admin only)."""
    return BranchService.list_organizations(db)


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    data: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Creates a new organization (Super Admin only)."""
    return BranchService.create_organization(db, data)

