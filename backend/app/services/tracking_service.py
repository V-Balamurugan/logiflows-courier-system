from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.parcel import Parcel
from app.models.tracking import TrackingHistory
from app.models.user import User
from app.models.enums import ParcelStatus, UserRole
from app.schemas.tracking import (
    TrackingUpdateRequest,
    PublicTrackingResponse,
    PublicTrackingMilestone,
    TrackingHistoryResponse
)


class TrackingService:
    @staticmethod
    def get_public_tracking(db: Session, tracking_number: str) -> PublicTrackingResponse:
        parcel = db.query(Parcel).filter(Parcel.tracking_number == tracking_number).first()
        if not parcel:
            raise HTTPException(status_code=404, detail="Shipment tracking number not found")

        milestones = []
        for h in parcel.tracking_history:
            milestones.append(
                PublicTrackingMilestone(
                    status=h.status,
                    location=h.location_name,
                    remarks=h.remarks,
                    timestamp=h.created_at
                )
            )

        return PublicTrackingResponse(
            tracking_number=parcel.tracking_number,
            status=parcel.delivery_status,
            origin_city=parcel.sender_city,
            destination_city=parcel.receiver_city,
            booking_date=parcel.booking_date,
            expected_delivery_date=parcel.expected_delivery_date,
            actual_delivery_date=parcel.actual_delivery_date,
            origin_lat=parcel.origin_branch.latitude if parcel.origin_branch else None,
            origin_lng=parcel.origin_branch.longitude if parcel.origin_branch else None,
            dest_lat=parcel.dest_branch.latitude if parcel.dest_branch else None,
            dest_lng=parcel.dest_branch.longitude if parcel.dest_branch else None,
            current_lat=parcel.tracking_history[-1].latitude if parcel.tracking_history and parcel.tracking_history[-1].latitude else (parcel.origin_branch.latitude if parcel.origin_branch else None),
            current_lng=parcel.tracking_history[-1].longitude if parcel.tracking_history and parcel.tracking_history[-1].longitude else (parcel.origin_branch.longitude if parcel.origin_branch else None),
            current_location=parcel.current_location,
            milestones=milestones
        )

    @staticmethod
    def add_tracking_event(
        db: Session,
        current_user: User,
        tracking_number: str,
        req: TrackingUpdateRequest
    ) -> TrackingHistory:
        parcel = db.query(Parcel).filter(Parcel.tracking_number == tracking_number).first()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")

        if current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id:
                raise HTTPException(status_code=404, detail="Parcel not found")
            origin_org = parcel.origin_branch.organization_id if parcel.origin_branch else None
            dest_org = parcel.dest_branch.organization_id if parcel.dest_branch else None
            if origin_org != current_user.organization_id and dest_org != current_user.organization_id:
                raise HTTPException(status_code=404, detail="Parcel not found")

        parcel.delivery_status = req.status
        if req.location_name:
            parcel.current_location = req.location_name

        now = datetime.now(timezone.utc)
        if req.status == ParcelStatus.DELIVERED:
            parcel.actual_delivery_date = now

        history = TrackingHistory(
            parcel_id=parcel.id,
            status=req.status,
            branch_id=req.branch_id or current_user.branch_id,
            employee_id=current_user.id,
            location_name=req.location_name or parcel.current_location,
            latitude=req.latitude,
            longitude=req.longitude,
            remarks=req.remarks
        )
        db.add(history)
        db.commit()
        db.refresh(history)
        return history

