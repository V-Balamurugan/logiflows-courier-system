from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.assignment import DeliveryAssignment
from app.models.parcel import Parcel
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.tracking import TrackingHistory
from app.models.enums import AssignmentStatus, AssignmentType, ParcelStatus, VehicleStatus, UserRole
from app.schemas.assignment import AssignmentCreate, AssignmentStatusUpdate, AssignmentResponse
from app.services.state_machine import ShipmentStateMachine


class AssignmentService:
    @staticmethod
    def create_assignment(db: Session, current_user: User, data: AssignmentCreate) -> DeliveryAssignment:
        parcel = db.query(Parcel).filter(Parcel.id == data.parcel_id).first()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")

        # Tenant scoping for parcel
        if current_user.role != UserRole.SUPER_ADMIN:
            origin_org = parcel.origin_branch.organization_id if parcel.origin_branch else None
            dest_org = parcel.dest_branch.organization_id if parcel.dest_branch else None
            if origin_org != current_user.organization_id and dest_org != current_user.organization_id:
                raise HTTPException(status_code=404, detail="Parcel not found")

        # Check existing active assignment for this parcel
        active_existing = db.query(DeliveryAssignment).filter(
            DeliveryAssignment.parcel_id == data.parcel_id,
            DeliveryAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS])
        ).first()
        if active_existing:
            raise HTTPException(
                status_code=400,
                detail=f"Parcel is already actively assigned to an agent (Assignment #{active_existing.id})"
            )

        employee = db.query(User).filter(User.id == data.employee_id, User.is_active == True).first()
        if not employee or employee.role not in [UserRole.DELIVERY_AGENT, UserRole.BRANCH_MANAGER]:
            raise HTTPException(status_code=400, detail="Invalid delivery employee")

        if current_user.role != UserRole.SUPER_ADMIN and employee.organization_id != current_user.organization_id:
            raise HTTPException(status_code=404, detail="Delivery employee not found")

        vehicle = None
        if data.vehicle_id:
            vehicle = db.query(Vehicle).filter(Vehicle.id == data.vehicle_id, Vehicle.is_active == True).first()
            if not vehicle:
                raise HTTPException(status_code=400, detail="Vehicle not found or inactive")
            if current_user.role != UserRole.SUPER_ADMIN and vehicle.organization_id != current_user.organization_id:
                raise HTTPException(status_code=404, detail="Vehicle not found")

        assignment = DeliveryAssignment(
            parcel_id=data.parcel_id,
            employee_id=data.employee_id,
            vehicle_id=data.vehicle_id,
            assignment_type=data.assignment_type,
            status=AssignmentStatus.ASSIGNED,
            notes=data.notes,
            assigned_at=datetime.now(timezone.utc)
        )
        db.add(assignment)
        db.flush()

        if vehicle:
            vehicle.status = VehicleStatus.ASSIGNED

        # Update parcel status according to assignment type via State Machine
        new_status = ParcelStatus.OUT_FOR_DELIVERY if data.assignment_type == AssignmentType.LAST_MILE else ParcelStatus.PICKUP_SCHEDULED
        if data.assignment_type == AssignmentType.TRANSFER:
            new_status = ParcelStatus.IN_TRANSIT

        ShipmentStateMachine.transition(
            db=db,
            current_user=current_user,
            parcel=parcel,
            to_status=new_status,
            remarks=f"Assigned for {data.assignment_type.value}. Delivery agent: {employee.full_name} ({employee.phone or 'N/A'})",
            location_name=f"Assigned to {employee.full_name}",
            branch_id=employee.branch_id,
            source="ASSIGNMENT"
        )
        db.commit()
        db.refresh(assignment)
        return assignment

    @staticmethod
    def list_assignments(
        db: Session,
        current_user: User,
        employee_id: Optional[int] = None,
        status: Optional[AssignmentStatus] = None
    ) -> List[AssignmentResponse]:
        query = db.query(DeliveryAssignment)

        if current_user.role != UserRole.SUPER_ADMIN and current_user.organization_id:
            query = query.join(User, DeliveryAssignment.employee_id == User.id).filter(
                User.organization_id == current_user.organization_id
            )

        if current_user.role == UserRole.DELIVERY_AGENT:
            query = query.filter(DeliveryAssignment.employee_id == current_user.id)
        elif employee_id:
            query = query.filter(DeliveryAssignment.employee_id == employee_id)

        if status:
            query = query.filter(DeliveryAssignment.status == status)

        assignments = query.order_by(DeliveryAssignment.assigned_at.desc()).all()

        responses = []
        for a in assignments:
            resp = AssignmentResponse(
                id=a.id,
                parcel_id=a.parcel_id,
                employee_id=a.employee_id,
                vehicle_id=a.vehicle_id,
                assignment_type=a.assignment_type,
                status=a.status,
                notes=a.notes,
                assigned_at=a.assigned_at,
                completed_at=a.completed_at,
                created_at=a.created_at,
                employee_name=a.employee.full_name if a.employee else None,
                tracking_number=a.parcel.tracking_number if a.parcel else None,
                vehicle_number=a.vehicle.vehicle_number if a.vehicle else None
            )
            responses.append(resp)
        return responses

    @staticmethod
    def update_assignment_status(
        db: Session,
        current_user: User,
        assignment_id: int,
        req: AssignmentStatusUpdate
    ) -> DeliveryAssignment:
        assignment = db.query(DeliveryAssignment).filter(DeliveryAssignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        # Check tenant isolation
        if current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id:
                raise HTTPException(status_code=404, detail="Assignment not found")
            emp_org = assignment.employee.organization_id if assignment.employee else None
            if emp_org != current_user.organization_id:
                raise HTTPException(status_code=404, detail="Assignment not found")

        if current_user.role == UserRole.DELIVERY_AGENT and assignment.employee_id != current_user.id:
            raise HTTPException(status_code=404, detail="Assignment not found")

        assignment.status = req.status
        if req.notes:
            assignment.notes = req.notes

        now = datetime.now(timezone.utc)
        if req.status in [AssignmentStatus.COMPLETED, AssignmentStatus.CANCELLED]:
            assignment.completed_at = now
            if assignment.vehicle:
                assignment.vehicle.status = VehicleStatus.AVAILABLE

        if req.status == AssignmentStatus.COMPLETED:
            if assignment.assignment_type == AssignmentType.LAST_MILE and assignment.parcel.delivery_status != ParcelStatus.DELIVERED:
                ShipmentStateMachine.transition(
                    db=db,
                    current_user=current_user,
                    parcel=assignment.parcel,
                    to_status=ParcelStatus.DELIVERED,
                    remarks="Delivered successfully. Proof of Delivery confirmed.",
                    location_name=f"Delivered to {assignment.parcel.receiver_name}",
                    branch_id=current_user.branch_id,
                    source="ASSIGNMENT"
                )

        db.commit()
        db.refresh(assignment)
        return assignment

