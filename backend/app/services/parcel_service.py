from datetime import datetime, timezone, timedelta
import secrets
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.parcel import Parcel
from app.models.branch import Branch
from app.models.user import User
from app.models.tracking import TrackingHistory
from app.models.enums import ParcelStatus, UserRole, PaymentStatus
from app.schemas.parcel import ParcelCreate, ParcelUpdate, ParcelCancelRequest
from app.services.pricing_service import PricingEngine
from app.services.state_machine import ShipmentStateMachine
from app.utils.qr_security import generate_secure_qr_code
from app.utils.pdf_label import generate_shipping_label_pdf


class ParcelService:
    @staticmethod
    def generate_tracking_number(db: Session, max_retries: int = 5) -> str:
        """Generates a cryptographically random, collision-checked tracking number like LF-2026-384912."""
        year = datetime.now().year
        for _ in range(max_retries):
            random_part = secrets.randbelow(900000) + 100000  # 6-digit cryptographically strong integer
            tracking_no = f"LF-{year}-{random_part}"
            if not db.query(Parcel.id).filter(Parcel.tracking_number == tracking_no).first():
                return tracking_no
        raise HTTPException(
            status_code=500,
            detail="Failed to generate unique tracking number after maximum retry attempts. Please retry."
        )

    @staticmethod
    def create_parcel(db: Session, current_user: User, data: ParcelCreate) -> Parcel:
        # Validate branches exist
        origin_branch = db.query(Branch).filter(Branch.id == data.origin_branch_id, Branch.is_active == True).first()
        if not origin_branch:
            raise HTTPException(status_code=400, detail="Invalid origin branch")

        dest_branch = db.query(Branch).filter(Branch.id == data.dest_branch_id, Branch.is_active == True).first()
        if not dest_branch:
            raise HTTPException(status_code=400, detail="Invalid destination branch")

        # AC1: Cross-organization branch check
        # Origin and destination branches must belong to the same operating organization
        if origin_branch.organization_id != dest_branch.organization_id:
            raise HTTPException(
                status_code=400,
                detail="Origin and destination branches must belong to the same operating organization"
            )

        # Staff can only create parcels originating from their organization
        if current_user.role not in [UserRole.CUSTOMER, UserRole.SUPER_ADMIN]:
            if current_user.organization_id and (
                origin_branch.organization_id != current_user.organization_id or
                dest_branch.organization_id != current_user.organization_id
            ):
                raise HTTPException(status_code=400, detail="Branches do not belong to your organization")

        # Serviceability check: Operating status must be ACTIVE
        from app.models.enums import OperatingStatus
        if origin_branch.operating_status == OperatingStatus.INACTIVE or dest_branch.operating_status == OperatingStatus.INACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Unserviceable route: Origin or destination hub is inactive for courier operations"
            )

        # Coordinate bounds validation
        import math
        for b in [origin_branch, dest_branch]:
            if b.latitude is not None and (math.isnan(b.latitude) or math.isinf(b.latitude) or not (-90.0 <= b.latitude <= 90.0)):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Unserviceable route: Hub '{b.branch_name}' has invalid latitude coordinates"
                )
            if b.longitude is not None and (math.isnan(b.longitude) or math.isinf(b.longitude) or not (-180.0 <= b.longitude <= 180.0)):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Unserviceable route: Hub '{b.branch_name}' has invalid longitude coordinates"
                )
                raise HTTPException(status_code=400, detail="Branches do not belong to your organization")

        # Calculate pricing
        quote = PricingEngine.calculate_quote(
            weight_kg=data.weight_kg,
            length_cm=data.length_cm,
            width_cm=data.width_cm,
            height_cm=data.height_cm,
            service_type=data.service_type
        )

        tracking_number = ParcelService.generate_tracking_number(db)
        _, qr_code_data = generate_secure_qr_code(tracking_number)

        now = datetime.now(timezone.utc)
        expected_delivery = now + timedelta(days=quote.estimated_delivery_days)

        customer_id = current_user.id if current_user.role == UserRole.CUSTOMER else None

        parcel = Parcel(
            tracking_number=tracking_number,
            customer_id=customer_id,
            origin_branch_id=data.origin_branch_id,
            dest_branch_id=data.dest_branch_id,
            sender_name=data.sender_name,
            sender_phone=data.sender_phone,
            sender_email=data.sender_email,
            sender_address=data.sender_address,
            sender_city=data.sender_city,
            sender_state=data.sender_state,
            sender_pincode=data.sender_pincode,
            receiver_name=data.receiver_name,
            receiver_phone=data.receiver_phone,
            receiver_email=data.receiver_email,
            receiver_address=data.receiver_address,
            receiver_city=data.receiver_city,
            receiver_state=data.receiver_state,
            receiver_pincode=data.receiver_pincode,
            weight_kg=data.weight_kg,
            length_cm=data.length_cm,
            width_cm=data.width_cm,
            height_cm=data.height_cm,
            volumetric_weight_kg=quote.volumetric_weight_kg,
            service_type=data.service_type,
            base_charge=quote.base_charge,
            weight_charge=quote.weight_charge,
            service_charge=quote.service_charge,
            tax_amount=quote.tax_amount,
            total_charge=quote.total_charge,
            payment_status=PaymentStatus.PENDING,
            delivery_status=ParcelStatus.BOOKED,
            current_location=f"{origin_branch.city} Hub",
            qr_code_data=qr_code_data,
            notes=data.notes,
            booking_date=now,
            expected_delivery_date=expected_delivery
        )
        db.add(parcel)
        db.flush()

        # Add initial tracking history record
        tracking_event = TrackingHistory(
            parcel_id=parcel.id,
            from_status=None,
            status=ParcelStatus.BOOKED,
            source="BOOKING",
            branch_id=origin_branch.id,
            employee_id=current_user.id if current_user.role != UserRole.CUSTOMER else None,
            location_name=f"{origin_branch.branch_name}, {origin_branch.city}",
            latitude=origin_branch.latitude,
            longitude=origin_branch.longitude,
            remarks=f"Shipment booked successfully with {data.service_type.value} service."
        )
        db.add(tracking_event)
        db.commit()
        db.refresh(parcel)
        return parcel

    @staticmethod
    def list_parcels(
        db: Session,
        current_user: User,
        status: Optional[ParcelStatus] = None,
        branch_id: Optional[int] = None,
        search: Optional[str] = None
    ) -> List[Parcel]:
        query = db.query(Parcel)

        # Role-based scoping
        if current_user.role == UserRole.CUSTOMER:
            query = query.filter(Parcel.customer_id == current_user.id)
        elif current_user.role == UserRole.BRANCH_MANAGER:
            query = query.filter(
                (Parcel.origin_branch_id == current_user.branch_id) |
                (Parcel.dest_branch_id == current_user.branch_id)
            )
        elif current_user.role != UserRole.SUPER_ADMIN and current_user.organization_id:
            # Filter by branches belonging to this organization
            org_branch_ids = [b.id for b in current_user.organization.branches]
            query = query.filter(
                (Parcel.origin_branch_id.in_(org_branch_ids)) |
                (Parcel.dest_branch_id.in_(org_branch_ids))
            )

        if branch_id:
            query = query.filter(
                (Parcel.origin_branch_id == branch_id) |
                (Parcel.dest_branch_id == branch_id)
            )
        if status:
            query = query.filter(Parcel.delivery_status == status)
        if search:
            query = query.filter(
                (Parcel.tracking_number.ilike(f"%{search}%")) |
                (Parcel.receiver_name.ilike(f"%{search}%")) |
                (Parcel.receiver_city.ilike(f"%{search}%")) |
                (Parcel.sender_name.ilike(f"%{search}%"))
            )

        return query.order_by(Parcel.created_at.desc()).all()

    @staticmethod
    def get_parcel_by_tracking(db: Session, tracking_number: str, current_user: Optional[User] = None) -> Parcel:
        parcel = db.query(Parcel).filter(Parcel.tracking_number == tracking_number).first()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")
        if current_user:
            if current_user.role == UserRole.CUSTOMER:
                if parcel.customer_id != current_user.id:
                    raise HTTPException(status_code=404, detail="Parcel not found")
            elif current_user.role != UserRole.SUPER_ADMIN:
                if not current_user.organization_id:
                    raise HTTPException(status_code=404, detail="Parcel not found")
                origin_org = parcel.origin_branch.organization_id if parcel.origin_branch else None
                dest_org = parcel.dest_branch.organization_id if parcel.dest_branch else None
                if origin_org != current_user.organization_id and dest_org != current_user.organization_id:
                    raise HTTPException(status_code=404, detail="Parcel not found")
                if current_user.role == UserRole.BRANCH_MANAGER and current_user.branch_id:
                    if current_user.branch_id not in [parcel.origin_branch_id, parcel.dest_branch_id]:
                        raise HTTPException(status_code=404, detail="Parcel not found")
        return parcel

    @staticmethod
    def cancel_parcel(db: Session, current_user: User, tracking_number: str, req: ParcelCancelRequest) -> Parcel:
        parcel = ParcelService.get_parcel_by_tracking(db, tracking_number, current_user=current_user)

        updated_parcel = ShipmentStateMachine.transition(
            db=db,
            current_user=current_user,
            parcel=parcel,
            to_status=ParcelStatus.CANCELLED,
            remarks=f"Booking cancelled: {req.cancellation_reason}",
            cancellation_reason=req.cancellation_reason,
            source="API"
        )

        # Update payment status accordingly
        if updated_parcel.payment_status == PaymentStatus.PAID:
            updated_parcel.payment_status = PaymentStatus.REFUNDED
        else:
            updated_parcel.payment_status = PaymentStatus.CANCELLED

        db.commit()
        db.refresh(updated_parcel)
        return updated_parcel

    @staticmethod
    def get_shipping_label_pdf(db: Session, tracking_number: str, current_user: Optional[User] = None) -> bytes:
        parcel = ParcelService.get_parcel_by_tracking(db, tracking_number, current_user=current_user)
        parcel_dict = {
            "tracking_number": parcel.tracking_number,
            "service_type": parcel.service_type.value,
            "sender_name": parcel.sender_name,
            "sender_address": parcel.sender_address,
            "sender_city": parcel.sender_city,
            "sender_state": parcel.sender_state,
            "sender_pincode": parcel.sender_pincode,
            "sender_phone": parcel.sender_phone,
            "receiver_name": parcel.receiver_name,
            "receiver_address": parcel.receiver_address,
            "receiver_city": parcel.receiver_city,
            "receiver_state": parcel.receiver_state,
            "receiver_pincode": parcel.receiver_pincode,
            "receiver_phone": parcel.receiver_phone,
            "weight_kg": parcel.weight_kg,
            "length_cm": parcel.length_cm,
            "width_cm": parcel.width_cm,
            "height_cm": parcel.height_cm,
            "volumetric_weight_kg": parcel.volumetric_weight_kg,
            "payment_status": parcel.payment_status.value,
            "booking_date": str(parcel.booking_date)
        }
        return generate_shipping_label_pdf(parcel_dict)

