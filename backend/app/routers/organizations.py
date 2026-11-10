from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationRegisterRequest,
    OrganizationRegisterResponse,
    OrganizationStatusUpdate,
    OrganizationDashboardResponse
)
from app.models.user import User
from app.services.organization_service import OrganizationService
from app.services.branch_service import BranchService
from app.dependencies.auth_deps import require_super_admin, require_org_admin, get_current_user

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    data: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Creates a new organization directly (Super Admin only)."""
    return BranchService.create_organization(db, data)


@router.post("/register", response_model=OrganizationRegisterResponse, status_code=status.HTTP_201_CREATED)
def register_organization(
    data: OrganizationRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Public or administrative atomic organization registration.
    Creates an organization and its primary Org Admin user in a single atomic transaction.
    """
    return OrganizationService.register_organization_atomic(db, data)


@router.get("", response_model=List[OrganizationResponse])
def list_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Lists all organizations in the platform (Super Admin only)."""
    return OrganizationService.list_organizations(db, current_user)


@router.get("/my-org", response_model=OrganizationResponse)
def get_my_organization(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_admin)
):
    """Returns the authenticated Org Admin's organization."""
    if not current_user.organization_id:
        return OrganizationService.get_organization(db, 1, current_user)
    return OrganizationService.get_organization(db, current_user.organization_id, current_user)


@router.patch("/my-org", response_model=OrganizationResponse)
def update_my_organization(
    data: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_admin)
):
    """Updates the authenticated Org Admin's organization profile and contact settings."""
    org_id = current_user.organization_id or 1
    return OrganizationService.update_organization(db, org_id, data, current_user)


@router.get("/{org_id}", response_model=OrganizationResponse)
def get_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_admin)
):
    """Retrieves organization details (Super Admin or authorized Org Admin)."""
    return OrganizationService.get_organization(db, org_id, current_user)


@router.patch("/{org_id}", response_model=OrganizationResponse)
def update_organization(
    org_id: int,
    data: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_admin)
):
    """Updates organization details (Super Admin or authorized Org Admin)."""
    return OrganizationService.update_organization(db, org_id, data, current_user)


@router.patch("/{org_id}/status", response_model=OrganizationResponse)
def set_organization_status(
    org_id: int,
    data: OrganizationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Suspends or activates an organization (Super Admin only)."""
    return OrganizationService.set_organization_status(db, org_id, data.is_active, current_user)


@router.get("/{org_id}/dashboard", response_model=OrganizationDashboardResponse)
def get_organization_dashboard(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_admin)
):
    """Returns summarized dashboard metrics for an organization."""
    return OrganizationService.get_organization_dashboard(db, org_id, current_user)
