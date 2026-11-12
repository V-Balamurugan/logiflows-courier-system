from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.parcel import Parcel
from app.models.tracking import TrackingHistory
from app.models.user import User
from app.models.enums import ParcelStatus, UserRole
from app.services.state_machine import ShipmentStateMachine
from app.schemas.tracking import (
    TrackingUpdateRequest,
    PublicTrackingResponse,
    PublicTrackingMilestone,
    TrackingHistoryResponse,
    AuthenticatedTrackingDetailResponse
)


class TrackingService:
    @staticmethod
    def get_public_tracking(db: Session, tracking_number: str) -> PublicTrackingResponse:
        """Public tracking milestone details. Strictly sanitized with 0 PII leakage."""
        if not tracking_number or not isinstance(tracking_number, str) or not tracking_number.strip():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment tracking number not found")

        parcel = db.query(Parcel).filter(Parcel.tracking_number == tracking_number.strip()).first()
        if not parcel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment tracking number not found")

        # Deterministic chronological order: created_at ASC, id ASC
        history_records = (
            db.query(TrackingHistory)
            .filter(TrackingHistory.parcel_id == parcel.id)
            .order_by(TrackingHistory.created_at.asc(), TrackingHistory.id.asc())
            .all()
        )

        milestones = [
            PublicTrackingMilestone(
                status=h.status,
                location=h.location_name,
                remarks=h.remarks,
                timestamp=h.created_at
            )
            for h in history_records
        ]

        # Deterministic latest point: created_at DESC, id DESC
        latest_event = (
            db.query(TrackingHistory)
            .filter(TrackingHistory.parcel_id == parcel.id)
            .order_by(TrackingHistory.created_at.desc(), TrackingHistory.id.desc())
            .first()
        )

        current_lat = latest_event.latitude if latest_event and latest_event.latitude is not None else (
            parcel.origin_branch.latitude if parcel.origin_branch else None
        )
        current_lng = latest_event.longitude if latest_event and latest_event.longitude is not None else (
            parcel.origin_branch.longitude if parcel.origin_branch else None
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
            current_lat=current_lat,
            current_lng=current_lng,
            current_location=parcel.current_location,
            milestones=milestones
        )

    @staticmethod
    def get_authenticated_tracking(
        db: Session,
        current_user: User,
        tracking_number: str
    ) -> AuthenticatedTrackingDetailResponse:
        """Full shipment tracking details for authorized staff or parcel owner customer."""
        if not tracking_number or not isinstance(tracking_number, str) or not tracking_number.strip():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

        parcel = db.query(Parcel).filter(Parcel.tracking_number == tracking_number.strip()).first()
        if not parcel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

        # Authorization & Tenant Isolation Checks
        if current_user.role == UserRole.CUSTOMER:
            if parcel.customer_id != current_user.id and parcel.sender_email != current_user.email:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")
        elif current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")
            origin_org = parcel.origin_branch.organization_id if parcel.origin_branch else None
            dest_org = parcel.dest_branch.organization_id if parcel.dest_branch else None
            if origin_org != current_user.organization_id and dest_org != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

        # Deterministic history
        history_records = (
            db.query(TrackingHistory)
            .filter(TrackingHistory.parcel_id == parcel.id)
            .order_by(TrackingHistory.created_at.asc(), TrackingHistory.id.asc())
            .all()
        )

        latest_event = (
            db.query(TrackingHistory)
            .filter(TrackingHistory.parcel_id == parcel.id)
            .order_by(TrackingHistory.created_at.desc(), TrackingHistory.id.desc())
            .first()
        )

        current_lat = latest_event.latitude if latest_event and latest_event.latitude is not None else (
            parcel.origin_branch.latitude if parcel.origin_branch else None
        )
        current_lng = latest_event.longitude if latest_event and latest_event.longitude is not None else (
            parcel.origin_branch.longitude if parcel.origin_branch else None
        )

        return AuthenticatedTrackingDetailResponse(
            tracking_number=parcel.tracking_number,
            status=parcel.delivery_status,
            version_id=parcel.version_id,
            sender_name=parcel.sender_name,
            sender_phone=parcel.sender_phone,
            sender_address=parcel.sender_address,
            sender_city=parcel.sender_city,
            sender_state=parcel.sender_state,
            sender_pincode=parcel.sender_pincode,
            receiver_name=parcel.receiver_name,
            receiver_phone=parcel.receiver_phone,
            receiver_address=parcel.receiver_address,
            receiver_city=parcel.receiver_city,
            receiver_state=parcel.receiver_state,
            receiver_pincode=parcel.receiver_pincode,
            weight_kg=float(parcel.weight_kg),
            service_type=parcel.service_type.value,
            booking_date=parcel.booking_date,
            expected_delivery_date=parcel.expected_delivery_date,
            actual_delivery_date=parcel.actual_delivery_date,
            origin_lat=parcel.origin_branch.latitude if parcel.origin_branch else None,
            origin_lng=parcel.origin_branch.longitude if parcel.origin_branch else None,
            dest_lat=parcel.dest_branch.latitude if parcel.dest_branch else None,
            dest_lng=parcel.dest_branch.longitude if parcel.dest_branch else None,
            current_lat=current_lat,
            current_lng=current_lng,
            current_location=parcel.current_location,
            history=[TrackingHistoryResponse.model_validate(h) for h in history_records]
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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

        if current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")
            origin_org = parcel.origin_branch.organization_id if parcel.origin_branch else None
            dest_org = parcel.dest_branch.organization_id if parcel.dest_branch else None
            if origin_org != current_user.organization_id and dest_org != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

        updated_parcel = ShipmentStateMachine.transition(
            db=db,
            current_user=current_user,
            parcel=parcel,
            to_status=req.status,
            expected_version=req.expected_version,
            remarks=req.remarks,
            location_name=req.location_name or parcel.current_location,
            branch_id=req.branch_id or current_user.branch_id,
            latitude=req.latitude,
            longitude=req.longitude,
            source="API"
        )

        # Return the newest tracking event deterministically
        latest_history = (
            db.query(TrackingHistory)
            .filter(TrackingHistory.parcel_id == updated_parcel.id)
            .order_by(TrackingHistory.created_at.desc(), TrackingHistory.id.desc())
            .first()
        )
        return latest_history
