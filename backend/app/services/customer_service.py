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
            raise HTTPException(status_code=403, detail="Access denied")
        customer = db.query(User).filter(User.id == customer_id, User.role == UserRole.CUSTOMER).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        return customer

    @staticmethod
    def get_customer_parcels(db: Session, current_user: User, customer_id: int) -> List[Parcel]:
        CustomerService.get_customer(db, current_user, customer_id)
        return db.query(Parcel).filter(Parcel.customer_id == customer_id).order_by(Parcel.created_at.desc()).all()

