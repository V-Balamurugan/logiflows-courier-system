"""OSRM Trip and Route adapter with CircuitBreaker, road polyline geometry, and diagnostic checks."""
import logging
import time
from typing import Callable, List, Optional, Sequence, Tuple

import httpx

from app.core.config import settings
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
    STOP_SERVICE_MINUTES,
    BaseRoutingProvider,
    CircuitBreaker,
    Waypoint,
)
from app.services.routing.local import LocalHaversineOptimizer
from app.services.routing.ors import _request_with_retry

logger = logging.getLogger(__name__)


class OSRMAdapter(BaseRoutingProvider):
    """
    OSRM Trip / Route adapter using OpenStreetMap road topology.

    Limitations:
    - Standard public OSRM demo server (router.project-osrm.org) is strictly for development/demonstration.
    - Commercial vehicle restrictions (axle load, height, hazardous cargo) are NOT enforced by standard car profile.
    - Endpoints must be configured to self-hosted OSRM instances for production deployments.
    """

    name = "osrm"
    provider_name = "osrm"

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        transport: Optional[httpx.BaseTransport] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.base_url = (base_url or settings.OSRM_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.ROUTING_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.ROUTING_MAX_RETRIES
        self.transport = transport
        self.sleep_fn = sleep_fn
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            name="osrm",
            failure_threshold=3,
            recovery_timeout_seconds=30.0,
        )

    def check_health(self) -> bool:
        """Check availability of configured OSRM server."""
        try:
            with httpx.Client(timeout=2.0, transport=self.transport) as client:
                resp = client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False

    def compute_route(
        self,
        start: Tuple[float, float],
        waypoints: Sequence[Waypoint],
        vehicle_type: VehicleType = VehicleType.VAN,
        objective: str = "FASTEST",
        return_to_hub: bool = True,
    ) -> RoutePlanResult:
        if not self.circuit_breaker.can_execute():
            raise RuntimeError(
                f"Circuit breaker for {self.name} is OPEN (failure threshold exceeded). Rejecting call."
            )

        baseline_plan = LocalHaversineOptimizer.compute_route(
            start=start,
            waypoints=waypoints,
            vehicle_type=vehicle_type,
            objective="MANUAL",
            return_to_hub=return_to_hub,
        )
        if not waypoints:
            return baseline_plan

        coords = [f"{start[1]},{start[0]}"] + [f"{wp.longitude},{wp.latitude}" for wp in waypoints]
        normalized_obj = (objective or "FASTEST").strip().upper()

        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                if normalized_obj == "MANUAL":
                    if return_to_hub:
                        coords.append(f"{start[1]},{start[0]}")
                    coord_str = ";".join(coords)
                    url = f"{self.base_url}/route/v1/driving/{coord_str}"
                    params = {"overview": "full", "geometries": "geojson"}
                    resp = _request_with_retry(
                        client,
                        "GET",
                        url,
                        max_retries=self.max_retries,
                        sleep_fn=self.sleep_fn,
                        params=params,
                    )
                    data = resp.json()
                    routes = data.get("routes") or []
                    if not routes:
                        raise ValueError("OSRM route returned empty routes")
                    route_obj = routes[0]
                    ordered_indices = list(range(len(waypoints)))
                else:
                    coord_str = ";".join(coords)
                    url = f"{self.base_url}/trip/v1/driving/{coord_str}"
                    params = {
                        "source": "first",
                        "roundtrip": "true" if return_to_hub else "false",
                        "overview": "full",
                        "geometries": "geojson",
                    }
                    if not return_to_hub:
                        params["destination"] = "any"
                    resp = _request_with_retry(
                        client,
                        "GET",
                        url,
                        max_retries=self.max_retries,
                        sleep_fn=self.sleep_fn,
                        params=params,
                    )
                    data = resp.json()
                    trips = data.get("trips") or []
                    osrm_waypoints = data.get("waypoints") or []
                    if not trips or len(osrm_waypoints) != len(waypoints) + 1:
                        raise ValueError("OSRM trip response missing trips or waypoints")
                    route_obj = trips[0]
                    # Map OSRM waypoint_index back to input stop indices
                    indexed_order = [
                        (int(osrm_waypoints[i + 1]["waypoint_index"]), i) for i in range(len(waypoints))
                    ]
                    indexed_order.sort(key=lambda pair: pair[0])
                    ordered_indices = [pair[1] for pair in indexed_order]

            self.circuit_breaker.record_success()
        except Exception as exc:
            self.circuit_breaker.record_failure(exc)
            raise

        raw_geom = route_obj.get("geometry", {}).get("coordinates") or []
        road_geometry: List[List[float]] = [
            [round(float(pt[1]), 6), round(float(pt[0]), 6)] for pt in raw_geom if len(pt) >= 2
        ]
        legs_data = route_obj.get("legs") or []
        expected_legs = len(ordered_indices) + (1 if return_to_hub else 0)
        if len(legs_data) != expected_legs:
            raise ValueError(f"OSRM returned {len(legs_data)} legs, expected {expected_legs}")

        legs: List[RouteLegResult] = []
        per_stop_eta: List[PerStopETAResult] = []
        cum_duration_s = 0.0

        prev_idx = -1
        for i, leg in enumerate(legs_data):
            dist_m = float(leg.get("distance", 0.0))
            drive_s = float(leg.get("duration", 0.0))
            service_s = STOP_SERVICE_MINUTES * 60.0 if i < len(ordered_indices) else 0.0
            leg_duration_s = round(drive_s + service_s, 1)

            target_idx = ordered_indices[i] if i < len(ordered_indices) else -1
            legs.append(
                RouteLegResult(
                    from_index=prev_idx,
                    to_index=target_idx,
                    distance_m=dist_m,
                    duration_s=leg_duration_s,
                    distance_basis=DistanceBasis.PROVIDER_ROAD,
                )
            )

            cum_duration_s += leg_duration_s
            if i < len(ordered_indices):
                per_stop_eta.append(
                    PerStopETAResult(
                        stop_index=target_idx,
                        eta_minutes_from_start=round(cum_duration_s / 60.0, 1),
                        distance_from_prev_m=dist_m,
                        duration_from_prev_s=leg_duration_s,
                        service_time_s=service_s,
                    )
                )
            prev_idx = target_idx

        total_distance_m = sum(leg.distance_m for leg in legs)
        total_duration_s = cum_duration_s

        warnings: List[str] = [
            "OSRM routing utilized; commercial HGV restrictions not actively enforced on standard profiles."
        ]

        return RoutePlanResult(
            provider_used=self.name,
            fallback_used=False,
            fallback_reason=None,
            ordered_stops=ordered_indices,
            legs=legs,
            total_distance_m=total_distance_m,
            total_duration_s=total_duration_s,
            geometry=road_geometry,
            per_stop_eta=per_stop_eta,
            objective=objective,
            optimization_status=OptimizationStatus.FEASIBLE,
            warnings=warnings,
            provenance=RouteProvenance(
                data_source="OSRM_TRIP_ROUTE",
                algorithm="OSRM-v5",
                version="v5",
            ),
            baseline_distance_m=baseline_plan.baseline_distance_m,
        )
