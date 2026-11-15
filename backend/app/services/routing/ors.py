"""OpenRouteService adapter with CircuitBreaker, rate-limit header parsing, and road geometry."""
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
    CLIENT_ERROR_STATUS_CODES,
    ORS_PROFILES,
    RETRYABLE_STATUS_CODES,
    STOP_SERVICE_MINUTES,
    BaseRoutingProvider,
    CircuitBreaker,
    Waypoint,
)
from app.services.routing.local import LocalHaversineOptimizer

logger = logging.getLogger(__name__)


def _request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    max_retries: int,
    sleep_fn: Callable[[float], None] = time.sleep,
    **kwargs,
) -> httpx.Response:
    """Execute HTTP call with exponential backoff across transient timeouts and 429/5xx codes."""
    last_exc: Optional[Exception] = None
    attempts = max(1, max_retries + 1)
    for attempt in range(attempts):
        try:
            response = client.request(method, url, **kwargs)
            if response.status_code in CLIENT_ERROR_STATUS_CODES:
                # Do not retry 400, 401, 403, 404, 422 - fail fast
                if response.status_code != 429:
                    response.raise_for_status()

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < attempts - 1:
                # Check for Retry-After header
                retry_after_str = response.headers.get("Retry-After")
                delay = 0.1 * (2**attempt)
                if retry_after_str:
                    try:
                        delay = max(delay, float(retry_after_str))
                    except ValueError:
                        pass
                logger.info("Retrying ORS request in %.2fs (attempt %d/%d)", delay, attempt + 1, attempts)
                sleep_fn(delay)
                continue

            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            is_retryable_status = (
                isinstance(exc, httpx.HTTPStatusError)
                and exc.response is not None
                and exc.response.status_code in RETRYABLE_STATUS_CODES
            )
            if (isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)) or is_retryable_status) and attempt < attempts - 1:
                sleep_fn(0.1 * (2**attempt))
                continue
            raise

    if last_exc:
        raise last_exc
    raise RuntimeError("HTTP request retry exhausted unexpectedly")


class OpenRouteServiceAdapter(BaseRoutingProvider):
    """OpenRouteService directions adapter computing sequenced road polyline and ETAs."""

    name = "openrouteservice"
    provider_name = "openrouteservice"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        transport: Optional[httpx.BaseTransport] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.api_key = (api_key if api_key is not None else settings.ORS_API_KEY).strip()
        self.base_url = (base_url or settings.ORS_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.ROUTING_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.ROUTING_MAX_RETRIES
        self.transport = transport
        self.sleep_fn = sleep_fn
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            name="openrouteservice",
            failure_threshold=3,
            recovery_timeout_seconds=30.0,
        )
        self.rate_limit_remaining: Optional[int] = None

    def compute_route(
        self,
        start: Tuple[float, float],
        waypoints: Sequence[Waypoint],
        vehicle_type: VehicleType = VehicleType.VAN,
        objective: str = "FASTEST",
        return_to_hub: bool = True,
    ) -> RoutePlanResult:
        if not self.api_key or self.api_key == "<SET_ME>":
            raise ValueError("ORS_API_KEY is not configured")

        if not self.circuit_breaker.can_execute():
            raise RuntimeError(
                f"Circuit breaker for {self.name} is OPEN (failure threshold exceeded). Rejecting call."
            )

        # Baseline plan via local optimizer to get order and baseline distance
        local_plan = LocalHaversineOptimizer.compute_route(
            start=start,
            waypoints=waypoints,
            vehicle_type=vehicle_type,
            objective=objective,
            return_to_hub=return_to_hub,
        )
        if not waypoints:
            return local_plan

        coords: List[List[float]] = [[start[1], start[0]]]
        for idx in local_plan.ordered_stops:
            wp = waypoints[idx]
            coords.append([wp.longitude, wp.latitude])
        if return_to_hub:
            coords.append([start[1], start[0]])

        profile = ORS_PROFILES.get(vehicle_type, "driving-car")
        preference = "shortest" if (objective or "").upper() in {"SHORTEST", "SHORTEST_DISTANCE"} else "fastest"
        url = f"{self.base_url}/v2/directions/{profile}/geojson"

        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                resp = _request_with_retry(
                    client,
                    "POST",
                    url,
                    max_retries=self.max_retries,
                    sleep_fn=self.sleep_fn,
                    headers={"Authorization": self.api_key, "Content-Type": "application/json"},
                    json={"coordinates": coords, "preference": preference},
                )
            self.circuit_breaker.record_success()
        except Exception as exc:
            self.circuit_breaker.record_failure(exc)
            raise

        # Track quota headers if returned
        rate_rem = resp.headers.get("x-ratelimit-remaining")
        if rate_rem is not None:
            try:
                self.rate_limit_remaining = int(rate_rem)
            except ValueError:
                pass

        payload = resp.json()
        features = payload.get("features") or []
        if not features:
            raise ValueError("OpenRouteService returned empty GeoJSON features")

        feat = features[0]
        raw_geom = feat.get("geometry", {}).get("coordinates") or []
        # WGS84 lat, lng points
        road_geometry: List[List[float]] = [
            [round(float(pt[1]), 6), round(float(pt[0]), 6)] for pt in raw_geom if len(pt) >= 2
        ]
        segments = feat.get("properties", {}).get("segments") or []

        expected_legs = len(local_plan.ordered_stops) + (1 if return_to_hub else 0)
        if len(segments) != expected_legs:
            raise ValueError(f"OpenRouteService returned {len(segments)} segments, expected {expected_legs}")

        legs: List[RouteLegResult] = []
        per_stop_eta: List[PerStopETAResult] = []
        cum_duration_s = 0.0

        prev_idx = -1
        for i, seg in enumerate(segments):
            dist_m = float(seg.get("distance", 0.0))
            drive_s = float(seg.get("duration", 0.0))
            service_s = STOP_SERVICE_MINUTES * 60.0 if i < len(local_plan.ordered_stops) else 0.0
            leg_duration_s = round(drive_s + service_s, 1)

            target_idx = local_plan.ordered_stops[i] if i < len(local_plan.ordered_stops) else -1
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
            if i < len(local_plan.ordered_stops):
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

        warnings: List[str] = []
        if self.rate_limit_remaining is not None and self.rate_limit_remaining < 50:
            warnings.append(f"ORS rate limit remaining low: {self.rate_limit_remaining}")

        return RoutePlanResult(
            provider_used=self.name,
            fallback_used=False,
            fallback_reason=None,
            ordered_stops=local_plan.ordered_stops,
            legs=legs,
            total_distance_m=total_distance_m,
            total_duration_s=total_duration_s,
            geometry=road_geometry,  # Real road geometry from provider
            per_stop_eta=per_stop_eta,
            objective=objective,
            optimization_status=OptimizationStatus.FEASIBLE,
            warnings=warnings,
            provenance=RouteProvenance(
                data_source="OPENROUTESERVICE_V2_DIRECTIONS",
                algorithm=preference,
                version="v2",
            ),
            baseline_distance_m=local_plan.baseline_distance_m,
        )
