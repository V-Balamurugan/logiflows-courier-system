from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.organization import Organization
from app.models.branch import Branch
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.parcel import Parcel
from app.models.assignment import DeliveryAssignment
from app.models.linehaul import LinehaulManifest
from app.models.enums import UserRole, ParcelStatus, AssignmentStatus, ManifestStatus
from app.schemas.organization import OrganizationCreate, OrganizationUpdate
from app.schemas.branch import BranchCreate, BranchUpdate, BranchDashboardResponse

TERMINAL_PARCEL_STATUSES = [
    ParcelStatus.DELIVERED,
    ParcelStatus.CANCELLED,
    ParcelStatus.RETURN_TO_ORIGIN
]


class BranchService:
    @staticmethod
    def create_organization(db: Session, data: OrganizationCreate) -> Organization:
        existing = db.query(Organization).filter(Organization.code == data.code.strip().upper()).first()
        if existing:
            raise HTTPException(status_code=400, detail="Organization code already exists")
        
        org = Organization(
            name=data.name.strip(),
            code=data.code.strip().upper(),
            contact_email=data.contact_email.strip().lower(),
            contact_phone=data.contact_phone,
            address=data.address,
            is_active=data.is_active
        )
        db.add(org)
        db.commit()
        db.refresh(org)
        return org

    @staticmethod
    def list_organizations(db: Session) -> List[Organization]:
        return db.query(Organization).order_by(Organization.created_at.desc()).all()

    @staticmethod
    def create_branch(db: Session, current_user: User, data: BranchCreate) -> Branch:
        org_id = current_user.organization_id if current_user.role != UserRole.SUPER_ADMIN else (data.organization_id or 1)
        if not org_id:
            raise HTTPException(status_code=400, detail="Organization ID is required")

        clean_code = data.branch_code.strip().upper()

        # Branch codes unique per organization
        existing_in_org = db.query(Branch).filter(
            Branch.organization_id == org_id,
            Branch.branch_code == clean_code
        ).first()
        if existing_in_org:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Branch code '{clean_code}' is already registered in this organization"
            )

        # Global uniqueness check
        existing_code = db.query(Branch).filter(Branch.branch_code == clean_code).first()
        if existing_code:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Branch code '{clean_code}' is already registered"
            )

        branch = Branch(
            organization_id=org_id,
            branch_code=clean_code,
            branch_name=data.branch_name.strip(),
            address=data.address.strip(),
            pincode=data.pincode.strip(),
            city=data.city.strip(),
            state=data.state.strip(),
            country=data.country.strip(),
            contact_email=data.contact_email.strip().lower(),
            contact_phone=data.contact_phone.strip(),
            latitude=data.latitude,
            longitude=data.longitude,
            operating_status=data.operating_status,
            is_active=data.is_active
        )
        db.add(branch)
        db.commit()
        db.refresh(branch)
        return branch

    @staticmethod
    def list_branches(
        db: Session,
        current_user: Optional[User] = None,
        search: Optional[str] = None,
        city: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> List[Branch]:
        query = db.query(Branch)
        
        # Branch Managers can strictly only see their assigned branch
        if current_user and current_user.role == UserRole.BRANCH_MANAGER:
            if current_user.branch_id:
                query = query.filter(Branch.id == current_user.branch_id)
            else:
                return []
        elif current_user and current_user.role != UserRole.SUPER_ADMIN and current_user.organization_id:
            query = query.filter(Branch.organization_id == current_user.organization_id)

        if search:
            query = query.filter(
                (Branch.branch_name.ilike(f"%{search}%")) |
                (Branch.branch_code.ilike(f"%{search}%")) |
                (Branch.city.ilike(f"%{search}%"))
            )
        if city:
            query = query.filter(Branch.city.ilike(f"%{city}%"))
        if is_active is not None:
            query = query.filter(Branch.is_active == is_active)

        return query.order_by(Branch.branch_name.asc()).all()

    @staticmethod
    def get_branch_by_id(db: Session, branch_id: int, current_user: Optional[User] = None) -> Branch:
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        if current_user and current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id or branch.organization_id != current_user.organization_id:
                raise HTTPException(status_code=404, detail="Branch not found")
            if current_user.role == UserRole.BRANCH_MANAGER and current_user.branch_id:
                if branch.id != current_user.branch_id:
                    raise HTTPException(status_code=404, detail="Branch not found")
        return branch

    @staticmethod
    def update_branch(db: Session, branch_id: int, data: BranchUpdate, current_user: Optional[User] = None) -> Branch:
        branch = BranchService.get_branch_by_id(db, branch_id, current_user)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(branch, key, value)
        db.commit()
        db.refresh(branch)
        return branch

    @staticmethod
    def delete_branch(db: Session, branch_id: int, current_user: Optional[User] = None) -> bool:
        """
        Soft-deactivates branch.
        Fails with HTTP 409 Conflict if active parcels or active assignments exist.
        """
        branch = BranchService.get_branch_by_id(db, branch_id, current_user)

        # 1. Check for active parcels in progress at or routed through this branch
        active_parcels = db.query(Parcel).filter(
            (Parcel.origin_branch_id == branch.id) | (Parcel.dest_branch_id == branch.id),
            ~Parcel.delivery_status.in_(TERMINAL_PARCEL_STATUSES)
        ).count()

        if active_parcels > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot deactivate branch: {active_parcels} active parcel(s) are currently in progress or routed through this branch"
            )

        # 2. Check for active assignments by personnel stationed at this branch
        active_assignments = db.query(DeliveryAssignment).join(
            User, DeliveryAssignment.employee_id == User.id
        ).filter(
            User.branch_id == branch.id,
            DeliveryAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS])
        ).count()

        if active_assignments > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot deactivate branch: {active_assignments} active delivery assignment(s) are in progress by personnel stationed at this branch"
            )

        # 3. Check for active linehaul manifests originating from or destined to this branch
        active_manifests = db.query(LinehaulManifest).filter(
            (LinehaulManifest.origin_branch_id == branch.id) | (LinehaulManifest.dest_branch_id == branch.id),
            LinehaulManifest.status.in_([
                ManifestStatus.DRAFT,
                ManifestStatus.SEALED,
                ManifestStatus.IN_TRANSIT,
                ManifestStatus.ARRIVED,
            ])
        ).count()

        if active_manifests > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot deactivate branch: {active_manifests} active linehaul transfer manifest(s) involve this branch"
            )

        branch.is_active = False
        db.commit()
        return True

    @staticmethod
    def get_branch_dashboard(
        db: Session,
        branch_id: int,
        current_user: Optional[User] = None
    ) -> BranchDashboardResponse:
        branch = BranchService.get_branch_by_id(db, branch_id, current_user)

        assigned_employees = db.query(User).filter(
            User.branch_id == branch.id,
            User.role != UserRole.CUSTOMER,
            User.is_active == True
        ).count()

        stationed_vehicles = db.query(Vehicle).filter(
            Vehicle.branch_id == branch.id,
            Vehicle.is_active == True
        ).count()

        active_inbound = db.query(Parcel).filter(
            Parcel.dest_branch_id == branch.id,
            ~Parcel.delivery_status.in_(TERMINAL_PARCEL_STATUSES)
        ).count()

        active_outbound = db.query(Parcel).filter(
            Parcel.origin_branch_id == branch.id,
            ~Parcel.delivery_status.in_(TERMINAL_PARCEL_STATUSES)
        ).count()

        return BranchDashboardResponse(
            branch_id=branch.id,
            branch_code=branch.branch_code,
            branch_name=branch.branch_name,
            city=branch.city,
            operating_status=branch.operating_status,
            is_active=branch.is_active,
            total_assigned_employees=assigned_employees,
            stationed_vehicles=stationed_vehicles,
            active_inbound_parcels=active_inbound,
            active_outbound_parcels=active_outbound
        )
