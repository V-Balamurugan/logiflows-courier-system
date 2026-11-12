import asyncio
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.tracking import (
    PublicTrackingResponse,
    TrackingUpdateRequest,
    TrackingHistoryResponse,
    AuthenticatedTrackingDetailResponse
)
from app.models.user import User
from app.models.parcel import Parcel
from app.services.tracking_service import TrackingService
from app.services.broadcaster import milestone_broadcaster
from app.dependencies.auth_deps import require_staff, get_current_user

router = APIRouter(prefix="/tracking", tags=["Tracking"])


@router.get("/public/{tracking_number}", response_model=PublicTrackingResponse)
def get_public_tracking(
    tracking_number: str,
    db: Session = Depends(get_db)
):
    """Public tracking endpoint for guests and customers without exposing sensitive customer info."""
    return TrackingService.get_public_tracking(db, tracking_number)


@router.get("/live/{tracking_number}")
async def stream_live_milestones(
    tracking_number: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Server-Sent Events (SSE) streaming endpoint for real-time milestone updates.
    Yields event data immediately upon any shipment status mutation or custody scan.
    """
    clean_tn = tracking_number.strip().upper()
    parcel = db.query(Parcel).filter(Parcel.tracking_number == clean_tn).first()
    if not parcel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment tracking number not found")

    queue = milestone_broadcaster.subscribe(clean_tn)

    async def event_generator():
        initial_data = {
            "type": "INITIAL_STATE",
            "tracking_number": parcel.tracking_number,
            "status": parcel.delivery_status.value,
            "current_location": parcel.current_location,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        yield f"data: {json.dumps(initial_data)}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event_data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event_data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            milestone_broadcaster.unsubscribe(clean_tn, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/{tracking_number}", response_model=AuthenticatedTrackingDetailResponse)
def get_authenticated_tracking(
    tracking_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Authenticated endpoint returning detailed tracking and metadata with tenant/owner authorization."""
    return TrackingService.get_authenticated_tracking(db, current_user, tracking_number)


@router.post("/{tracking_number}/update", response_model=TrackingHistoryResponse)
def manual_tracking_update(
    tracking_number: str,
    req: TrackingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Staff manual update for parcel tracking milestone and physical location."""
    return TrackingService.add_tracking_event(db, current_user, tracking_number, req)
