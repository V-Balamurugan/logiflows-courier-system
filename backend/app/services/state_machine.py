from datetime import datetime, timezone
from typing import Optional, Set, Dict, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import update
from fastapi import HTTPException, status

from app.models.parcel import Parcel
from app.models.tracking import TrackingHistory
from app.models.assignment import DeliveryAssignment
from app.models.user import User
from app.models.enums import ParcelStatus, UserRole, PaymentStatus, AssignmentStatus, VehicleStatus


class TransitionRule:
    def __init__(
        self,
        allowed_roles: Set[UserRole],
        description: str,
        require_active_assignment: bool = False
    ):
        self.allowed_roles = allowed_roles
        self.description = description
        self.require_active_assignment = require_active_assignment


# Centralized, immutable state transition matrix
TRANSITION_TABLE: Dict[Tuple[ParcelStatus, ParcelStatus], TransitionRule] = {
    # From BOOKED
    (ParcelStatus.BOOKED, ParcelStatus.CANCELLED): TransitionRule(
        allowed_roles={UserRole.CUSTOMER, UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Booking cancelled by customer or branch admin before dispatch."
    ),
    (ParcelStatus.BOOKED, ParcelStatus.PICKUP_SCHEDULED): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Assigned to agent for doorstep pickup."
    ),
    (ParcelStatus.BOOKED, ParcelStatus.PICKED_UP): TransitionRule(
        allowed_roles={UserRole.DELIVERY_AGENT, UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Picked up directly from sender."
    ),
    (ParcelStatus.BOOKED, ParcelStatus.AT_ORIGIN_BRANCH): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN, UserRole.DELIVERY_AGENT},
        description="Direct drop-off or inward scan at origin branch."
    ),

    # From PICKUP_SCHEDULED
    (ParcelStatus.PICKUP_SCHEDULED, ParcelStatus.PICKED_UP): TransitionRule(
        allowed_roles={UserRole.DELIVERY_AGENT, UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Agent confirmed pickup from consignor."
    ),
    (ParcelStatus.PICKUP_SCHEDULED, ParcelStatus.CANCELLED): TransitionRule(
        allowed_roles={UserRole.CUSTOMER, UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Booking cancelled prior to physical pickup."
    ),
    (ParcelStatus.PICKUP_SCHEDULED, ParcelStatus.BOOKED): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Pickup rescheduled; reverted to booked status."
    ),

    # From PICKED_UP
    (ParcelStatus.PICKED_UP, ParcelStatus.AT_ORIGIN_BRANCH): TransitionRule(
        allowed_roles={UserRole.DELIVERY_AGENT, UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Inward scan upon arrival at origin branch."
    ),
    (ParcelStatus.PICKED_UP, ParcelStatus.OUT_FOR_DELIVERY): TransitionRule(
        allowed_roles={UserRole.DELIVERY_AGENT, UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        require_active_assignment=True,
        description="Direct local delivery dispatch following pickup."
    ),

    # From AT_ORIGIN_BRANCH
    (ParcelStatus.AT_ORIGIN_BRANCH, ParcelStatus.IN_TRANSIT): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Dispatched from origin hub for inter-branch transit."
    ),
    (ParcelStatus.AT_ORIGIN_BRANCH, ParcelStatus.OUT_FOR_DELIVERY): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        require_active_assignment=True,
        description="Local intra-city dispatch directly from origin branch."
    ),
    (ParcelStatus.AT_ORIGIN_BRANCH, ParcelStatus.ON_HOLD): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Shipment placed on operational or administrative hold."
    ),

    # From IN_TRANSIT
    (ParcelStatus.IN_TRANSIT, ParcelStatus.AT_DESTINATION_BRANCH): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Inward scan upon arrival at destination branch."
    ),
    (ParcelStatus.IN_TRANSIT, ParcelStatus.AT_ORIGIN_BRANCH): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Returned to origin branch hub."
    ),
    (ParcelStatus.IN_TRANSIT, ParcelStatus.ON_HOLD): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="In-transit transit hold (customs / inspection / delay)."
    ),

    # From AT_DESTINATION_BRANCH
    (ParcelStatus.AT_DESTINATION_BRANCH, ParcelStatus.OUT_FOR_DELIVERY): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Dispatched for last-mile delivery to consignee.",
        require_active_assignment=True
    ),
    (ParcelStatus.AT_DESTINATION_BRANCH, ParcelStatus.ON_HOLD): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Hold applied at destination hub."
    ),
    (ParcelStatus.AT_DESTINATION_BRANCH, ParcelStatus.RETURN_TO_ORIGIN): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Consignee refused delivery; returning to origin."
    ),

    # From OUT_FOR_DELIVERY
    (ParcelStatus.OUT_FOR_DELIVERY, ParcelStatus.DELIVERED): TransitionRule(
        allowed_roles={UserRole.DELIVERY_AGENT, UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Proof of delivery confirmed; successfully delivered."
    ),
    (ParcelStatus.OUT_FOR_DELIVERY, ParcelStatus.AT_DESTINATION_BRANCH): TransitionRule(
        allowed_roles={UserRole.DELIVERY_AGENT, UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Delivery run cancelled or returned to destination hub."
    ),
    (ParcelStatus.OUT_FOR_DELIVERY, ParcelStatus.DELIVERY_FAILED): TransitionRule(
        allowed_roles={UserRole.DELIVERY_AGENT, UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Delivery attempt failed (consignee unavailable / wrong address)."
    ),

    # From DELIVERY_FAILED
    (ParcelStatus.DELIVERY_FAILED, ParcelStatus.OUT_FOR_DELIVERY): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN, UserRole.DELIVERY_AGENT},
        description="Reattempting last-mile delivery.",
        require_active_assignment=True
    ),
    (ParcelStatus.DELIVERY_FAILED, ParcelStatus.AT_DESTINATION_BRANCH): TransitionRule(
        allowed_roles={UserRole.DELIVERY_AGENT, UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Parcel returned to destination branch after failed attempt."
    ),
    (ParcelStatus.DELIVERY_FAILED, ParcelStatus.RETURN_TO_ORIGIN): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Max delivery attempts exceeded; initiated return to sender."
    ),

    # From ON_HOLD
    (ParcelStatus.ON_HOLD, ParcelStatus.AT_ORIGIN_BRANCH): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Hold released at origin branch."
    ),
    (ParcelStatus.ON_HOLD, ParcelStatus.IN_TRANSIT): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Hold released; resumed in-transit transport."
    ),
    (ParcelStatus.ON_HOLD, ParcelStatus.AT_DESTINATION_BRANCH): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Hold released at destination branch."
    ),
    (ParcelStatus.ON_HOLD, ParcelStatus.RETURN_TO_ORIGIN): TransitionRule(
        allowed_roles={UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN},
        description="Hold unresolved or damaged; initiating return."
    ),
}

