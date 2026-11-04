from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.user import User, CustomerProfile
from app.models.parcel import Parcel
from app.models.enums import UserRole


class CustomerService:
    @staticmethod
    def list_customers(db: Session, current_user: User, search: Optional[str] = None) -> List[User]:
        query = db.query(User).filter(User.role == UserRole.CUSTOMER)

        if current_user.role != UserRole.SUPER_ADMIN and current_user.organization_id:
            org_branch_ids = [b.id for b in current_user.organization.branches] if current_user.organization else []
            if org_branch_ids:
                subquery = db.query(Parcel.customer_id).filter(
                    (Parcel.origin_branch_id.in_(org_branch_ids)) |
                    (Parcel.dest_branch_id.in_(org_branch_ids))
                ).distinct()
                query = query.filter(User.id.in_(subquery))
            else:
                return []

        if search:
            query = query.filter(
                (User.full_name.ilike(f"%{search}%")) |
                (User.email.ilike(f"%{search}%")) |
                (User.phone.ilike(f"%{search}%"))
            )
        return query.order_by(User.created_at.desc()).all()

    @staticmethod
    def get_customer(db: Session, current_user: User, customer_id: int) -> User:
        if current_user.role == UserRole.CUSTOMER and current_user.id != customer_id:
            raise HTTPException(status_code=404, detail="Customer not found")
        customer = db.query(User).filter(User.id == customer_id, User.role == UserRole.CUSTOMER).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        return customer

    @staticmethod
    def get_customer_parcels(db: Session, current_user: User, customer_id: int) -> List[Parcel]:
        CustomerService.get_customer(db, current_user, customer_id)
        query = db.query(Parcel).filter(Parcel.customer_id == customer_id)
        if current_user.role != UserRole.SUPER_ADMIN and current_user.role != UserRole.CUSTOMER:
            if current_user.organization_id and current_user.organization:
                org_branch_ids = [b.id for b in current_user.organization.branches]
                query = query.filter(
                    (Parcel.origin_branch_id.in_(org_branch_ids)) |
                    (Parcel.dest_branch_id.in_(org_branch_ids))
                )
        return query.order_by(Parcel.created_at.desc()).all()

