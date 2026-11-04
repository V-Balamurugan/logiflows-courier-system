from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.vehicle import VehicleCreate, VehicleUpdate, VehicleResponse
from app.models.user import User
from app.models.enums import VehicleStatus
from app.services.vehicle_service import VehicleService
from app.dependencies.auth_deps import require_branch_manager_or_higher, require_staff

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.get("", response_model=List[VehicleResponse])
def list_vehicles(
    branch_id: Optional[int] = Query(None),
    status: Optional[VehicleStatus] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Lists vehicles in the fleet with availability status."""
    return VehicleService.list_vehicles(db, current_user, branch_id=branch_id, status=status)


@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    data: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher)
):
    """Registers a new fleet vehicle."""
    return VehicleService.create_vehicle(db, current_user, data)


@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Retrieves specific vehicle record with tenant isolation."""
    return VehicleService.get_vehicle(db, vehicle_id, current_user=current_user)


@router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: int,
    data: VehicleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher)
):
    """Updates vehicle status or maintenance state within tenant scope."""
    return VehicleService.update_vehicle(db, vehicle_id, data, current_user=current_user)

