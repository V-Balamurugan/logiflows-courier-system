from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.organization import Organization
from app.models.user import User
from app.models.branch import Branch
from app.models.vehicle import Vehicle
from app.models.parcel import Parcel
from app.models.assignment import DeliveryAssignment
from app.models.enums import UserRole, AssignmentStatus, ParcelStatus
from app.core.security import get_password_hash
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationRegisterRequest,
    OrganizationRegisterResponse,
    OrganizationResponse,
    OrganizationDashboardResponse
)


class OrganizationService:
    @staticmethod
    def register_organization_atomic(db: Session, req: OrganizationRegisterRequest) -> OrganizationRegisterResponse:
        """
        Creates an Organization and its first ORG_ADMIN user in a single atomic transaction.
        If either fails, the entire transaction is rolled back so no orphan records are created.
        """
        clean_code = req.code.strip().upper()
        clean_org_email = req.contact_email.strip().lower()
        clean_admin_email = req.admin_email.strip().lower()

        # Pre-check collisions
        if db.query(Organization).filter(Organization.code == clean_code).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Organization with code '{clean_code}' already exists"
            )

        if db.query(User).filter(User.email == clean_admin_email).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{clean_admin_email}' already exists"
            )

        try:
            # 1. Create Organization
            org = Organization(
                name=req.name.strip(),
                code=clean_code,
                contact_email=clean_org_email,
                contact_phone=req.contact_phone.strip() if req.contact_phone else None,
                address=req.address.strip() if req.address else None,
                is_active=True
            )
            db.add(org)
            db.flush()  # Populates org.id

            # 2. Create First Org Admin User
            admin_user = User(
                email=clean_admin_email,
                hashed_password=get_password_hash(req.admin_password),
                full_name=req.admin_full_name.strip(),
                phone=req.admin_phone.strip() if req.admin_phone else None,
                role=UserRole.ORG_ADMIN,
                organization_id=org.id,
                branch_id=None,
                is_active=True
            )
            db.add(admin_user)
            db.flush()  # Verifies constraints

            db.commit()
            db.refresh(org)
            db.refresh(admin_user)

            return OrganizationRegisterResponse(
                organization=OrganizationResponse.model_validate(org),
                admin_user_id=admin_user.id,
                admin_email=admin_user.email,
                admin_full_name=admin_user.full_name,
                message="Organization and primary administrator created successfully"
            )
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def list_organizations(db: Session, current_user: User) -> List[Organization]:
        if current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super Admin privileges required to view all organizations"
            )
        return db.query(Organization).order_by(Organization.created_at.desc()).all()

    @staticmethod
    def get_organization(db: Session, org_id: int, current_user: User) -> Organization:
        if current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id or current_user.organization_id != org_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Organization not found"
                )
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
        return org

    @staticmethod
    def update_organization(
        db: Session,
        org_id: int,
        data: OrganizationUpdate,
        current_user: User
    ) -> Organization:
        org = OrganizationService.get_organization(db, org_id, current_user)

        # Only Super Admin can change is_active via update_organization
        if data.is_active is not None and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Super Administrators can activate or suspend organizations"
            )

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(org, key, value)

        db.commit()
        db.refresh(org)
        return org

    @staticmethod
    def set_organization_status(
        db: Session,
        org_id: int,
        is_active: bool,
        current_user: User
    ) -> Organization:
        if current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super Admin privileges required to change organization status"
            )
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
        org.is_active = is_active
        db.commit()
        db.refresh(org)
        return org

    @staticmethod
    def get_organization_dashboard(
        db: Session,
        org_id: int,
        current_user: User
    ) -> OrganizationDashboardResponse:
        org = OrganizationService.get_organization(db, org_id, current_user)

        total_branches = db.query(Branch).filter(Branch.organization_id == org.id).count()
        total_employees = db.query(User).filter(
            User.organization_id == org.id,
            User.role != UserRole.CUSTOMER
        ).count()
        total_vehicles = db.query(Vehicle).filter(Vehicle.organization_id == org.id).count()

        # Count parcels connected to this organization's branches
        org_branch_ids = [b.id for b in org.branches]
        total_parcels = 0
        active_assignments = 0

        if org_branch_ids:
            total_parcels = db.query(Parcel).filter(
                (Parcel.origin_branch_id.in_(org_branch_ids)) |
                (Parcel.dest_branch_id.in_(org_branch_ids))
            ).count()

            active_assignments = db.query(DeliveryAssignment).join(
                User, DeliveryAssignment.employee_id == User.id
            ).filter(
                User.organization_id == org.id,
                DeliveryAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS])
            ).count()

        return OrganizationDashboardResponse(
            organization_id=org.id,
            organization_name=org.name,
            organization_code=org.code,
            is_active=org.is_active,
            total_branches=total_branches,
            total_employees=total_employees,
            total_vehicles=total_vehicles,
            total_parcels=total_parcels,
            active_assignments=active_assignments
        )
