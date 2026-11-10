from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.user import UserResponse
from app.schemas.parcel import ParcelResponse
from app.schemas.auth import CustomerProfileUpdateRequest
from app.models.user import User
from app.services.customer_service import CustomerService
from app.dependencies.auth_deps import require_staff, get_current_user

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=List[UserResponse])
def list_customers(
    search: Optional[str] = Query(None, description="Search by customer name, email, or phone"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Lists registered customer profiles (Staff only)."""
    return CustomerService.list_customers(db, current_user, search=search)


@router.get("/me/profile", response_model=UserResponse)
def get_my_customer_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves profile and saved default addresses for currently authenticated customer."""
    return CustomerService.get_customer(db, current_user, current_user.id)


@router.put("/me/profile", response_model=UserResponse)
def update_my_customer_profile(
    data: CustomerProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Updates profile details, company, and default addresses for currently authenticated customer."""
    return CustomerService.update_customer_profile(db, current_user, data)


@router.get("/me/parcels", response_model=List[ParcelResponse])
def get_my_customer_parcels(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves consignment history for currently authenticated customer."""
    return CustomerService.get_customer_parcels(db, current_user, current_user.id)


@router.get("/{customer_id}", response_model=UserResponse)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves customer profile and default addresses (scoped)."""
    return CustomerService.get_customer(db, current_user, customer_id)


@router.get("/{customer_id}/parcels", response_model=List[ParcelResponse])
def get_customer_parcels(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves shipment history for a customer."""
    return CustomerService.get_customer_parcels(db, current_user, customer_id)
