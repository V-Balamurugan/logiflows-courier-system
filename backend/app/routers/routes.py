"""FastAPI endpoints for Phase 15 dynamic route optimization and execution."""
import asyncio
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth_deps import require_branch_manager_or_higher, require_staff, get_current_user
from app.models.enums import RouteStatus
from app.models.user import User
from app.schemas.route import (
    DeliveryRouteResponse,
    DriverTelemetryInput,
    DriverTelemetryResponse,
    RouteAllocationRecommendationResponse,
    RouteCancelRequest,
    RouteCreateRequest,
    RouteDispatchRequest,
    RoutePreviewRequest,
    RoutePreviewResponse,
    RouteReoptimizeRequest,
    RouteStopUpdateRequest,
)
from app.services.broadcaster import route_event_broadcaster
from app.services.route_service import RouteService
from app.services.routing_providers import RoutingEngine

router = APIRouter(prefix="/routes", tags=["Route Optimization"])


@router.get("/providers/health", response_model=Dict[str, Any])
def get_providers_health(
    current_user: User = Depends(require_staff),
):
    """Retrieve operational diagnostics for external routing providers and circuit breakers."""
    return RoutingEngine.get_providers_health()


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


@router.get("/{route_id}/allocation-recommendations", response_model=RouteAllocationRecommendationResponse)
def get_route_allocation_recommendations(
    route_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_branch_manager_or_higher),
):
    """Retrieve explainable ranked driver and vehicle allocation recommendations with blocking reasons."""
    return RouteService.get_route_allocation_recommendations(db, current_user, route_id)


@router.post("/{route_id}/telemetry", response_model=DriverTelemetryResponse)
def ingest_driver_telemetry(
    route_id: int,
    req: DriverTelemetryInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Ingest driver GPS stream, check freshness, and recalculate dynamic remaining ETAs."""
    return RouteService.ingest_driver_telemetry(db, current_user, route_id, req)


@router.get("/{route_id}/events")
async def stream_route_events(
    route_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Server-Sent Events (SSE) streaming endpoint for real-time route lifecycle and telemetry events.
    Yields events post-commit: ROUTE_DISPATCHED, DRIVER_ASSIGNED, ROUTE_STARTED, STOP_COMPLETED,
    DELIVERY_FAILED, ETA_CHANGED, ROUTE_DELAYED, ROUTE_REOPTIMIZED.
    """
    route = RouteService._get_route_scoped(db, current_user, route_id)
    queue = route_event_broadcaster.subscribe(str(route.id))

    async def event_generator():
        initial_data = {
            "type": "INITIAL_STATE",
            "route_id": route.id,
            "route_code": route.route_code,
            "status": route.status.value,
            "driver_id": route.driver_id,
            "vehicle_id": route.vehicle_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        yield f"data: {json.dumps(initial_data)}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event_data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event_data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            route_event_broadcaster.unsubscribe(str(route.id), queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
