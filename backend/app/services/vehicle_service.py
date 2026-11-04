from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.vehicle import Vehicle
from app.models.user import User
from app.models.enums import UserRole, VehicleStatus
from app.schemas.vehicle import VehicleCreate, VehicleUpdate


class VehicleService:
    @staticmethod
    def create_vehicle(db: Session, current_user: User, data: VehicleCreate) -> Vehicle:
        org_id = current_user.organization_id if current_user.role != UserRole.SUPER_ADMIN else (data.organization_id or 1)
        
        existing = db.query(Vehicle).filter(Vehicle.vehicle_number == data.vehicle_number.upper()).first()
        if existing:
            raise HTTPException(status_code=400, detail="Vehicle with this registration number already exists")

        vehicle = Vehicle(
            organization_id=org_id,
            branch_id=data.branch_id or current_user.branch_id,
            vehicle_number=data.vehicle_number.upper(),
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
            raise HTTPException(status_code=404, detail="Vehicle not found")
        if current_user and current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id or vehicle.organization_id != current_user.organization_id:
                raise HTTPException(status_code=404, detail="Vehicle not found")
            if current_user.role == UserRole.BRANCH_MANAGER and current_user.branch_id:
                if vehicle.branch_id and vehicle.branch_id != current_user.branch_id:
                    raise HTTPException(status_code=404, detail="Vehicle not found")
        return vehicle

    @staticmethod
    def update_vehicle(db: Session, vehicle_id: int, data: VehicleUpdate, current_user: Optional[User] = None) -> Vehicle:
        vehicle = VehicleService.get_vehicle(db, vehicle_id, current_user=current_user)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(vehicle, key, value)
        db.commit()
        db.refresh(vehicle)
        return vehicle

