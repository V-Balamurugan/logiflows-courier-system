"""Business logic and atomic transaction management for Phase 15 dynamic route optimization."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import secrets
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.exc import StaleDataError

from app.dependencies.auth_deps import (
    verify_branch_tenant,
    verify_employee_tenant,
    verify_vehicle_tenant,
)
from app.models.assignment import DeliveryAssignment
from app.models.branch import Branch
from app.models.enums import (
    AssignmentStatus,
    AssignmentType,
    ManifestStatus,
    ParcelStatus,
    RouteObjective,
    RouteStatus,
    RouteStopStatus,
    RouteStopType,
    ServiceType,
    UserRole,
    VehicleStatus,
    VehicleType,
)
from app.models.linehaul import BagItem, LinehaulManifest, LinehaulManifestItem
from app.models.parcel import Parcel
from app.models.route import DeliveryRoute, RouteStop
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.route import (
    DeliveryRouteResponse,
    RouteCancelRequest,
    RouteCreateRequest,
    RouteDispatchRequest,
    RoutePreviewRequest,
    RoutePreviewResponse,
    RoutePreviewStop,
    RouteReoptimizeRequest,
    RouteStopInput,
    RouteStopResponse,
    RouteStopUpdateRequest,
)
from app.services.routing_providers import (
    VEHICLE_SPEED_KMH,
    RouteComputationResult,
    RoutingEngine,
    Waypoint,
    derive_branch_vicinity_coords,
    estimate_road_distance_km,
)
from app.services.state_machine import ShipmentStateMachine


MUTABLE_STOP_STATUSES = (
    RouteStopStatus.PENDING,
    RouteStopStatus.EN_ROUTE,
)
TERMINAL_STOP_STATUSES = (
    RouteStopStatus.COMPLETED,
    RouteStopStatus.FAILED,
    RouteStopStatus.SKIPPED,
)
TERMINAL_PARCEL_STATUSES = (
    ParcelStatus.DELIVERED,
    ParcelStatus.CANCELLED,
    ParcelStatus.RETURN_TO_ORIGIN,
)
DELIVERY_ELIGIBLE_STATUSES = (
    ParcelStatus.PICKED_UP,
    ParcelStatus.AT_ORIGIN_BRANCH,
    ParcelStatus.AT_DESTINATION_BRANCH,
    ParcelStatus.DELIVERY_FAILED,
)
PICKUP_ELIGIBLE_STATUSES = (
    ParcelStatus.BOOKED,
    ParcelStatus.PICKUP_SCHEDULED,
)
PRIORITY_SERVICES = {
    ServiceType.EXPRESS,
    ServiceType.SAME_DAY,
    ServiceType.OVERNIGHT,
}


@dataclass
class _ResolvedStopInput:
    """Normalized stop metadata prior to optimizer permutation or persistence."""

    parcel: Optional[Parcel]
    stop_type: RouteStopType
    location_name: str
    address: Optional[str]
    latitude: float
    longitude: float
    coords_source: str
    parcel_weight_kg: float
    priority: int
    notes: Optional[str]


class RouteService:
    """Orchestrates stateless optimization previews, persisted route plans, and execution."""

    @staticmethod
    def _ensure_manager(current_user: User) -> None:
        if current_user.role not in (
            UserRole.SUPER_ADMIN,
            UserRole.ORG_ADMIN,
            UserRole.BRANCH_MANAGER,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only dispatch managers or admins may plan, modify, or dispatch routes",
            )

    @staticmethod
    def _validate_branch(db: Session, current_user: User, branch_id: int) -> Branch:
        branch = verify_branch_tenant(db, current_user, branch_id)
        if not branch.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Branch '{branch.branch_name}' is inactive and cannot anchor routes",
            )
        if branch.latitude is None or branch.longitude is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Branch '{branch.branch_name}' does not have depot latitude/longitude configured",
            )
        return branch

    @staticmethod
    def _validate_vehicle(
        db: Session,
        current_user: User,
        branch: Branch,
        vehicle_id: int,
        total_weight_kg: float = 0.0,
        require_available: bool = False,
        exclude_route_id: Optional[int] = None,
    ) -> Vehicle:
        vehicle = verify_vehicle_tenant(db, current_user, vehicle_id)
        if vehicle.organization_id != branch.organization_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Selected vehicle belongs to a different organization than the route branch",
            )
        if vehicle.branch_id is not None and vehicle.branch_id != branch.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Vehicle {vehicle.vehicle_number} is assigned to a different branch hub",
            )
        if not vehicle.is_active or vehicle.status == VehicleStatus.RETIRED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle {vehicle.vehicle_number} is retired or inactive",
            )
        if require_available:
            if vehicle.status != VehicleStatus.AVAILABLE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Vehicle {vehicle.vehicle_number} is currently '{vehicle.status.value}' and unavailable for dispatch",
                )
            route_conflict_q = db.query(DeliveryRoute).filter(
                DeliveryRoute.vehicle_id == vehicle.id,
                DeliveryRoute.is_active_dispatch == True,
            )
            if exclude_route_id is not None:
                route_conflict_q = route_conflict_q.filter(DeliveryRoute.id != exclude_route_id)
            conflict_route = route_conflict_q.first()
            if conflict_route:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Vehicle {vehicle.vehicle_number} is already dispatched on route {conflict_route.route_code}",
                )
            conflict_manifest = (
                db.query(LinehaulManifest)
                .filter(
                    LinehaulManifest.vehicle_id == vehicle.id,
                    LinehaulManifest.status.in_(
                        [ManifestStatus.DRAFT, ManifestStatus.SEALED, ManifestStatus.IN_TRANSIT]
                    ),
                )
                .first()
            )
            if conflict_manifest:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Vehicle {vehicle.vehicle_number} is locked on linehaul manifest {conflict_manifest.manifest_number}",
                )
            if float(total_weight_kg) > float(vehicle.max_weight_kg):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Route cargo weight {total_weight_kg:.2f} kg exceeds vehicle "
                        f"{vehicle.vehicle_number} capacity {vehicle.max_weight_kg:.2f} kg"
                    ),
                )
        else:
            if vehicle.status == VehicleStatus.MAINTENANCE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Vehicle {vehicle.vehicle_number} is in MAINTENANCE",
                )
            if total_weight_kg > 0 and float(total_weight_kg) > float(vehicle.max_weight_kg):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Route cargo weight {total_weight_kg:.2f} kg exceeds vehicle "
                        f"{vehicle.vehicle_number} capacity {vehicle.max_weight_kg:.2f} kg"
                    ),
                )
        return vehicle

    @staticmethod
    def _validate_driver(db: Session, current_user: User, branch: Branch, driver_id: int) -> User:
        driver = verify_employee_tenant(db, current_user, driver_id)
        if driver.organization_id != branch.organization_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Selected driver belongs to a different organization",
            )
        if not driver.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Selected driver account is inactive",
            )
        if driver.role not in (UserRole.DELIVERY_AGENT, UserRole.BRANCH_MANAGER):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected driver must hold DELIVERY_AGENT or BRANCH_MANAGER role",
            )
        if driver.branch_id is not None and driver.branch_id != branch.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Selected driver is assigned to a different branch hub",
            )
        return driver

    @staticmethod
    def _generate_route_code(db: Session, branch: Branch) -> str:
        prefix = (branch.branch_code or "HUB").upper().replace(" ", "")[:8]
        date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
        for _ in range(10):
            candidate = f"RTE-{prefix}-{date_part}-{secrets.token_hex(2).upper()}"
            exists = db.query(DeliveryRoute.id).filter(DeliveryRoute.route_code == candidate).first()
            if not exists:
                return candidate
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to allocate unique route code",
        )

    @staticmethod
    def _verify_parcel_for_route(
        db: Session,
        current_user: User,
        branch: Branch,
        parcel: Parcel,
        stop_type: RouteStopType,
        strict_lock_check: bool,
    ) -> None:
        origin_org_id = parcel.origin_branch.organization_id if parcel.origin_branch else None
        dest_org_id = parcel.dest_branch.organization_id if parcel.dest_branch else None
        if branch.organization_id not in (origin_org_id, dest_org_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

        if branch.id not in (parcel.origin_branch_id, parcel.dest_branch_id):
            if current_user.role == UserRole.BRANCH_MANAGER:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Parcel {parcel.tracking_number} does not originate at or terminate at branch '{branch.branch_name}'",
            )

        if not strict_lock_check:
            return

        if parcel.delivery_status in TERMINAL_PARCEL_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Parcel {parcel.tracking_number} is already in terminal state '{parcel.delivery_status.value}'",
            )
        if parcel.delivery_status == ParcelStatus.ON_HOLD:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Parcel {parcel.tracking_number} is currently ON_HOLD and cannot be routed",
            )
        if stop_type == RouteStopType.PICKUP and parcel.delivery_status not in PICKUP_ELIGIBLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Parcel {parcel.tracking_number} cannot be scheduled for PICKUP while '{parcel.delivery_status.value}'",
            )
        if stop_type == RouteStopType.DELIVERY and parcel.delivery_status not in DELIVERY_ELIGIBLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Parcel {parcel.tracking_number} cannot be scheduled for DELIVERY while '{parcel.delivery_status.value}'",
            )

        active_stop = (
            db.query(RouteStop)
            .filter(RouteStop.parcel_id == parcel.id, RouteStop.is_active == True)
            .first()
        )
        if active_stop:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Parcel {parcel.tracking_number} is already allocated to an active route stop",
            )

        active_assignment = (
            db.query(DeliveryAssignment)
            .filter(
                DeliveryAssignment.parcel_id == parcel.id,
                DeliveryAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS]),
            )
            .first()
        )
        if active_assignment:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Parcel {parcel.tracking_number} already has an active delivery assignment",
            )

        active_bag = (
            db.query(BagItem)
            .filter(BagItem.parcel_id == parcel.id, BagItem.is_active == True)
            .first()
        )
        if active_bag:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Parcel {parcel.tracking_number} is sealed/packed in an active consolidation bag",
            )

        active_manifest = (
            db.query(LinehaulManifestItem)
            .filter(LinehaulManifestItem.parcel_id == parcel.id, LinehaulManifestItem.is_active == True)
            .first()
        )
        if active_manifest:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Parcel {parcel.tracking_number} is currently loaded on an active linehaul manifest",
            )

    @staticmethod
    def _resolve_stops(
        db: Session,
        current_user: User,
        branch: Branch,
        stops_input: Optional[List[RouteStopInput]],
        parcel_ids_input: Optional[List[int]],
        strict_lock_check: bool,
    ) -> List[_ResolvedStopInput]:
        normalized_inputs: List[RouteStopInput] = list(stops_input or [])
        seen_parcel_ids = {s.parcel_id for s in normalized_inputs if s.parcel_id is not None}

        if parcel_ids_input:
            for pid in parcel_ids_input:
                if pid in seen_parcel_ids:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=f"Duplicate parcel_id {pid} provided across stops and parcel_ids",
                    )
                seen_parcel_ids.add(pid)
                normalized_inputs.append(RouteStopInput(parcel_id=pid, stop_type=RouteStopType.DELIVERY))

        if not normalized_inputs:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="At least one stop or parcel_id is required",
            )

        parcels_by_id: Dict[int, Parcel] = {}
        if seen_parcel_ids:
            parcels = (
                db.query(Parcel)
                .options(joinedload(Parcel.origin_branch), joinedload(Parcel.dest_branch))
                .filter(Parcel.id.in_(list(seen_parcel_ids)))
                .all()
            )
            parcels_by_id = {p.id: p for p in parcels}

        resolved: List[_ResolvedStopInput] = []
        for item in normalized_inputs:
            if item.parcel_id is None:
                resolved.append(
                    _ResolvedStopInput(
                        parcel=None,
                        stop_type=item.stop_type,
                        location_name=item.location_name or "Waypoint",
                        address=item.address,
                        latitude=float(item.latitude),
                        longitude=float(item.longitude),
                        coords_source="EXPLICIT",
                        parcel_weight_kg=0.0,
                        priority=0,
                        notes=item.notes,
                    )
                )
                continue

            parcel = parcels_by_id.get(item.parcel_id)
            if not parcel:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

            RouteService._verify_parcel_for_route(
                db=db,
                current_user=current_user,
                branch=branch,
                parcel=parcel,
                stop_type=item.stop_type,
                strict_lock_check=strict_lock_check,
            )

            is_pickup = item.stop_type == RouteStopType.PICKUP
            if item.latitude is not None and item.longitude is not None:
                lat, lng = float(item.latitude), float(item.longitude)
                coords_source = "EXPLICIT"
            elif is_pickup and parcel.origin_latitude is not None and parcel.origin_longitude is not None:
                lat, lng = float(parcel.origin_latitude), float(parcel.origin_longitude)
                coords_source = "PARCEL_STORED"
            elif not is_pickup and parcel.dest_latitude is not None and parcel.dest_longitude is not None:
                lat, lng = float(parcel.dest_latitude), float(parcel.dest_longitude)
                coords_source = "PARCEL_STORED"
            else:
                pincode = (
                    parcel.sender_pincode if is_pickup else parcel.receiver_pincode
                ) or branch.pincode
                lat, lng = derive_branch_vicinity_coords(
                    float(branch.latitude),
                    float(branch.longitude),
                    pincode,
                    parcel.tracking_number,
                )
                coords_source = "BRANCH_VICINITY_ESTIMATE"

            default_loc = (
                f"{parcel.sender_name} ({parcel.sender_city})"
                if is_pickup
                else f"{parcel.receiver_name} ({parcel.receiver_city})"
            )
            default_addr = (
                f"{parcel.sender_address}, {parcel.sender_city} {parcel.sender_pincode}"
                if is_pickup
                else f"{parcel.receiver_address}, {parcel.receiver_city} {parcel.receiver_pincode}"
            )
            resolved.append(
                _ResolvedStopInput(
                    parcel=parcel,
                    stop_type=item.stop_type,
                    location_name=item.location_name or default_loc,
                    address=item.address or default_addr,
                    latitude=lat,
                    longitude=lng,
                    coords_source=coords_source,
                    parcel_weight_kg=float(parcel.weight_kg or 0.0),
                    priority=1 if parcel.service_type in PRIORITY_SERVICES else 0,
                    notes=item.notes,
                )
            )
        return resolved

    @staticmethod
    def _get_route_scoped(db: Session, current_user: User, route_id: int) -> DeliveryRoute:
        route = (
            db.query(DeliveryRoute)
            .options(
                joinedload(DeliveryRoute.branch),
                joinedload(DeliveryRoute.vehicle),
                joinedload(DeliveryRoute.driver),
                joinedload(DeliveryRoute.stops).joinedload(RouteStop.parcel),
            )
            .filter(DeliveryRoute.id == route_id)
            .first()
        )
        if not route:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

        if current_user.role == UserRole.SUPER_ADMIN:
            return route

        if not current_user.organization_id or route.organization_id != current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

        if current_user.role == UserRole.BRANCH_MANAGER:
            if current_user.branch_id and route.branch_id != current_user.branch_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
        elif current_user.role == UserRole.DELIVERY_AGENT:
            if route.driver_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
        elif current_user.role == UserRole.CUSTOMER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Customers cannot access internal dispatch routes",
            )
        return route

    @staticmethod
    def _parse_geometry(route_geometry: Optional[str]) -> List[List[float]]:
        if not route_geometry:
            return []
        try:
            parsed = json.loads(route_geometry)
            if isinstance(parsed, list):
                return [[float(pt[0]), float(pt[1])] for pt in parsed if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        except Exception:
            return []
        return []

    @staticmethod
    def to_route_response(route: DeliveryRoute) -> DeliveryRouteResponse:
        max_w = float(route.vehicle.max_weight_kg) if route.vehicle else None
        util_pct = round((float(route.total_weight_kg) / max_w) * 100.0, 1) if max_w and max_w > 0 else None
        saved_pct = (
            round((float(route.distance_saved_km) / float(route.baseline_distance_km)) * 100.0, 1)
            if route.baseline_distance_km and route.baseline_distance_km > 0
            else 0.0
        )
        ordered_stops = sorted(route.stops, key=lambda s: s.sequence_order)
        stop_responses = [
            RouteStopResponse(
                id=s.id,
                route_id=s.route_id,
                parcel_id=s.parcel_id,
                tracking_number=s.parcel.tracking_number if s.parcel else None,
                receiver_name=s.parcel.receiver_name if s.parcel else None,
                parcel_weight_kg=float(s.parcel.weight_kg) if s.parcel else None,
                assignment_id=s.assignment_id,
                sequence_order=s.sequence_order,
                stop_type=s.stop_type,
                status=s.status,
                is_active=s.is_active,
                location_name=s.location_name,
                address=s.address,
                latitude=s.latitude,
                longitude=s.longitude,
                coords_source=s.coords_source,
                distance_from_prev_km=s.distance_from_prev_km,
                eta_minutes_from_start=s.eta_minutes_from_start,
                estimated_arrival_at=s.estimated_arrival_at,
                arrived_at=s.arrived_at,
                completed_at=s.completed_at,
                failure_reason=s.failure_reason,
                notes=s.notes,
            )
            for s in ordered_stops
        ]
        return DeliveryRouteResponse(
            id=route.id,
            route_code=route.route_code,
            organization_id=route.organization_id,
            branch_id=route.branch_id,
            branch_name=route.branch.branch_name if route.branch else None,
            vehicle_id=route.vehicle_id,
            vehicle_number=route.vehicle.vehicle_number if route.vehicle else None,
            vehicle_type=route.vehicle.vehicle_type.value if route.vehicle else None,
            vehicle_max_weight_kg=max_w,
            driver_id=route.driver_id,
            driver_name=route.driver.full_name if route.driver else None,
            status=route.status,
            is_active_dispatch=route.is_active_dispatch,
            optimization_objective=route.optimization_objective,
            provider_used=route.provider_used,
            is_fallback=route.is_fallback,
            fallback_reason=route.fallback_reason,
            return_to_hub=route.return_to_hub,
            start_latitude=route.start_latitude,
            start_longitude=route.start_longitude,
            total_distance_km=route.total_distance_km,
            baseline_distance_km=route.baseline_distance_km,
            distance_saved_km=route.distance_saved_km,
            distance_saved_pct=saved_pct,
            estimated_duration_min=route.estimated_duration_min,
            total_weight_kg=route.total_weight_kg,
            utilization_pct=util_pct,
            total_stops=route.total_stops,
            completed_stops=route.completed_stops,
            geometry_points=RouteService._parse_geometry(route.route_geometry),
            notes=route.notes,
            version_id=route.version_id,
            dispatched_at=route.dispatched_at,
            started_at=route.started_at,
            completed_at=route.completed_at,
            cancelled_at=route.cancelled_at,
            created_at=route.created_at,
            updated_at=route.updated_at,
            stops=stop_responses,
        )

    @staticmethod
    def preview_route(
        db: Session, current_user: User, req: RoutePreviewRequest
    ) -> RoutePreviewResponse:
        RouteService._ensure_manager(current_user)
        branch = RouteService._validate_branch(db, current_user, req.branch_id)

        vehicle: Optional[Vehicle] = None
        if req.vehicle_id is not None:
            vehicle = verify_vehicle_tenant(db, current_user, req.vehicle_id)
            if vehicle.organization_id != branch.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Selected vehicle belongs to a different organization",
                )
            if vehicle.branch_id is not None and vehicle.branch_id != branch.id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Vehicle {vehicle.vehicle_number} belongs to a different branch hub",
                )

        resolved_stops = RouteService._resolve_stops(
            db=db,
            current_user=current_user,
            branch=branch,
            stops_input=req.stops,
            parcel_ids_input=req.parcel_ids,
            strict_lock_check=False,
        )

        total_weight = round(sum(s.parcel_weight_kg for s in resolved_stops), 2)
        waypoints = [
            Waypoint(
                index=idx,
                latitude=s.latitude,
                longitude=s.longitude,
                label=s.location_name,
                priority=s.priority,
            )
            for idx, s in enumerate(resolved_stops)
        ]

        comp: RouteComputationResult = RoutingEngine.compute_route(
            start=(float(branch.latitude), float(branch.longitude)),
            waypoints=waypoints,
            vehicle_type=vehicle.vehicle_type if vehicle else VehicleType.VAN,
            objective=req.objective.value,
            provider=req.provider,
            return_to_hub=req.return_to_hub,
        )

        preview_stops: List[RoutePreviewStop] = []
        cum_eta = 0.0
        for seq_pos, orig_idx in enumerate(comp.ordered_indices):
            s = resolved_stops[orig_idx]
            leg_dist = comp.leg_distances_km[seq_pos] if seq_pos < len(comp.leg_distances_km) else 0.0
            leg_dur = comp.leg_durations_min[seq_pos] if seq_pos < len(comp.leg_durations_min) else 0.0
            cum_eta = round(cum_eta + leg_dur, 1)
            preview_stops.append(
                RoutePreviewStop(
                    sequence_order=seq_pos + 1,
                    parcel_id=s.parcel.id if s.parcel else None,
                    tracking_number=s.parcel.tracking_number if s.parcel else None,
                    stop_type=s.stop_type,
                    location_name=s.location_name,
                    address=s.address,
                    latitude=s.latitude,
                    longitude=s.longitude,
                    coords_source=s.coords_source,
                    parcel_weight_kg=s.parcel_weight_kg,
                    distance_from_prev_km=round(leg_dist, 3),
                    eta_minutes_from_start=cum_eta,
                )
            )

        max_w = float(vehicle.max_weight_kg) if vehicle else None
        util_pct = round((total_weight / max_w) * 100.0, 1) if max_w and max_w > 0 else None
        cap_exceeded = bool(max_w is not None and total_weight > max_w)

        return RoutePreviewResponse(
            branch_id=branch.id,
            branch_name=branch.branch_name,
            start_latitude=float(branch.latitude),
            start_longitude=float(branch.longitude),
            vehicle_id=vehicle.id if vehicle else None,
            vehicle_number=vehicle.vehicle_number if vehicle else None,
            vehicle_max_weight_kg=max_w,
            total_weight_kg=total_weight,
            utilization_pct=util_pct,
            capacity_exceeded=cap_exceeded,
            objective=req.objective,
            return_to_hub=req.return_to_hub,
            provider_used=comp.provider_used,
            is_fallback=comp.is_fallback,
            fallback_reason=comp.fallback_reason,
            baseline_distance_km=comp.baseline_distance_km,
            total_distance_km=comp.total_distance_km,
            distance_saved_km=comp.distance_saved_km,
            distance_saved_pct=comp.distance_saved_pct,
            estimated_duration_min=comp.total_duration_min,
            geometry_points=[[float(lat), float(lng)] for lat, lng in comp.geometry_points],
            stops=preview_stops,
        )

    @staticmethod
    def create_route(
        db: Session, current_user: User, req: RouteCreateRequest
    ) -> DeliveryRouteResponse:
        RouteService._ensure_manager(current_user)
        branch = RouteService._validate_branch(db, current_user, req.branch_id)
        resolved_stops = RouteService._resolve_stops(
            db=db,
            current_user=current_user,
            branch=branch,
            stops_input=req.stops,
            parcel_ids_input=req.parcel_ids,
            strict_lock_check=True,
        )

        total_weight = round(sum(s.parcel_weight_kg for s in resolved_stops), 2)
        vehicle: Optional[Vehicle] = None
        if req.vehicle_id is not None:
            vehicle = RouteService._validate_vehicle(
                db, current_user, branch, req.vehicle_id, total_weight_kg=total_weight
            )
        driver: Optional[User] = None
        if req.driver_id is not None:
            driver = RouteService._validate_driver(db, current_user, branch, req.driver_id)

        waypoints = [
            Waypoint(
                index=idx,
                latitude=s.latitude,
                longitude=s.longitude,
                label=s.location_name,
                priority=s.priority,
            )
            for idx, s in enumerate(resolved_stops)
        ]
        comp = RoutingEngine.compute_route(
            start=(float(branch.latitude), float(branch.longitude)),
            waypoints=waypoints,
            vehicle_type=vehicle.vehicle_type if vehicle else VehicleType.VAN,
            objective=req.objective.value,
            provider=req.provider,
            return_to_hub=req.return_to_hub,
        )

        now = datetime.now(timezone.utc)
        route = DeliveryRoute(
            route_code=RouteService._generate_route_code(db, branch),
            organization_id=branch.organization_id,
            branch_id=branch.id,
            vehicle_id=vehicle.id if vehicle else None,
            driver_id=driver.id if driver else None,
            status=RouteStatus.PLANNED,
            is_active_dispatch=False,
            optimization_objective=req.objective,
            provider_used=comp.provider_used,
            is_fallback=comp.is_fallback,
            fallback_reason=comp.fallback_reason,
            return_to_hub=req.return_to_hub,
            start_latitude=float(branch.latitude),
            start_longitude=float(branch.longitude),
            total_distance_km=comp.total_distance_km,
            baseline_distance_km=comp.baseline_distance_km,
            distance_saved_km=comp.distance_saved_km,
            estimated_duration_min=comp.total_duration_min,
            total_weight_kg=total_weight,
            total_stops=len(resolved_stops),
            completed_stops=0,
            route_geometry=json.dumps([[float(lat), float(lng)] for lat, lng in comp.geometry_points]),
            notes=req.notes,
            created_by_id=current_user.id,
        )

        try:
            db.add(route)
            db.flush()

            cum_eta = 0.0
            for seq_pos, orig_idx in enumerate(comp.ordered_indices):
                s = resolved_stops[orig_idx]
                leg_dist = comp.leg_distances_km[seq_pos] if seq_pos < len(comp.leg_distances_km) else 0.0
                leg_dur = comp.leg_durations_min[seq_pos] if seq_pos < len(comp.leg_durations_min) else 0.0
                cum_eta = round(cum_eta + leg_dur, 1)
                db.add(
                    RouteStop(
                        route_id=route.id,
                        parcel_id=s.parcel.id if s.parcel else None,
                        sequence_order=seq_pos + 1,
                        stop_type=s.stop_type,
                        status=RouteStopStatus.PENDING,
                        is_active=(s.parcel is not None),
                        location_name=s.location_name,
                        address=s.address,
                        latitude=s.latitude,
                        longitude=s.longitude,
                        coords_source=s.coords_source,
                        distance_from_prev_km=round(leg_dist, 3),
                        eta_minutes_from_start=cum_eta,
                        estimated_arrival_at=now + timedelta(minutes=cum_eta),
                        notes=s.notes,
                    )
                )
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="One or more parcels or resources were claimed concurrently by another route",
            )

        return RouteService.get_route(db, current_user, route.id)

    @staticmethod
    def list_routes(
        db: Session,
        current_user: User,
        branch_id: Optional[int] = None,
        status_filter: Optional[RouteStatus] = None,
        vehicle_id: Optional[int] = None,
        driver_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DeliveryRouteResponse]:
        if current_user.role == UserRole.CUSTOMER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Customers cannot access internal dispatch routes",
            )

        q = db.query(DeliveryRoute).options(
            joinedload(DeliveryRoute.branch),
            joinedload(DeliveryRoute.vehicle),
            joinedload(DeliveryRoute.driver),
            joinedload(DeliveryRoute.stops).joinedload(RouteStop.parcel),
        )

        if current_user.role != UserRole.SUPER_ADMIN:
            if not current_user.organization_id:
                return []
            q = q.filter(DeliveryRoute.organization_id == current_user.organization_id)
            if current_user.role == UserRole.BRANCH_MANAGER and current_user.branch_id:
                q = q.filter(DeliveryRoute.branch_id == current_user.branch_id)
            elif current_user.role == UserRole.DELIVERY_AGENT:
                q = q.filter(DeliveryRoute.driver_id == current_user.id)

        if branch_id is not None:
            q = q.filter(DeliveryRoute.branch_id == branch_id)
        if status_filter is not None:
            q = q.filter(DeliveryRoute.status == status_filter)
        if vehicle_id is not None:
            q = q.filter(DeliveryRoute.vehicle_id == vehicle_id)
        if driver_id is not None:
            q = q.filter(DeliveryRoute.driver_id == driver_id)

        routes = q.order_by(DeliveryRoute.id.desc()).offset(skip).limit(limit).all()
        return [RouteService.to_route_response(r) for r in routes]

    @staticmethod
    def get_route(db: Session, current_user: User, route_id: int) -> DeliveryRouteResponse:
        route = RouteService._get_route_scoped(db, current_user, route_id)
        return RouteService.to_route_response(route)

    @staticmethod
    def reoptimize_route(
        db: Session, current_user: User, route_id: int, req: RouteReoptimizeRequest
    ) -> DeliveryRouteResponse:
        RouteService._ensure_manager(current_user)
        route = RouteService._get_route_scoped(db, current_user, route_id)
        if route.status in (RouteStatus.COMPLETED, RouteStatus.CANCELLED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot re-optimize a route in '{route.status.value}' status",
            )
        if req.expected_version_id is not None and route.version_id != req.expected_version_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Route version conflict (expected {req.expected_version_id}, current {route.version_id})",
            )

        ordered_stops = sorted(route.stops, key=lambda s: s.sequence_order)
        if not ordered_stops:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Route has no stops to re-optimize",
            )

        # Keep all already-progressed stops fixed ahead of mutable pending/en-route stops
        fixed_prefix = [s for s in ordered_stops if s.status not in MUTABLE_STOP_STATUSES]
        mutable_stops = [s for s in ordered_stops if s.status in MUTABLE_STOP_STATUSES]

        if not mutable_stops:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="All stops on this route are already completed or arrived; nothing remains to reorder",
            )

        return_to_hub = req.return_to_hub if req.return_to_hub is not None else route.return_to_hub
        if req.objective == RouteObjective.MANUAL:
            if not req.manual_stop_ids or set(req.manual_stop_ids) != {s.id for s in mutable_stops}:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="manual_stop_ids must contain the exact set of pending/en-route stop IDs on this route",
                )
            stops_by_id = {s.id: s for s in mutable_stops}
            input_stops = [stops_by_id[sid] for sid in req.manual_stop_ids]
        else:
            input_stops = list(mutable_stops)

        hub_lat = float(route.start_latitude or (route.branch.latitude if route.branch else 0.0))
        hub_lng = float(route.start_longitude or (route.branch.longitude if route.branch else 0.0))
        start_coord = (
            (float(fixed_prefix[-1].latitude), float(fixed_prefix[-1].longitude))
            if fixed_prefix
            else (hub_lat, hub_lng)
        )

        waypoints = [
            Waypoint(
                index=idx,
                latitude=s.latitude,
                longitude=s.longitude,
                label=s.location_name,
                priority=1 if (s.parcel and s.parcel.service_type in PRIORITY_SERVICES) else 0,
            )
            for idx, s in enumerate(input_stops)
        ]
        veh_type = route.vehicle.vehicle_type if route.vehicle else VehicleType.VAN
        comp = RoutingEngine.compute_route(
            start=start_coord,
            waypoints=waypoints,
            vehicle_type=veh_type,
            objective=req.objective.value,
            provider=req.provider,
            return_to_hub=(return_to_hub and not fixed_prefix),
        )

        reordered_mutable = [input_stops[idx] for idx in comp.ordered_indices]
        new_full_stops = fixed_prefix + reordered_mutable

        now = datetime.now(timezone.utc)
        fixed_dist = round(sum(float(s.distance_from_prev_km or 0.0) for s in fixed_prefix), 3)
        fixed_eta = float(fixed_prefix[-1].eta_minutes_from_start) if fixed_prefix else 0.0
        cum_eta = fixed_eta

        for pos, stop_obj in enumerate(reordered_mutable):
            leg_dist = comp.leg_distances_km[pos] if pos < len(comp.leg_distances_km) else 0.0
            leg_dur = comp.leg_durations_min[pos] if pos < len(comp.leg_durations_min) else 0.0
            cum_eta = round(cum_eta + leg_dur, 1)
            stop_obj.sequence_order = len(fixed_prefix) + pos + 1
            stop_obj.distance_from_prev_km = round(leg_dist, 3)
            stop_obj.eta_minutes_from_start = cum_eta
            stop_obj.estimated_arrival_at = now + timedelta(minutes=cum_eta)

        # Build complete route geometry starting at depot through all ordered stops
        full_geom: List[List[float]] = [[round(hub_lat, 6), round(hub_lng, 6)]]
        if not fixed_prefix and comp.geometry_points:
            full_geom = [[float(lat), float(lng)] for lat, lng in comp.geometry_points]
        else:
            for fs_idx, fs in enumerate(fixed_prefix):
                fs.sequence_order = fs_idx + 1
                full_geom.append([round(fs.latitude, 6), round(fs.longitude, 6)])
            for lat, lng in comp.geometry_points[1:]:
                full_geom.append([float(lat), float(lng)])
            if return_to_hub and fixed_prefix:
                tail = new_full_stops[-1]
                back_km = round(estimate_road_distance_km(tail.latitude, tail.longitude, hub_lat, hub_lng), 3)
                back_min = (back_km / VEHICLE_SPEED_KMH.get(veh_type, 35.0)) * 60.0
                cum_eta = round(cum_eta + back_min, 1)
                full_geom.append([round(hub_lat, 6), round(hub_lng, 6)])
                comp_tail_dist = back_km
            else:
                comp_tail_dist = 0.0
            route_total_extra = comp_tail_dist
        if not fixed_prefix:
            route_total_extra = 0.0

        total_distance = round(fixed_dist + comp.total_distance_km + route_total_extra, 2)
        baseline_distance = max(route.baseline_distance_km or 0.0, total_distance) if route.status != RouteStatus.PLANNED else comp.baseline_distance_km
        if req.objective == RouteObjective.MANUAL:
            # Keep original unoptimized baseline when manually reordering so savings accurately reflect manual vs baseline
            baseline_distance = max(route.baseline_distance_km or 0.0, comp.baseline_distance_km)
        saved_km = round(max(0.0, baseline_distance - total_distance), 2)

        route.optimization_objective = req.objective
        route.return_to_hub = return_to_hub
        route.provider_used = comp.provider_used
        route.is_fallback = comp.is_fallback
        route.fallback_reason = comp.fallback_reason
        route.baseline_distance_km = round(baseline_distance, 2)
        route.total_distance_km = total_distance
        route.distance_saved_km = saved_km
        route.estimated_duration_min = comp.total_duration_min if not fixed_prefix else round(cum_eta, 1)
        route.route_geometry = json.dumps(full_geom)
        route.updated_at = now

        try:
            db.commit()
        except StaleDataError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Route was modified concurrently. Please refresh and retry.",
            )

        return RouteService.get_route(db, current_user, route.id)

    @staticmethod
    def dispatch_route(
        db: Session, current_user: User, route_id: int, req: RouteDispatchRequest
    ) -> DeliveryRouteResponse:
        RouteService._ensure_manager(current_user)
        route = RouteService._get_route_scoped(db, current_user, route_id)
        if route.status != RouteStatus.PLANNED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only PLANNED routes can be dispatched (current: '{route.status.value}')",
            )
        if req.expected_version_id is not None and route.version_id != req.expected_version_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Route version conflict (expected {req.expected_version_id}, current {route.version_id})",
            )

        ordered_stops = sorted(route.stops, key=lambda s: s.sequence_order)
        if not ordered_stops:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Cannot dispatch an empty route with zero stops",
            )

        vehicle_id = req.vehicle_id or route.vehicle_id
        driver_id = req.driver_id or route.driver_id
        if not vehicle_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="A vehicle_id must be selected before dispatching a route",
            )
        if not driver_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="A driver_id must be selected before dispatching a route",
            )

        branch = RouteService._validate_branch(db, current_user, route.branch_id)
        vehicle = RouteService._validate_vehicle(
            db,
            current_user,
            branch,
            vehicle_id,
            total_weight_kg=float(route.total_weight_kg or 0.0),
            require_available=True,
            exclude_route_id=route.id,
        )
        driver = RouteService._validate_driver(db, current_user, branch, driver_id)

        # Atomic conditional CAS lock on vehicle eliminates double-dispatch races
        veh_lock = db.execute(
            update(Vehicle)
            .where(Vehicle.id == vehicle.id, Vehicle.status == VehicleStatus.AVAILABLE)
            .values(status=VehicleStatus.ASSIGNED)
        )
        if veh_lock.rowcount == 0:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle {vehicle.vehicle_number} was dispatched concurrently; please retry with another vehicle",
            )

        now = datetime.now(timezone.utc)
        broadcasts: List[Dict[str, Any]] = []

        try:
            for stop_obj in ordered_stops:
                stop_obj.estimated_arrival_at = now + timedelta(minutes=float(stop_obj.eta_minutes_from_start or 0.0))
                parcel = stop_obj.parcel
                if not parcel:
                    continue

                if parcel.delivery_status in TERMINAL_PARCEL_STATUSES or parcel.delivery_status == ParcelStatus.ON_HOLD:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Parcel {parcel.tracking_number} cannot be dispatched in '{parcel.delivery_status.value}' status",
                    )

                existing_assign = (
                    db.query(DeliveryAssignment)
                    .filter(
                        DeliveryAssignment.parcel_id == parcel.id,
                        DeliveryAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS]),
                    )
                    .first()
                )
                if existing_assign:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Parcel {parcel.tracking_number} already has an active delivery assignment",
                    )

                active_bag = (
                    db.query(BagItem)
                    .filter(BagItem.parcel_id == parcel.id, BagItem.is_active == True)
                    .first()
                )
                active_manifest = (
                    db.query(LinehaulManifestItem)
                    .filter(LinehaulManifestItem.parcel_id == parcel.id, LinehaulManifestItem.is_active == True)
                    .first()
                )
                if active_bag or active_manifest:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Parcel {parcel.tracking_number} is locked on an active linehaul bag or manifest",
                    )

                assign_type = (
                    AssignmentType.PICKUP
                    if stop_obj.stop_type == RouteStopType.PICKUP
                    else AssignmentType.LAST_MILE
                )
                assignment = DeliveryAssignment(
                    parcel_id=parcel.id,
                    employee_id=driver.id,
                    vehicle_id=vehicle.id,
                    assignment_type=assign_type,
                    status=AssignmentStatus.ASSIGNED,
                    notes=f"Route {route.route_code} Stop #{stop_obj.sequence_order}",
                )
                db.add(assignment)
                db.flush()
                stop_obj.assignment_id = assignment.id

                remarks = (
                    f"Dispatched on route {route.route_code} "
                    f"(Stop #{stop_obj.sequence_order}, Vehicle {vehicle.vehicle_number})"
                )
                if stop_obj.stop_type == RouteStopType.PICKUP:
                    if parcel.delivery_status == ParcelStatus.BOOKED:
                        ShipmentStateMachine.transition(
                            db=db,
                            current_user=current_user,
                            parcel=parcel,
                            to_status=ParcelStatus.PICKUP_SCHEDULED,
                            remarks=remarks,
                            location_name=branch.branch_name,
                            branch_id=branch.id,
                            source="ROUTE_DISPATCH",
                            commit=False,
                        )
                        broadcasts.append(
                            {
                                "tracking_number": parcel.tracking_number,
                                "to_status": ParcelStatus.PICKUP_SCHEDULED,
                                "location": branch.branch_name,
                                "remarks": remarks,
                                "timestamp": now,
                            }
                        )
                    elif parcel.delivery_status != ParcelStatus.PICKUP_SCHEDULED:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Parcel {parcel.tracking_number} is not eligible for PICKUP dispatch ({parcel.delivery_status.value})",
                        )
                else:
                    if parcel.delivery_status not in DELIVERY_ELIGIBLE_STATUSES:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Parcel {parcel.tracking_number} is not eligible for DELIVERY dispatch ({parcel.delivery_status.value})",
                        )
                    ShipmentStateMachine.transition(
                        db=db,
                        current_user=current_user,
                        parcel=parcel,
                        to_status=ParcelStatus.OUT_FOR_DELIVERY,
                        remarks=remarks,
                        location_name=branch.branch_name,
                        branch_id=branch.id,
                        source="ROUTE_DISPATCH",
                        commit=False,
                    )
                    broadcasts.append(
                        {
                            "tracking_number": parcel.tracking_number,
                            "to_status": ParcelStatus.OUT_FOR_DELIVERY,
                            "location": branch.branch_name,
                            "remarks": remarks,
                            "timestamp": now,
                        }
                    )

            route.vehicle_id = vehicle.id
            route.driver_id = driver.id
            route.status = RouteStatus.DISPATCHED
            route.is_active_dispatch = True
            route.dispatched_at = now
            route.updated_at = now
            if req.notes:
                route.notes = f"{route.notes} | Dispatch: {req.notes}" if route.notes else req.notes

            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except (IntegrityError, StaleDataError):
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Concurrent dispatch conflict on route, vehicle, or parcel; please refresh and retry",
            )
        except Exception:
            db.rollback()
            raise

        for b in broadcasts:
            ShipmentStateMachine.broadcast_milestone(**b)

        return RouteService.get_route(db, current_user, route.id)

    @staticmethod
    def start_route(db: Session, current_user: User, route_id: int) -> DeliveryRouteResponse:
        route = RouteService._get_route_scoped(db, current_user, route_id)
        if route.status != RouteStatus.DISPATCHED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only DISPATCHED routes can be started (current: '{route.status.value}')",
            )

        now = datetime.now(timezone.utc)
        route.status = RouteStatus.IN_PROGRESS
        route.started_at = now
        route.updated_at = now
        if route.vehicle and route.vehicle.status in (VehicleStatus.AVAILABLE, VehicleStatus.ASSIGNED):
            route.vehicle.status = VehicleStatus.IN_TRANSIT

        ordered_stops = sorted(route.stops, key=lambda s: s.sequence_order)
        for s in ordered_stops:
            if s.assignment and s.assignment.status == AssignmentStatus.ASSIGNED:
                s.assignment.status = AssignmentStatus.IN_PROGRESS
        first_pending = next((s for s in ordered_stops if s.status == RouteStopStatus.PENDING), None)
        if first_pending:
            first_pending.status = RouteStopStatus.EN_ROUTE

        db.commit()
        return RouteService.get_route(db, current_user, route.id)

    @staticmethod
    def update_stop_status(
        db: Session,
        current_user: User,
        route_id: int,
        stop_id: int,
        req: RouteStopUpdateRequest,
    ) -> DeliveryRouteResponse:
        route = RouteService._get_route_scoped(db, current_user, route_id)
        if route.status not in (RouteStatus.DISPATCHED, RouteStatus.IN_PROGRESS):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stops can only be updated on DISPATCHED or IN_PROGRESS routes (current: '{route.status.value}')",
            )

        stop_obj = next((s for s in route.stops if s.id == stop_id), None)
        if not stop_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route stop not found")

        if stop_obj.status in TERMINAL_STOP_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stop #{stop_obj.sequence_order} is already finalized ('{stop_obj.status.value}')",
            )
        if req.status == RouteStopStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Cannot revert an active stop back to PENDING",
            )

        now = datetime.now(timezone.utc)
        if route.status == RouteStatus.DISPATCHED:
            route.status = RouteStatus.IN_PROGRESS
            route.started_at = route.started_at or now
            if route.vehicle and route.vehicle.status in (VehicleStatus.AVAILABLE, VehicleStatus.ASSIGNED):
                route.vehicle.status = VehicleStatus.IN_TRANSIT

        broadcasts: List[Dict[str, Any]] = []
        lat = req.latitude if req.latitude is not None else stop_obj.latitude
        lng = req.longitude if req.longitude is not None else stop_obj.longitude

        try:
            if req.status in (RouteStopStatus.EN_ROUTE, RouteStopStatus.ARRIVED):
                stop_obj.status = req.status
                if req.status == RouteStopStatus.ARRIVED and not stop_obj.arrived_at:
                    stop_obj.arrived_at = now
                if stop_obj.assignment and stop_obj.assignment.status == AssignmentStatus.ASSIGNED:
                    stop_obj.assignment.status = AssignmentStatus.IN_PROGRESS
                if req.notes:
                    stop_obj.notes = req.notes

            elif req.status == RouteStopStatus.COMPLETED:
                stop_obj.status = RouteStopStatus.COMPLETED
                stop_obj.arrived_at = stop_obj.arrived_at or now
                stop_obj.completed_at = now
                stop_obj.is_active = False
                if req.notes:
                    stop_obj.notes = req.notes

                parcel = stop_obj.parcel
                if parcel:
                    target_status = (
                        ParcelStatus.PICKED_UP
                        if stop_obj.stop_type == RouteStopType.PICKUP
                        else ParcelStatus.DELIVERED
                    )
                    if parcel.delivery_status != target_status:
                        remarks = f"Completed on route {route.route_code} stop #{stop_obj.sequence_order} at {stop_obj.location_name}"
                        ShipmentStateMachine.transition(
                            db=db,
                            current_user=current_user,
                            parcel=parcel,
                            to_status=target_status,
                            remarks=remarks,
                            location_name=stop_obj.location_name,
                            branch_id=route.branch_id,
                            latitude=lat,
                            longitude=lng,
                            source="ROUTE_STOP_COMPLETE",
                            commit=False,
                        )
                        broadcasts.append(
                            {
                                "tracking_number": parcel.tracking_number,
                                "to_status": target_status,
                                "location": stop_obj.location_name,
                                "latitude": lat,
                                "longitude": lng,
                                "remarks": remarks,
                                "timestamp": now,
                            }
                        )
                if stop_obj.assignment and stop_obj.assignment.status != AssignmentStatus.COMPLETED:
                    stop_obj.assignment.status = AssignmentStatus.COMPLETED
                    stop_obj.assignment.completed_at = now

            elif req.status == RouteStopStatus.FAILED:
                stop_obj.status = RouteStopStatus.FAILED
                stop_obj.completed_at = now
                stop_obj.is_active = False
                stop_obj.failure_reason = req.failure_reason
                if req.notes:
                    stop_obj.notes = req.notes

                parcel = stop_obj.parcel
                if parcel:
                    if stop_obj.stop_type == RouteStopType.DELIVERY and parcel.delivery_status == ParcelStatus.OUT_FOR_DELIVERY:
                        remarks = f"Delivery failed on route {route.route_code} stop #{stop_obj.sequence_order}: {req.failure_reason}"
                        ShipmentStateMachine.transition(
                            db=db,
                            current_user=current_user,
                            parcel=parcel,
                            to_status=ParcelStatus.DELIVERY_FAILED,
                            remarks=remarks,
                            location_name=stop_obj.location_name,
                            branch_id=route.branch_id,
                            latitude=lat,
                            longitude=lng,
                            source="ROUTE_STOP_FAILED",
                            commit=False,
                        )
                        broadcasts.append(
                            {
                                "tracking_number": parcel.tracking_number,
                                "to_status": ParcelStatus.DELIVERY_FAILED,
                                "location": stop_obj.location_name,
                                "latitude": lat,
                                "longitude": lng,
                                "remarks": remarks,
                                "timestamp": now,
                            }
                        )
                    elif (
                        stop_obj.stop_type == RouteStopType.PICKUP
                        and parcel.delivery_status == ParcelStatus.PICKUP_SCHEDULED
                        and current_user.role in (UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN)
                    ):
                        remarks = f"Pickup failed on route {route.route_code} stop #{stop_obj.sequence_order}: {req.failure_reason}"
                        ShipmentStateMachine.transition(
                            db=db,
                            current_user=current_user,
                            parcel=parcel,
                            to_status=ParcelStatus.BOOKED,
                            remarks=remarks,
                            location_name=stop_obj.location_name,
                            branch_id=route.branch_id,
                            latitude=lat,
                            longitude=lng,
                            source="ROUTE_STOP_FAILED",
                            commit=False,
                        )
                        broadcasts.append(
                            {
                                "tracking_number": parcel.tracking_number,
                                "to_status": ParcelStatus.BOOKED,
                                "location": stop_obj.location_name,
                                "latitude": lat,
                                "longitude": lng,
                                "remarks": remarks,
                                "timestamp": now,
                            }
                        )

                if stop_obj.assignment:
                    stop_obj.assignment.status = AssignmentStatus.FAILED
                    stop_obj.assignment.completed_at = now

            elif req.status == RouteStopStatus.SKIPPED:
                stop_obj.status = RouteStopStatus.SKIPPED
                stop_obj.completed_at = now
                stop_obj.is_active = False
                if req.notes:
                    stop_obj.notes = req.notes

                if stop_obj.assignment and stop_obj.assignment.status in (
                    AssignmentStatus.ASSIGNED,
                    AssignmentStatus.IN_PROGRESS,
                ):
                    stop_obj.assignment.status = AssignmentStatus.CANCELLED
                    stop_obj.assignment.completed_at = now

                parcel = stop_obj.parcel
                if parcel:
                    if stop_obj.stop_type == RouteStopType.DELIVERY and parcel.delivery_status == ParcelStatus.OUT_FOR_DELIVERY:
                        remarks = f"Stop #{stop_obj.sequence_order} skipped on route {route.route_code}; returned parcel to branch pool"
                        ShipmentStateMachine.transition(
                            db=db,
                            current_user=current_user,
                            parcel=parcel,
                            to_status=ParcelStatus.AT_DESTINATION_BRANCH,
                            remarks=remarks,
                            location_name=route.branch.branch_name if route.branch else "Branch Hub",
                            branch_id=route.branch_id,
                            source="ROUTE_STOP_SKIPPED",
                            commit=False,
                        )
                        broadcasts.append(
                            {
                                "tracking_number": parcel.tracking_number,
                                "to_status": ParcelStatus.AT_DESTINATION_BRANCH,
                                "location": route.branch.branch_name if route.branch else "Branch Hub",
                                "remarks": remarks,
                                "timestamp": now,
                            }
                        )
                    elif (
                        stop_obj.stop_type == RouteStopType.PICKUP
                        and parcel.delivery_status == ParcelStatus.PICKUP_SCHEDULED
                        and current_user.role in (UserRole.BRANCH_MANAGER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN)
                    ):
                        remarks = f"Pickup stop #{stop_obj.sequence_order} skipped on route {route.route_code}"
                        ShipmentStateMachine.transition(
                            db=db,
                            current_user=current_user,
                            parcel=parcel,
                            to_status=ParcelStatus.BOOKED,
                            remarks=remarks,
                            location_name=route.branch.branch_name if route.branch else "Branch Hub",
                            branch_id=route.branch_id,
                            source="ROUTE_STOP_SKIPPED",
                            commit=False,
                        )
                        broadcasts.append(
                            {
                                "tracking_number": parcel.tracking_number,
                                "to_status": ParcelStatus.BOOKED,
                                "location": route.branch.branch_name if route.branch else "Branch Hub",
                                "remarks": remarks,
                                "timestamp": now,
                            }
                        )

            db.flush()

            completed_count = sum(1 for s in route.stops if s.status == RouteStopStatus.COMPLETED)
            route.completed_stops = completed_count
            all_terminal = all(s.status in TERMINAL_STOP_STATUSES for s in route.stops)
            if all_terminal:
                route.status = RouteStatus.COMPLETED
                route.is_active_dispatch = False
                route.completed_at = now
                if route.vehicle and route.vehicle.status in (VehicleStatus.ASSIGNED, VehicleStatus.IN_TRANSIT):
                    route.vehicle.status = VehicleStatus.AVAILABLE
            else:
                # Guard against ShipmentStateMachine prematurely releasing a shared route vehicle mid-tour
                if route.vehicle and route.vehicle.status == VehicleStatus.AVAILABLE:
                    route.vehicle.status = VehicleStatus.IN_TRANSIT

            route.updated_at = now
            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except StaleDataError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Route was updated concurrently; please refresh and retry",
            )
        except Exception:
            db.rollback()
            raise

        for b in broadcasts:
            ShipmentStateMachine.broadcast_milestone(**b)

        return RouteService.get_route(db, current_user, route.id)

    @staticmethod
    def cancel_route(
        db: Session, current_user: User, route_id: int, req: RouteCancelRequest
    ) -> DeliveryRouteResponse:
        RouteService._ensure_manager(current_user)
        route = RouteService._get_route_scoped(db, current_user, route_id)
        if route.status in (RouteStatus.COMPLETED, RouteStatus.CANCELLED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot cancel route in '{route.status.value}' status",
            )

        now = datetime.now(timezone.utc)
        branch_name = route.branch.branch_name if route.branch else "Branch Hub"
        broadcasts: List[Dict[str, Any]] = []

        try:
            for stop_obj in sorted(route.stops, key=lambda s: s.sequence_order):
                if stop_obj.status not in TERMINAL_STOP_STATUSES:
                    stop_obj.status = RouteStopStatus.SKIPPED
                    stop_obj.is_active = False
                    stop_obj.completed_at = now

                    if stop_obj.assignment and stop_obj.assignment.status in (
                        AssignmentStatus.ASSIGNED,
                        AssignmentStatus.IN_PROGRESS,
                    ):
                        stop_obj.assignment.status = AssignmentStatus.CANCELLED
                        stop_obj.assignment.completed_at = now

                    parcel = stop_obj.parcel
                    if parcel:
                        if parcel.delivery_status == ParcelStatus.OUT_FOR_DELIVERY:
                            remarks = f"Route {route.route_code} cancelled ({req.cancellation_reason})"
                            ShipmentStateMachine.transition(
                                db=db,
                                current_user=current_user,
                                parcel=parcel,
                                to_status=ParcelStatus.AT_DESTINATION_BRANCH,
                                remarks=remarks,
                                location_name=branch_name,
                                branch_id=route.branch_id,
                                source="ROUTE_CANCEL",
                                commit=False,
                            )
                            broadcasts.append(
                                {
                                    "tracking_number": parcel.tracking_number,
                                    "to_status": ParcelStatus.AT_DESTINATION_BRANCH,
                                    "location": branch_name,
                                    "remarks": remarks,
                                    "timestamp": now,
                                }
                            )
                        elif parcel.delivery_status == ParcelStatus.PICKUP_SCHEDULED:
                            remarks = f"Pickup route {route.route_code} cancelled ({req.cancellation_reason})"
                            ShipmentStateMachine.transition(
                                db=db,
                                current_user=current_user,
                                parcel=parcel,
                                to_status=ParcelStatus.BOOKED,
                                remarks=remarks,
                                location_name=branch_name,
                                branch_id=route.branch_id,
                                source="ROUTE_CANCEL",
                                commit=False,
                            )
                            broadcasts.append(
                                {
                                    "tracking_number": parcel.tracking_number,
                                    "to_status": ParcelStatus.BOOKED,
                                    "location": branch_name,
                                    "remarks": remarks,
                                    "timestamp": now,
                                }
                            )
                else:
                    stop_obj.is_active = False

            was_active_dispatch = route.is_active_dispatch
            route.status = RouteStatus.CANCELLED
            route.is_active_dispatch = False
            route.cancelled_at = now
            route.updated_at = now
            route.notes = (
                f"{route.notes} | Cancelled: {req.cancellation_reason}"
                if route.notes
                else f"Cancelled: {req.cancellation_reason}"
            )

            if (
                was_active_dispatch
                and route.vehicle
                and route.vehicle.status in (VehicleStatus.ASSIGNED, VehicleStatus.IN_TRANSIT)
            ):
                route.vehicle.status = VehicleStatus.AVAILABLE

            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except StaleDataError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Route was modified concurrently during cancellation",
            )
        except Exception:
            db.rollback()
            raise

        for b in broadcasts:
            ShipmentStateMachine.broadcast_milestone(**b)

        return RouteService.get_route(db, current_user, route.id)
