"""3-Phase constraint validation pipeline for route planning, optimization, and dispatch."""
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
import logging
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from app.models.enums import RouteStopStatus, RouteStopType, ServiceType, VehicleType
from app.schemas.route_plan import RoutePlanResult

logger = logging.getLogger(__name__)


class ViolationSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass
class ConstraintViolation:
    """Structured machine-readable constraint rejection or warning."""

    code: str
    message: str
    severity: ViolationSeverity = ViolationSeverity.ERROR
    field: Optional[str] = None
    stop_index: Optional[int] = None
    parcel_id: Optional[int] = None


@dataclass
class OptimizationConstraints:
    """Configurable boundaries and operational rules passed into the routing engine."""

    max_vehicle_payload_kg: float = 500.0
    max_vehicle_volume_cbm: Optional[float] = None
    max_route_duration_minutes: float = 480.0  # 8 hour standard shift
    max_route_distance_km: float = 200.0
    stop_service_duration_min: float = 5.0
    require_return_to_hub: bool = True
    enforce_hard_time_windows: bool = False
    enforce_precedence: bool = True
    locked_stop_ids: Set[int] = field(default_factory=set)


class RouteConstraintValidator:
    """
    Validates logistics invariants before optimization (pre-validation)
    and asserts post-optimization candidate compliance (post-validation).
    """

    @staticmethod
    def validate_pre_optimization(
        total_cargo_weight_kg: float,
        total_cargo_volume_cbm: Optional[float],
        waypoints_meta: Sequence[Dict[str, Any]],
        constraints: OptimizationConstraints,
        has_depot_coords: bool,
    ) -> List[ConstraintViolation]:
        """
        Phase 1: Pre-validation prior to solver execution.
        Rejects obviously infeasible requests (e.g. payload exceeded, missing depot coords).
        """
        violations: List[ConstraintViolation] = []

        if not has_depot_coords:
            violations.append(
                ConstraintViolation(
                    code="MISSING_DEPOT_COORDINATES",
                    message="Branch hub depot is missing verified latitude/longitude coordinates",
                    severity=ViolationSeverity.ERROR,
                    field="branch_id",
                )
            )

        # 1. Payload Capacity Constraint
        if total_cargo_weight_kg > constraints.max_vehicle_payload_kg:
            violations.append(
                ConstraintViolation(
                    code="EXCEEDS_VEHICLE_PAYLOAD",
                    message=(
                        f"Total cargo weight ({total_cargo_weight_kg:.1f} kg) exceeds "
                        f"vehicle maximum payload capacity ({constraints.max_vehicle_payload_kg:.1f} kg)"
                    ),
                    severity=ViolationSeverity.ERROR,
                    field="vehicle_id",
                )
            )

        if (
            constraints.max_vehicle_volume_cbm is not None
            and total_cargo_volume_cbm is not None
            and total_cargo_volume_cbm > constraints.max_vehicle_volume_cbm
        ):
            violations.append(
                ConstraintViolation(
                    code="EXCEEDS_VEHICLE_VOLUME",
                    message=(
                        f"Total cargo volume ({total_cargo_volume_cbm:.2f} m3) exceeds "
                        f"vehicle maximum volumetric capacity ({constraints.max_vehicle_volume_cbm:.2f} m3)"
                    ),
                    severity=ViolationSeverity.ERROR,
                    field="vehicle_id",
                )
            )

        # 2. Precedence feasibility check
        # If a stop is a DELIVERY for a parcel that also has a PICKUP on this route,
        # both stops must be present.
        pickup_parcel_ids = {
            w["parcel_id"] for w in waypoints_meta if w.get("stop_type") in ("PICKUP", RouteStopType.PICKUP) and w.get("parcel_id")
        }
        delivery_parcel_ids = {
            w["parcel_id"] for w in waypoints_meta if w.get("stop_type") in ("DELIVERY", RouteStopType.DELIVERY) and w.get("parcel_id")
        }

        # Any parcel requiring pickup must have valid parcel coordinates
        for idx, w in enumerate(waypoints_meta):
            if w.get("latitude") is None or w.get("longitude") is None:
                violations.append(
                    ConstraintViolation(
                        code="UNRESOLVED_STOP_COORDINATES",
                        message=f"Stop #{idx} (Parcel ID: {w.get('parcel_id')}) lacks valid geographic coordinates",
                        severity=ViolationSeverity.ERROR,
                        stop_index=idx,
                        parcel_id=w.get("parcel_id"),
                    )
                )

        return violations

    @staticmethod
    def validate_post_optimization(
        route_plan: RoutePlanResult,
        waypoints_meta: Sequence[Dict[str, Any]],
        constraints: OptimizationConstraints,
    ) -> List[ConstraintViolation]:
        """
        Phase 3: Post-validation verifying the generated sequenced route
        complies with physical constraints, shift limits, and precedence.
        """
        violations: List[ConstraintViolation] = []

        # 1. Total Route Distance & Duration Constraints
        route_dist_km = route_plan.total_distance_m / 1000.0
        route_duration_min = route_plan.total_duration_s / 60.0

        if route_dist_km > constraints.max_route_distance_km:
            violations.append(
                ConstraintViolation(
                    code="MAX_ROUTE_DISTANCE_EXCEEDED",
                    message=(
                        f"Planned route distance ({route_dist_km:.1f} km) exceeds maximum "
                        f"allowed boundary ({constraints.max_route_distance_km:.1f} km)"
                    ),
                    severity=(
                        ViolationSeverity.ERROR
                        if constraints.max_route_distance_km > 0
                        else ViolationSeverity.WARNING
                    ),
                )
            )

        if route_duration_min > constraints.max_route_duration_minutes:
            violations.append(
                ConstraintViolation(
                    code="MAX_ROUTE_DURATION_EXCEEDED",
                    message=(
                        f"Planned route duration ({route_duration_min:.1f} min) exceeds maximum "
                        f"driver shift limit ({constraints.max_route_duration_minutes:.1f} min)"
                    ),
                    severity=ViolationSeverity.WARNING,
                )
            )

        # 2. Pickup-before-delivery Precedence Verification
        if constraints.enforce_precedence:
            seen_pickups: Set[int] = set()
            for stop_idx in route_plan.ordered_stops:
                if stop_idx >= len(waypoints_meta):
                    continue
                meta = waypoints_meta[stop_idx]
                pid = meta.get("parcel_id")
                stype = str(meta.get("stop_type", "")).upper()

                if "PICKUP" in stype and pid:
                    seen_pickups.add(pid)
                elif "DELIVERY" in stype and pid:
                    # Check if this parcel also had a pickup on this route
                    has_route_pickup = any(
                        w.get("parcel_id") == pid and "PICKUP" in str(w.get("stop_type", "")).upper()
                        for w in waypoints_meta
                    )
                    if has_route_pickup and pid not in seen_pickups:
                        violations.append(
                            ConstraintViolation(
                                code="PRECEDENCE_VIOLATION",
                                message=(
                                    f"Delivery for parcel #{pid} scheduled at sequence position before its pickup stop"
                                ),
                                severity=ViolationSeverity.ERROR,
                                stop_index=stop_idx,
                                parcel_id=pid,
                            )
                        )

        # 3. Time Windows Check
        for eta_entry in route_plan.per_stop_eta:
            idx = eta_entry.stop_index
            if idx >= len(waypoints_meta):
                continue
            meta = waypoints_meta[idx]
            win_end_min = meta.get("window_end_min")
            if win_end_min is not None and eta_entry.eta_minutes_from_start > win_end_min:
                severity = (
                    ViolationSeverity.ERROR
                    if constraints.enforce_hard_time_windows
                    else ViolationSeverity.WARNING
                )
                violations.append(
                    ConstraintViolation(
                        code="TIME_WINDOW_MISSED",
                        message=(
                            f"Stop #{idx} estimated arrival ({eta_entry.eta_minutes_from_start:.1f} min) "
                            f"exceeds delivery time window deadline ({win_end_min:.1f} min)"
                        ),
                        severity=severity,
                        stop_index=idx,
                        parcel_id=meta.get("parcel_id"),
                    )
                )

        return violations
