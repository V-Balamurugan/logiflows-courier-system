"""FastAPI endpoints for Phase 15 dynamic route optimization and execution."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth_deps import require_branch_manager_or_higher, require_staff
from app.models.enums import RouteStatus
from app.models.user import User
from app.schemas.route import (
    DeliveryRouteResponse,
    RouteCancelRequest,
    RouteCreateRequest,
    RouteDispatchRequest,
    RoutePreviewRequest,
    RoutePreviewResponse,
    RouteReoptimizeRequest,
    RouteStopUpdateRequest,
)
from app.services.route_service import RouteService

router = APIRouter(prefix="/routes", tags=["Route Optimization"])


@router.post("/preview", response_model=RoutePreviewResponse)
def preview_route(
    req: RoutePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Compute a stateless optimized route preview with distance, duration, savings, and geometry."""
    return RouteService.preview_route(db, current_user, req)


@router.post("", response_model=DeliveryRouteResponse, status_code=status.HTTP_201_CREATED)
def create_route(
    req: RouteCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Persist an optimized multi-stop route plan in PLANNED state."""
    return RouteService.create_route(db, current_user, req)


@router.get("", response_model=List[DeliveryRouteResponse])
def list_routes(
    branch_id: Optional[int] = Query(None),
    status_filter: Optional[RouteStatus] = Query(None, alias="status"),
    vehicle_id: Optional[int] = Query(None),
    driver_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """List tenant/branch/agent-scoped route plans."""
    return RouteService.list_routes(
        db=db,
        current_user=current_user,
        branch_id=branch_id,
        status_filter=status_filter,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        skip=skip,
        limit=limit,
    )


@router.get("/{route_id}", response_model=DeliveryRouteResponse)
def get_route(
    route_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Retrieve full details, ordered stops, and polyline geometry for a single route."""
    return RouteService.get_route(db, current_user, route_id)


@router.post("/{route_id}/reoptimize", response_model=DeliveryRouteResponse)
def reoptimize_route(
    route_id: int,
    req: RouteReoptimizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Re-optimize pending stops on an active route or apply a manual permutation."""
    return RouteService.reoptimize_route(db, current_user, route_id, req)


@router.post("/{route_id}/dispatch", response_model=DeliveryRouteResponse)
def dispatch_route(
    route_id: int,
    req: RouteDispatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Atomically claim vehicle, link driver assignments, transition parcels, and dispatch route."""
    return RouteService.dispatch_route(db, current_user, route_id, req)


@router.post("/{route_id}/start", response_model=DeliveryRouteResponse)
def start_route(
    route_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Transition a DISPATCHED route into active IN_PROGRESS execution."""
    return RouteService.start_route(db, current_user, route_id)


@router.post("/{route_id}/stops/{stop_id}/update", response_model=DeliveryRouteResponse)
def update_route_stop(
    route_id: int,
    stop_id: int,
    req: RouteStopUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Update a route stop status with optional GPS coords and auto-complete route when done."""
    return RouteService.update_stop_status(db, current_user, route_id, stop_id, req)


@router.post("/{route_id}/cancel", response_model=DeliveryRouteResponse)
def cancel_route(
    route_id: int,
    req: RouteCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Cancel a route plan or active dispatch, restoring vehicle availability and parcel state."""
    return RouteService.cancel_route(db, current_user, route_id, req)
