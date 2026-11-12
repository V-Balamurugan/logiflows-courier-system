import re
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.vehicle import Vehicle
from app.models.user import User
from app.models.assignment import DeliveryAssignment
from app.models.linehaul import LinehaulManifest
from app.models.enums import UserRole, VehicleStatus, AssignmentStatus, ManifestStatus
from app.schemas.vehicle import VehicleCreate, VehicleUpdate, normalize_reg_number


class VehicleService:
    @staticmethod
    def create_vehicle(db: Session, current_user: User, data: VehicleCreate) -> Vehicle:
        org_id = current_user.organization_id if current_user.role != UserRole.SUPER_ADMIN else (data.organization_id or 1)
        normalized_number = normalize_reg_number(data.vehicle_number)

        existing = db.query(Vehicle).filter(Vehicle.vehicle_number == normalized_number).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle with registration number '{normalized_number}' already exists"
            )

        vehicle = Vehicle(
            organization_id=org_id,
            branch_id=data.branch_id or current_user.branch_id,
            vehicle_number=normalized_number,
            vehicle_type=data.vehicle_type,
            model=data.model,
            max_weight_kg=data.max_weight_kg,
            max_volume_cbm=data.max_volume_cbm,
            status=data.status,
            assigned_employee_id=data.assigned_employee_id,
            is_active=data.is_active
        )
        db.add(vehicle)
        db.commit()
        db.refresh(vehicle)
        return vehicle

    @staticmethod
    def list_vehicles(
        db: Session,
        current_user: User,
        branch_id: Optional[int] = None,
        status: Optional[VehicleStatus] = None
    ) -> List[Vehicle]:
        query = db.query(Vehicle)

        if current_user.role != UserRole.SUPER_ADMIN and current_user.organization_id:
            query = query.filter(Vehicle.organization_id == current_user.organization_id)

        if current_user.role == UserRole.BRANCH_MANAGER:
            query = query.filter(Vehicle.branch_id == current_user.branch_id)
        elif branch_id:
            query = query.filter(Vehicle.branch_id == branch_id)

        if status:
            query = query.filter(Vehicle.status == status)

        return query.order_by(Vehicle.vehicle_number.asc()).all()

    @staticmethod
    def get_vehicle(db: Session, vehicle_id: int, current_user: Optional[User] = None) -> Vehicle:
        vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
        if not vehicle:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
        if current_user and current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id or vehicle.organization_id != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
            if current_user.role == UserRole.BRANCH_MANAGER and current_user.branch_id:
                if vehicle.branch_id and vehicle.branch_id != current_user.branch_id:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
        return vehicle

    @staticmethod
    def update_vehicle(db: Session, vehicle_id: int, data: VehicleUpdate, current_user: Optional[User] = None) -> Vehicle:
        vehicle = VehicleService.get_vehicle(db, vehicle_id, current_user=current_user)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(vehicle, key, value)
        db.commit()
        db.refresh(vehicle)
        return vehicle

    @staticmethod
    def set_maintenance_status(
        db: Session,
        vehicle_id: int,
        is_in_maintenance: bool,
        notes: Optional[str] = None,
        current_user: Optional[User] = None
    ) -> Vehicle:
        vehicle = VehicleService.get_vehicle(db, vehicle_id, current_user=current_user)

        if is_in_maintenance:
            # Check for active assignments
            active_assignment = db.query(DeliveryAssignment).filter(
                DeliveryAssignment.vehicle_id == vehicle.id,
                DeliveryAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS])
            ).first()

            if active_assignment:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot place vehicle into maintenance: actively dispatched on Assignment #{active_assignment.id}"
                )

            active_manifest = db.query(LinehaulManifest).filter(
                LinehaulManifest.vehicle_id == vehicle.id,
                LinehaulManifest.status.in_([
                    ManifestStatus.SEALED,
                    ManifestStatus.IN_TRANSIT,
                ])
            ).first()
            if active_manifest:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot place vehicle into maintenance: actively assigned to Linehaul Manifest {active_manifest.manifest_number}"
                )

            vehicle.status = VehicleStatus.MAINTENANCE
        else:
            if vehicle.status == VehicleStatus.MAINTENANCE:
                vehicle.status = VehicleStatus.AVAILABLE

        db.commit()
        db.refresh(vehicle)
        return vehicle
