from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.parcel import (
    ParcelQuoteRequest,
    ParcelQuoteResponse,
    ParcelCreate,
    ParcelUpdate,
    ParcelCancelRequest,
    ParcelResponse
)
from app.models.user import User
from app.models.enums import ParcelStatus
from app.services.parcel_service import ParcelService
from app.services.pricing_service import PricingEngine
from app.dependencies.auth_deps import get_current_user

router = APIRouter(prefix="/parcels", tags=["Parcels"])


@router.post("/quote", response_model=ParcelQuoteResponse)
def calculate_quote(req: ParcelQuoteRequest):
    """Calculates estimated shipment costs and delivery duration."""
    return PricingEngine.calculate_quote(
        weight_kg=req.weight_kg,
        length_cm=req.length_cm,
        width_cm=req.width_cm,
        height_cm=req.height_cm,
        service_type=req.service_type
    )


@router.post("", response_model=ParcelResponse, status_code=status.HTTP_201_CREATED)
def book_parcel(
    data: ParcelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Books a new shipment and generates a unique tracking number with QR code."""
    return ParcelService.create_parcel(db, current_user, data)


@router.get("", response_model=List[ParcelResponse])
def list_parcels(
    status: Optional[ParcelStatus] = Query(None),
    branch_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists parcels accessible to the current user."""
    return ParcelService.list_parcels(
        db, current_user, status=status, branch_id=branch_id, search=search
    )


@router.get("/{tracking_number}", response_model=ParcelResponse)
def get_parcel(
    tracking_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves full parcel details and milestone tracking history."""
    return ParcelService.get_parcel_by_tracking(db, tracking_number)


@router.post("/{tracking_number}/cancel", response_model=ParcelResponse)
def cancel_parcel(
    tracking_number: str,
    req: ParcelCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancels a booked shipment if eligible."""
    return ParcelService.cancel_parcel(db, current_user, tracking_number, req)


@router.get("/{tracking_number}/label")
def download_label_pdf(
    tracking_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates and downloads a printable PDF shipping label with QR code."""
    pdf_bytes = ParcelService.get_shipping_label_pdf(db, tracking_number)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=shipping_label_{tracking_number}.pdf"
        }
    )

