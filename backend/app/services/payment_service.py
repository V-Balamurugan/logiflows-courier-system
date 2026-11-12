from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.parcel import Parcel
from app.models.user import User
from app.models.tracking import TrackingHistory
from app.models.enums import PaymentStatus, UserRole
from app.schemas.parcel import PaymentRecordRequest


class PaymentService:
    """
    Service layer governing payment transitions, verification, and auditability.
    
    Payment State Machine:
    PENDING   --> [PAID, FAILED, CANCELLED]
    FAILED    --> [PENDING, PAID, CANCELLED]
    PAID      --> [REFUNDED]
    REFUNDED  --> [] (Terminal)
    CANCELLED --> [] (Terminal)
    """

    ALLOWED_TRANSITIONS: Dict[PaymentStatus, List[PaymentStatus]] = {
        PaymentStatus.PENDING: [PaymentStatus.PAID, PaymentStatus.FAILED, PaymentStatus.CANCELLED],
        PaymentStatus.FAILED: [PaymentStatus.PENDING, PaymentStatus.PAID, PaymentStatus.CANCELLED],
        PaymentStatus.PAID: [PaymentStatus.REFUNDED],
        PaymentStatus.REFUNDED: [],
        PaymentStatus.CANCELLED: [],
    }

    @classmethod
    def can_transition(cls, from_status: PaymentStatus, to_status: PaymentStatus) -> bool:
        return to_status in cls.ALLOWED_TRANSITIONS.get(from_status, [])

    @classmethod
    def record_payment(
        cls,
        db: Session,
        current_user: User,
        tracking_number: str,
        req: PaymentRecordRequest
    ) -> Parcel:
        parcel = db.query(Parcel).filter(Parcel.tracking_number == tracking_number).first()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")

        # Tenant isolation
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

        target_status = PaymentStatus.PAID if req.is_success else PaymentStatus.FAILED

        # Validate payment state transition
        if not cls.can_transition(parcel.payment_status, target_status):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Illegal payment transition from '{parcel.payment_status.value}' to '{target_status.value}'."
            )

        now = datetime.now(timezone.utc)

        if req.is_success:
            # Validate payment amount against total charge (tolerance 0.05 for rounding)
            expected_amount = Decimal(str(parcel.total_charge))
            paid_amount = Decimal(str(req.amount))
            if abs(paid_amount - expected_amount) > Decimal("0.05"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Payment amount ₹{req.amount} does not match required shipment charge ₹{parcel.total_charge}."
                )

            parcel.payment_status = PaymentStatus.PAID
            parcel.payment_method = req.payment_method
            parcel.transaction_reference = req.transaction_reference
            parcel.paid_at = now

            remarks = f"Payment verified & completed via {req.payment_method} (Ref: {req.transaction_reference}). Amount: ₹{req.amount:.2f}"
        else:
            parcel.payment_status = PaymentStatus.FAILED
            remarks = f"Payment attempt failed via {req.payment_method} (Ref: {req.transaction_reference}). Reason: {req.failure_reason or 'Unknown'}"

        # Record atomic tracking history audit event
        history = TrackingHistory(
            parcel_id=parcel.id,
            from_status=parcel.delivery_status,
            status=parcel.delivery_status,
            source="PAYMENT",
            branch_id=current_user.branch_id,
            employee_id=current_user.id if current_user.role != UserRole.CUSTOMER else None,
            location_name=parcel.current_location,
            remarks=remarks
        )
        db.add(history)
        db.commit()
        db.refresh(parcel)
        return parcel
