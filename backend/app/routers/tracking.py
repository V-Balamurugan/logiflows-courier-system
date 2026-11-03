from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.tracking import (
    PublicTrackingResponse,
    TrackingUpdateRequest,
    TrackingHistoryResponse
)
from app.models.user import User
from app.services.tracking_service import TrackingService
from app.dependencies.auth_deps import require_staff

router = APIRouter(prefix="/tracking", tags=["Tracking"])


@router.get("/public/{tracking_number}", response_model=PublicTrackingResponse)
def get_public_tracking(
    tracking_number: str,
    db: Session = Depends(get_db)
):
    """Public tracking endpoint for guests and customers without exposing sensitive customer info."""
    return TrackingService.get_public_tracking(db, tracking_number)


@router.post("/{tracking_number}/update", response_model=TrackingHistoryResponse)
def manual_tracking_update(
    tracking_number: str,
    req: TrackingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Staff manual update for parcel tracking milestone and physical location."""
    return TrackingService.add_tracking_event(db, current_user, tracking_number, req)

