from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.organization import Organization
from app.models.branch import Branch
from app.models.user import User
from app.models.enums import UserRole
from app.schemas.organization import OrganizationCreate, OrganizationUpdate
from app.schemas.branch import BranchCreate, BranchUpdate


class BranchService:
    @staticmethod
    def create_organization(db: Session, data: OrganizationCreate) -> Organization:
        existing = db.query(Organization).filter(Organization.code == data.code.upper()).first()
        if existing:
            raise HTTPException(status_code=400, detail="Organization code already exists")
        
        org = Organization(
            name=data.name,
            code=data.code.upper(),
            contact_email=data.contact_email,
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

        existing_code = db.query(Branch).filter(Branch.branch_code == data.branch_code.upper()).first()
        if existing_code:
            raise HTTPException(status_code=400, detail="Branch code already in use")

        branch = Branch(
            organization_id=org_id,
            branch_code=data.branch_code.upper(),
            branch_name=data.branch_name,
            address=data.address,
            pincode=data.pincode,
            city=data.city,
            state=data.state,
            country=data.country,
            contact_email=data.contact_email,
            contact_phone=data.contact_phone,
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
        
        if current_user and current_user.role != UserRole.SUPER_ADMIN and current_user.organization_id:
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
    def get_branch_by_id(db: Session, branch_id: int) -> Branch:
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        return branch

    @staticmethod
    def update_branch(db: Session, branch_id: int, data: BranchUpdate) -> Branch:
        branch = BranchService.get_branch_by_id(db, branch_id)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(branch, key, value)
        db.commit()
        db.refresh(branch)
        return branch

    @staticmethod
    def delete_branch(db: Session, branch_id: int) -> bool:
        branch = BranchService.get_branch_by_id(db, branch_id)
        branch.is_active = False
        db.commit()
        return True