TERMINAL_STATES = {
    ParcelStatus.DELIVERED,
    ParcelStatus.CANCELLED,
    ParcelStatus.RETURN_TO_ORIGIN
}


class ShipmentStateMachine:
    """
    Centralized, race-safe shipment lifecycle engine.
    This service is the SOLE authority for mutating parcel status.
    """

    @staticmethod
    def is_terminal(status: ParcelStatus) -> bool:
        return status in TERMINAL_STATES

    @staticmethod
    def is_transition_allowed(from_status: ParcelStatus, to_status: ParcelStatus) -> bool:
        return (from_status, to_status) in TRANSITION_TABLE

    @staticmethod
    def transition(
        db: Session,
        current_user: User,
        parcel: Parcel,
        to_status: ParcelStatus,
        remarks: Optional[str] = None,
        location_name: Optional[str] = None,
        branch_id: Optional[int] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        source: str = "API",
        cancellation_reason: Optional[str] = None,
        expected_version: Optional[int] = None
    ) -> Parcel:
        from_status = parcel.delivery_status

        # 0. Concurrency & Optimistic locking pre-check
        if expected_version is not None and parcel.version_id != expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Parcel {parcel.tracking_number} version mismatch (expected {expected_version}, current {parcel.version_id}). Refresh and retry."
            )

        # 1. Terminal state check
        if ShipmentStateMachine.is_terminal(from_status):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot transition parcel {parcel.tracking_number} from terminal state '{from_status.value}'."
            )

        # 2. Transition existence check
        rule = TRANSITION_TABLE.get((from_status, to_status))
        if not rule:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Illegal state transition from '{from_status.value}' to '{to_status.value}'."
            )

        # 3. Actor role validation
        if current_user.role not in rule.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role.value}' is not authorized to transition parcel from '{from_status.value}' to '{to_status.value}'."
            )

        # 4. Customer ownership check
        if current_user.role == UserRole.CUSTOMER and parcel.customer_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parcel not found"
            )

        # 5. Preconditions: assignment check for OUT_FOR_DELIVERY
        if rule.require_active_assignment:
            active_assignment = db.query(DeliveryAssignment).filter(
                DeliveryAssignment.parcel_id == parcel.id,
                DeliveryAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS])
            ).first()
            if not active_assignment:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot transition to '{to_status.value}' without an active delivery assignment."
                )

        now = datetime.now(timezone.utc)
        curr_version = expected_version if expected_version is not None else parcel.version_id

        # 6. Concurrency & Optimistic Locking Update
        update_values: Dict[str, Any] = {
            "delivery_status": to_status,
            "version_id": Parcel.version_id + 1,
            "updated_at": now
        }
        if location_name:
            update_values["current_location"] = location_name

        if to_status == ParcelStatus.DELIVERED:
            update_values["actual_delivery_date"] = now
        elif to_status == ParcelStatus.CANCELLED:
            update_values["cancellation_reason"] = cancellation_reason or remarks
            update_values["payment_status"] = PaymentStatus.REFUNDED

        stmt = (
            update(Parcel)
            .where(
                Parcel.id == parcel.id,
                Parcel.version_id == curr_version,
                Parcel.delivery_status == from_status
            )
            .values(**update_values)
        )
        result = db.execute(stmt)

        if result.rowcount == 0:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Concurrent modification conflict on parcel {parcel.tracking_number}. Please retry."
            )

        # 7. Immutable Tracking Event (created in same transaction - AC6)
        loc_desc = location_name or parcel.current_location or "In Transit"
        effective_branch_id = branch_id or (current_user.branch_id if hasattr(current_user, "branch_id") else None)

        tracking_event = TrackingHistory(
            parcel_id=parcel.id,
            from_status=from_status,
            status=to_status,
            source=source,
            branch_id=effective_branch_id,
            employee_id=current_user.id if current_user.role != UserRole.CUSTOMER else None,
            location_name=loc_desc,
            latitude=latitude,
            longitude=longitude,
            remarks=remarks or rule.description
        )
        db.add(tracking_event)

        # 8. Side effects: complete assignment on delivery
        if to_status == ParcelStatus.DELIVERED:
            active_assign = db.query(DeliveryAssignment).filter(
                DeliveryAssignment.parcel_id == parcel.id,
                DeliveryAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS])
            ).first()
            if active_assign:
                active_assign.status = AssignmentStatus.COMPLETED
                active_assign.completed_at = now
                if active_assign.vehicle:
                    active_assign.vehicle.status = VehicleStatus.AVAILABLE

        db.commit()
        db.refresh(parcel)
        return parcel
