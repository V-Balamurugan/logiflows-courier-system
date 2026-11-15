"""Local deterministic TSP solver using Haversine distance, road tortuosity, and bounded 2-opt."""
from datetime import datetime, timezone
import hashlib
import logging
import math
from typing import List, Optional, Sequence, Set, Tuple

from app.models.enums import VehicleType
from app.schemas.route_plan import (
    DistanceBasis,
    OptimizationStatus,
    PerStopETAResult,
    RouteLegResult,
    RoutePlanResult,
    RouteProvenance,
)
from app.services.routing.base import (
    BaseRoutingProvider,
    DEFAULT_ROAD_TORTUOSITY,
    EARTH_RADIUS_KM,
    MAX_TWO_OPT_ITERATIONS,
    STOP_SERVICE_MINUTES,
    VEHICLE_SPEED_KMH,
    Waypoint,
    validate_lat_lng,
)

logger = logging.getLogger(__name__)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate great-circle distance in kilometers between two WGS84 coordinates."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(d_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return EARTH_RADIUS_KM * c


def estimate_road_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Convert straight-line geodesic distance into calibrated road-adjusted km estimate."""
    return haversine_km(lat1, lng1, lat2, lng2) * DEFAULT_ROAD_TORTUOSITY


def derive_branch_vicinity_coords(
    branch_lat: float, branch_lng: float, pincode: str, seed_key: str
) -> Tuple[float, float]:
    """Deterministically generate a bounded ~1.5-6.5 km vicinity coordinate near a branch hub."""
    validate_lat_lng(branch_lat, branch_lng, "Branch hub coordinate")
    digest = hashlib.sha256(f"{pincode}:{seed_key}".encode("utf-8")).digest()
    angle = (int.from_bytes(digest[:2], "big") / 65535.0) * 2.0 * math.pi
    radius_km = 1.5 + (int.from_bytes(digest[2:4], "big") / 65535.0) * 5.0
    d_lat = (radius_km * math.cos(angle)) / 111.0
    cos_lat = max(0.2, math.cos(math.radians(branch_lat)))
    d_lng = (radius_km * math.sin(angle)) / (111.0 * cos_lat)
    lat = max(-89.9, min(89.9, branch_lat + d_lat))
    lng = max(-179.9, min(179.9, branch_lng + d_lng))
    return (round(lat, 6), round(lng, 6))


def _route_sequence_distance(
    start: Tuple[float, float],
    waypoints: Sequence[Waypoint],
    order: Sequence[int],
    return_to_hub: bool,
) -> float:
    """Compute total road-estimated distance in km for an ordered index permutation."""
    if not order:
        return 0.0
    total = 0.0
    prev_lat, prev_lng = start
    for idx in order:
        wp = waypoints[idx]
        total += estimate_road_distance_km(prev_lat, prev_lng, wp.latitude, wp.longitude)
        prev_lat, prev_lng = wp.latitude, wp.longitude
    if return_to_hub:
        total += estimate_road_distance_km(prev_lat, prev_lng, start[0], start[1])
    return total


def _check_precedence(order: Sequence[int], waypoints: Sequence[Waypoint]) -> bool:
    """
    Verify pickup-before-delivery precedence invariants.
    If a parcel has both pickup and delivery waypoints, pickup must precede delivery.
    """
    seen_pickups: Set[int] = set()
    for idx in order:
        wp = waypoints[idx]
        if wp.pickup_parcel_id is not None:
            seen_pickups.add(wp.pickup_parcel_id)
        if wp.delivery_parcel_id is not None:
            # Check if there was a pickup waypoint for the same parcel on this route
            # If so, it must have been seen already
            has_matching_pickup = any(w.pickup_parcel_id == wp.delivery_parcel_id for w in waypoints)
            if has_matching_pickup and wp.delivery_parcel_id not in seen_pickups:
                return False
    return True


def _score_objective(
    start: Tuple[float, float],
    waypoints: Sequence[Waypoint],
    order: Sequence[int],
    return_to_hub: bool,
    speed_kmh: float,
    objective: str,
) -> float:
    """
    Compute scalar penalty score for candidate sequence based on objective formula.
    - FASTEST: Total travel time + service time + waiting time penalty.
    - SHORTEST_DISTANCE: Total road distance in km.
    - BALANCED: 0.5 * time + 0.3 * distance + 0.2 * priority_delay.
    - PRIORITY_FIRST: Lexicographic penalty on priority sequence inversion + distance.
    """
    dist_km = _route_sequence_distance(start, waypoints, order, return_to_hub)
    travel_time_min = (dist_km / speed_kmh) * 60.0
    total_service_min = sum(waypoints[idx].service_duration_min for idx in order)

    # Hard precedence check: heavily penalize candidate violating pickup-before-delivery
    if not _check_precedence(order, waypoints):
        return 1e9

    norm_obj = objective.strip().upper()
    if norm_obj in {"SHORTEST", "SHORTEST_DISTANCE"}:
        return dist_km

    if norm_obj == "FASTEST":
        return travel_time_min + total_service_min

    if norm_obj == "BALANCED":
        # Weighting: time (w_t=0.50), distance (w_d=0.30), priority penalty (w_p=0.20)
        # Priority penalty: earlier service of high-priority stops reduces penalty
        priority_penalty = 0.0
        for pos, idx in enumerate(order):
            wp = waypoints[idx]
            if wp.priority > 0:
                priority_penalty += (pos + 1) * 10.0 * float(wp.priority)
        return (0.50 * travel_time_min) + (0.30 * dist_km) + (0.20 * priority_penalty)

    if norm_obj == "PRIORITY_FIRST":
        # Heavily penalize any higher-priority stop served after a lower-priority stop
        inversion_penalty = 0.0
        for pos, idx in enumerate(order):
            wp = waypoints[idx]
            # Higher priority served later in the sequence accrues severe quadratic penalty
            inversion_penalty += (pos ** 2) * (100.0 * max(0, wp.priority))
        return inversion_penalty + (0.01 * dist_km)

    return dist_km


def _apply_two_opt(
    start: Tuple[float, float],
    waypoints: Sequence[Waypoint],
    initial_order: List[int],
    return_to_hub: bool,
    speed_kmh: float = 38.0,
    objective: str = "FASTEST",
) -> List[int]:
    """Refine a TSP stop sequence using bounded 2-opt edge-swap improvement."""
    n = len(initial_order)
    if n < 3:
        return list(initial_order)

    best = list(initial_order)
    best_score = _score_objective(start, waypoints, best, return_to_hub, speed_kmh, objective)

    improved = True
    iterations = 0
    while improved and iterations < MAX_TWO_OPT_ITERATIONS:
        improved = False
        iterations += 1
        for i in range(0, n - 1):
            for j in range(i + 1, n):
                candidate = best[:i] + list(reversed(best[i : j + 1])) + best[j + 1 :]
                cand_score = _score_objective(start, waypoints, candidate, return_to_hub, speed_kmh, objective)
                if cand_score + 1e-6 < best_score:
                    best = candidate
                    best_score = cand_score
                    improved = True
                    break
            if improved:
                break
    return best


class LocalHaversineOptimizer(BaseRoutingProvider):
    """Deterministic offline TSP route optimizer using Haversine + 2-opt refinement."""

    name = "local_fallback"
    provider_name = "local_fallback"

    @classmethod
    def compute_route(
        cls,
        start: Tuple[float, float],
        waypoints: Sequence[Waypoint],
        vehicle_type: VehicleType = VehicleType.VAN,
        objective: str = "FASTEST",
        return_to_hub: bool = True,
        is_fallback: bool = False,
        fallback_reason: Optional[str] = None,
    ) -> RoutePlanResult:
        validate_lat_lng(start[0], start[1], "Start depot")
        for wp in waypoints:
            validate_lat_lng(wp.latitude, wp.longitude, f"Stop #{wp.index}")

        n = len(waypoints)
        if n == 0:
            return RoutePlanResult(
                provider_used=cls.name,
                fallback_used=is_fallback,
                fallback_reason=fallback_reason,
                ordered_stops=[],
                legs=[],
                total_distance_m=0.0,
                total_duration_s=0.0,
                geometry=None,  # Strictly None for local fallback
                per_stop_eta=[],
                objective=objective,
                optimization_status=OptimizationStatus.OPTIMAL,
                warnings=["Empty waypoint set provided; zero-distance route created."],
                provenance=RouteProvenance(
                    data_source="LOCAL_CALIBRATED_HAVERSINE",
                    algorithm="NearestNeighbor+2-Opt",
                    version="2.0.0",
                ),
                baseline_distance_m=0.0,
            )

        speed_kmh = VEHICLE_SPEED_KMH.get(vehicle_type, 38.0)
        input_order = list(range(n))
        baseline_distance_km = _route_sequence_distance(start, waypoints, input_order, return_to_hub)
        normalized_obj = (objective or "FASTEST").strip().upper()

        if normalized_obj == "MANUAL":
            order = input_order
        elif normalized_obj == "PRIORITY_FIRST":
            # Sort waypoints by priority descending, then nearest neighbor within tier
            priority_groups: dict[int, list[int]] = {}
            for idx in input_order:
                pri = waypoints[idx].priority
                priority_groups.setdefault(pri, []).append(idx)
            sorted_priorities = sorted(priority_groups.keys(), reverse=True)

            order = []
            cur_lat, cur_lng = start
            for pri in sorted_priorities:
                group = set(priority_groups[pri])
                while group:
                    best_idx = min(
                        group,
                        key=lambda idx: (
                            estimate_road_distance_km(
                                cur_lat, cur_lng, waypoints[idx].latitude, waypoints[idx].longitude
                            ),
                            idx,
                        ),
                    )
                    order.append(best_idx)
                    group.remove(best_idx)
                    cur_lat, cur_lng = waypoints[best_idx].latitude, waypoints[best_idx].longitude
            # Refine preserving priority order
            order = _apply_two_opt(start, waypoints, order, return_to_hub, speed_kmh, "PRIORITY_FIRST")
        else:
            # Nearest-neighbor construction with objective-aware tie breaking
            remaining = set(input_order)
            order = []
            cur_lat, cur_lng = start
            while remaining:
                if normalized_obj == "BALANCED":
                    # Priority bias discount on candidate distance
                    best_idx = min(
                        remaining,
                        key=lambda idx: (
                            estimate_road_distance_km(
                                cur_lat, cur_lng, waypoints[idx].latitude, waypoints[idx].longitude
                            )
                            * (0.80 if waypoints[idx].priority > 0 else 1.0),
                            idx,
                        ),
                    )
                else:
                    best_idx = min(
                        remaining,
                        key=lambda idx: (
                            estimate_road_distance_km(
                                cur_lat, cur_lng, waypoints[idx].latitude, waypoints[idx].longitude
                            ),
                            idx,
                        ),
                    )
                order.append(best_idx)
                remaining.remove(best_idx)
                cur_lat, cur_lng = waypoints[best_idx].latitude, waypoints[best_idx].longitude

            order = _apply_two_opt(start, waypoints, order, return_to_hub, speed_kmh, normalized_obj)

        # Enforce pickup-before-delivery precedence if violated
        if not _check_precedence(order, waypoints):
            # Repair sequence by moving delivery stops after corresponding pickup stops
            repaired: List[int] = []
            seen_pickups: Set[int] = set()
            deferred_deliveries: List[int] = []
            for idx in order:
                wp = waypoints[idx]
                if wp.pickup_parcel_id is not None:
                    seen_pickups.add(wp.pickup_parcel_id)
                    repaired.append(idx)
                    # Process any deliveries that were waiting for this pickup
                    to_remove = []
                    for d_idx in deferred_deliveries:
                        if waypoints[d_idx].delivery_parcel_id in seen_pickups:
                            repaired.append(d_idx)
                            to_remove.append(d_idx)
                    for d_idx in to_remove:
                        deferred_deliveries.remove(d_idx)
                elif wp.delivery_parcel_id is not None:
                    has_pickup = any(w.pickup_parcel_id == wp.delivery_parcel_id for w in waypoints)
                    if has_pickup and wp.delivery_parcel_id not in seen_pickups:
                        deferred_deliveries.append(idx)
                    else:
                        repaired.append(idx)
                else:
                    repaired.append(idx)
            repaired.extend(deferred_deliveries)
            order = repaired

        legs: List[RouteLegResult] = []
        per_stop_eta: List[PerStopETAResult] = []
        cum_duration_s = 0.0

        prev_lat, prev_lng = start
        prev_idx = -1  # hub representation

        for pos, idx in enumerate(order):
            wp = waypoints[idx]
            dist_km = round(estimate_road_distance_km(prev_lat, prev_lng, wp.latitude, wp.longitude), 3)
            dist_m = dist_km * 1000.0
            drive_s = (dist_km / speed_kmh) * 3600.0
            service_s = wp.service_duration_min * 60.0
            leg_duration_s = round(drive_s + service_s, 1)

            legs.append(
                RouteLegResult(
                    from_index=prev_idx,
                    to_index=idx,
                    distance_m=dist_m,
                    duration_s=leg_duration_s,
                    distance_basis=DistanceBasis.ROAD_ESTIMATE,
                )
            )

            cum_duration_s += leg_duration_s
            per_stop_eta.append(
                PerStopETAResult(
                    stop_index=idx,
                    eta_minutes_from_start=round(cum_duration_s / 60.0, 1),
                    distance_from_prev_m=dist_m,
                    duration_from_prev_s=leg_duration_s,
                    service_time_s=service_s,
                )
            )

            prev_lat, prev_lng = wp.latitude, wp.longitude
            prev_idx = idx

        if return_to_hub:
            back_km = round(estimate_road_distance_km(prev_lat, prev_lng, start[0], start[1]), 3)
            back_m = back_km * 1000.0
            back_s = round((back_km / speed_kmh) * 3600.0, 1)
            legs.append(
                RouteLegResult(
                    from_index=prev_idx,
                    to_index=-1,
                    distance_m=back_m,
                    duration_s=back_s,
                    distance_basis=DistanceBasis.ROAD_ESTIMATE,
                )
            )
            cum_duration_s += back_s

        total_distance_m = sum(leg.distance_m for leg in legs)
        total_duration_s = cum_duration_s
        baseline_distance_m = baseline_distance_km * 1000.0

        warnings = [
            "Local heuristic fallback used; geometry is null (no road-network polyline synthesized).",
            "Distances and durations are calibrated road-tortuosity estimates.",
        ]
        if fallback_reason:
            warnings.insert(0, f"Fallback trigger: {fallback_reason}")

        status = OptimizationStatus.OPTIMAL if n <= 3 else OptimizationStatus.HEURISTIC

        return RoutePlanResult(
            provider_used=cls.name,
            fallback_used=is_fallback,
            fallback_reason=fallback_reason,
            ordered_stops=order,
            legs=legs,
            total_distance_m=total_distance_m,
            total_duration_s=total_duration_s,
            geometry=None,  # Strictly None for local fallback per Subphase 15.7
            per_stop_eta=per_stop_eta,
            objective=objective,
            optimization_status=status,
            warnings=warnings,
            provenance=RouteProvenance(
                data_source="LOCAL_CALIBRATED_HAVERSINE",
                algorithm="NearestNeighbor+2-Opt",
                version="2.0.0",
            ),
            baseline_distance_m=baseline_distance_m,
        )
