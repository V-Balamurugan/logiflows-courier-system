"""Pluggable routing optimization providers with deterministic 2-opt TSP fallback."""
from dataclasses import dataclass
import hashlib
import logging
import math
import time
from typing import Callable, List, Optional, Sequence, Tuple

import httpx

from app.core.config import settings
from app.models.enums import VehicleType

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0
DEFAULT_ROAD_TORTUOSITY = 1.30
STOP_SERVICE_MINUTES = 5.0
MAX_TWO_OPT_ITERATIONS = 200

VEHICLE_SPEED_KMH = {
    VehicleType.BIKE: 28.0,
    VehicleType.VAN: 38.0,
    VehicleType.TRUCK: 48.0,
}

ORS_PROFILES = {
    VehicleType.BIKE: "cycling-regular",
    VehicleType.VAN: "driving-car",
    VehicleType.TRUCK: "driving-hgv",
}

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class Waypoint:
    """Normalized geographic stop input passed into routing providers."""

    index: int
    latitude: float
    longitude: float
    label: str = ""
    priority: int = 0  # higher priority favors earlier service under BALANCED objective


@dataclass
class RouteComputationResult:
    """Standardized output across local and external routing provider adapters."""

    provider_used: str
    is_fallback: bool
    fallback_reason: Optional[str]
    ordered_indices: List[int]
    leg_distances_km: List[float]
    leg_durations_min: List[float]
    total_distance_km: float
    total_duration_min: float
    baseline_distance_km: float
    distance_saved_km: float
    distance_saved_pct: float
    geometry_points: List[Tuple[float, float]]


def validate_lat_lng(lat: Optional[float], lng: Optional[float], label: str = "Coordinate") -> Tuple[float, float]:
    """Validate WGS84 latitude/longitude bounds and reject NaN/Inf values."""
    if lat is None or lng is None:
        raise ValueError(f"{label} requires both latitude and longitude.")
    if not (math.isfinite(lat) and math.isfinite(lng)):
        raise ValueError(f"{label} latitude and longitude must be finite numbers.")
    if lat < -90.0 or lat > 90.0:
        raise ValueError(f"{label} latitude {lat} is out of bounds [-90, 90].")
    if lng < -180.0 or lng > 180.0:
        raise ValueError(f"{label} longitude {lng} is out of bounds [-180, 180].")
    return (float(lat), float(lng))


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
    """Convert straight-line geodesic distance into road-adjusted km estimate."""
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


def _apply_two_opt(
    start: Tuple[float, float],
    waypoints: Sequence[Waypoint],
    initial_order: List[int],
    return_to_hub: bool,
) -> List[int]:
    """Refine a TSP stop sequence using bounded 2-opt edge-swap improvement."""
    n = len(initial_order)
    if n < 3:
        return list(initial_order)

    best = list(initial_order)
    best_dist = _route_sequence_distance(start, waypoints, best, return_to_hub)

    improved = True
    iterations = 0
    while improved and iterations < MAX_TWO_OPT_ITERATIONS:
        improved = False
        iterations += 1
        for i in range(0, n - 1):
            for j in range(i + 1, n):
                candidate = best[:i] + list(reversed(best[i : j + 1])) + best[j + 1 :]
                cand_dist = _route_sequence_distance(start, waypoints, candidate, return_to_hub)
                if cand_dist + 1e-6 < best_dist:
                    best = candidate
                    best_dist = cand_dist
                    improved = True
                    break
            if improved:
                break
    return best


class LocalHaversineOptimizer:
    """Deterministic offline TSP route optimizer using Haversine + 2-opt refinement."""

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
    ) -> RouteComputationResult:
        validate_lat_lng(start[0], start[1], "Start depot")
        for wp in waypoints:
            validate_lat_lng(wp.latitude, wp.longitude, f"Stop #{wp.index}")

        n = len(waypoints)
        if n == 0:
            return RouteComputationResult(
                provider_used=cls.provider_name,
                is_fallback=is_fallback,
                fallback_reason=fallback_reason,
                ordered_indices=[],
                leg_distances_km=[],
                leg_durations_min=[],
                total_distance_km=0.0,
                total_duration_min=0.0,
                baseline_distance_km=0.0,
                distance_saved_km=0.0,
                distance_saved_pct=0.0,
                geometry_points=[start],
            )

        input_order = list(range(n))
        baseline_distance = _route_sequence_distance(start, waypoints, input_order, return_to_hub)
        normalized_obj = (objective or "FASTEST").strip().upper()

        if normalized_obj == "MANUAL":
            order = input_order
        else:
            # Nearest-neighbor construction weighted lightly for urgent express parcels when BALANCED
            remaining = set(input_order)
            order = []
            cur_lat, cur_lng = start
            while remaining:
                best_idx = min(
                    remaining,
                    key=lambda idx: (
                        estimate_road_distance_km(
                            cur_lat, cur_lng, waypoints[idx].latitude, waypoints[idx].longitude
                        )
                        * (0.85 if normalized_obj == "BALANCED" and waypoints[idx].priority > 0 else 1.0),
                        idx,
                    ),
                )
                order.append(best_idx)
                remaining.remove(best_idx)
                cur_lat, cur_lng = waypoints[best_idx].latitude, waypoints[best_idx].longitude

            if normalized_obj in {"FASTEST", "SHORTEST"}:
                order = _apply_two_opt(start, waypoints, order, return_to_hub)
            elif normalized_obj == "BALANCED":
                # Keep priority bias intact unless candidate order yields strict distance savings without moving express stops later
                two_opt = _apply_two_opt(start, waypoints, order, return_to_hub)
                if _route_sequence_distance(start, waypoints, two_opt, return_to_hub) <= baseline_distance:
                    order = two_opt

        speed_kmh = VEHICLE_SPEED_KMH.get(vehicle_type, 35.0)
        leg_distances_km: List[float] = []
        leg_durations_min: List[float] = []
        geometry_points: List[Tuple[float, float]] = [(round(start[0], 6), round(start[1], 6))]

        prev_lat, prev_lng = start
        for idx in order:
            wp = waypoints[idx]
            dist = round(estimate_road_distance_km(prev_lat, prev_lng, wp.latitude, wp.longitude), 3)
            drive_min = (dist / speed_kmh) * 60.0 + STOP_SERVICE_MINUTES
            leg_distances_km.append(dist)
            leg_durations_min.append(round(drive_min, 2))
            geometry_points.append((round(wp.latitude, 6), round(wp.longitude, 6)))
            prev_lat, prev_lng = wp.latitude, wp.longitude

        if return_to_hub:
            back_dist = round(estimate_road_distance_km(prev_lat, prev_lng, start[0], start[1]), 3)
            back_min = (back_dist / speed_kmh) * 60.0
            leg_distances_km.append(back_dist)
            leg_durations_min.append(round(back_min, 2))
            geometry_points.append((round(start[0], 6), round(start[1], 6)))

        total_dist = round(sum(leg_distances_km), 2)
        total_dur = round(sum(leg_durations_min), 1)
        baseline_rounded = round(baseline_distance, 2)
        saved_km = round(max(0.0, baseline_rounded - total_dist), 2)
        saved_pct = round((saved_km / baseline_rounded) * 100.0, 1) if baseline_rounded > 0 else 0.0

        return RouteComputationResult(
            provider_used=cls.provider_name,
            is_fallback=is_fallback,
            fallback_reason=fallback_reason,
            ordered_indices=order,
            leg_distances_km=leg_distances_km,
            leg_durations_min=leg_durations_min,
            total_distance_km=total_dist,
            total_duration_min=total_dur,
            baseline_distance_km=baseline_rounded,
            distance_saved_km=saved_km,
            distance_saved_pct=saved_pct,
            geometry_points=geometry_points,
        )


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
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < attempts - 1:
                sleep_fn(0.1 * (2**attempt))
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
            if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)) or is_retryable_status:
                if attempt < attempts - 1:
                    sleep_fn(0.1 * (2**attempt))
                    continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("HTTP request retry exhausted unexpectedly")


class OpenRouteServiceAdapter:
    """OpenRouteService directions adapter computing sequenced road polyline and ETAs."""

    provider_name = "openrouteservice"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        transport: Optional[httpx.BaseTransport] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self.api_key = (api_key if api_key is not None else settings.ORS_API_KEY).strip()
        self.base_url = (base_url or settings.ORS_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.ROUTING_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.ROUTING_MAX_RETRIES
        self.transport = transport
        self.sleep_fn = sleep_fn

    def compute_route(
        self,
        start: Tuple[float, float],
        waypoints: Sequence[Waypoint],
        vehicle_type: VehicleType = VehicleType.VAN,
        objective: str = "FASTEST",
        return_to_hub: bool = True,
    ) -> RouteComputationResult:
        if not self.api_key or self.api_key == "<SET_ME>":
            raise ValueError("ORS_API_KEY is not configured")

        # Determine initial stop order cleanly via local optimizer so ORS scores full road network
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
        for idx in local_plan.ordered_indices:
            wp = waypoints[idx]
            coords.append([wp.longitude, wp.latitude])
        if return_to_hub:
            coords.append([start[1], start[0]])

        profile = ORS_PROFILES.get(vehicle_type, "driving-car")
        preference = "shortest" if (objective or "").upper() == "SHORTEST" else "fastest"
        url = f"{self.base_url}/v2/directions/{profile}/geojson"

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
        payload = resp.json()
        features = payload.get("features") or []
        if not features:
            raise ValueError("OpenRouteService returned empty GeoJSON features")

        feat = features[0]
        raw_geom = feat.get("geometry", {}).get("coordinates") or []
        geometry_points = [(round(float(pt[1]), 6), round(float(pt[0]), 6)) for pt in raw_geom if len(pt) >= 2]
        segments = feat.get("properties", {}).get("segments") or []

        expected_legs = len(local_plan.ordered_indices) + (1 if return_to_hub else 0)
        if len(segments) != expected_legs:
            raise ValueError(f"OpenRouteService returned {len(segments)} segments, expected {expected_legs}")

        leg_distances_km = [round(float(seg.get("distance", 0.0)) / 1000.0, 3) for seg in segments]
        leg_durations_min = []
        for i, seg in enumerate(segments):
            drive_min = float(seg.get("duration", 0.0)) / 60.0
            if i < len(local_plan.ordered_indices):
                drive_min += STOP_SERVICE_MINUTES
            leg_durations_min.append(round(drive_min, 2))

        total_dist = round(sum(leg_distances_km), 2)
        total_dur = round(sum(leg_durations_min), 1)
        baseline_dist = local_plan.baseline_distance_km
        saved_km = round(max(0.0, baseline_dist - total_dist), 2)
        saved_pct = round((saved_km / baseline_dist) * 100.0, 1) if baseline_dist > 0 else 0.0

        return RouteComputationResult(
            provider_used=self.provider_name,
            is_fallback=False,
            fallback_reason=None,
            ordered_indices=local_plan.ordered_indices,
            leg_distances_km=leg_distances_km,
            leg_durations_min=leg_durations_min,
            total_distance_km=total_dist,
            total_duration_min=total_dur,
            baseline_distance_km=baseline_dist,
            distance_saved_km=saved_km,
            distance_saved_pct=saved_pct,
            geometry_points=geometry_points or local_plan.geometry_points,
        )


class OSRMAdapter:
    """OSRM Trip / Route adapter using OpenStreetMap road topology."""

    provider_name = "osrm"

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        transport: Optional[httpx.BaseTransport] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self.base_url = (base_url or settings.OSRM_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.ROUTING_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.ROUTING_MAX_RETRIES
        self.transport = transport
        self.sleep_fn = sleep_fn

    def compute_route(
        self,
        start: Tuple[float, float],
        waypoints: Sequence[Waypoint],
        vehicle_type: VehicleType = VehicleType.VAN,
        objective: str = "FASTEST",
        return_to_hub: bool = True,
    ) -> RouteComputationResult:
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

        with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
            if normalized_obj == "MANUAL":
                if return_to_hub:
                    coords.append(f"{start[1]},{start[0]}")
                coord_str = ";".join(coords)
                url = f"{self.base_url}/route/v1/driving/{coord_str}"
                params = {"overview": "full", "geometries": "geojson"}
                resp = _request_with_retry(
                    client, "GET", url, max_retries=self.max_retries, sleep_fn=self.sleep_fn, params=params
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
                    client, "GET", url, max_retries=self.max_retries, sleep_fn=self.sleep_fn, params=params
                )
                data = resp.json()
                trips = data.get("trips") or []
                osrm_waypoints = data.get("waypoints") or []
                if not trips or len(osrm_waypoints) != len(waypoints) + 1:
                    raise ValueError("OSRM trip response missing trips or waypoints")
                route_obj = trips[0]
                # Map OSRM waypoint_index (skipping depot at input idx 0 -> waypoint_index 0) back to input stop indices
                indexed_order = [
                    (int(osrm_waypoints[i + 1]["waypoint_index"]), i) for i in range(len(waypoints))
                ]
                indexed_order.sort(key=lambda pair: pair[0])
                ordered_indices = [pair[1] for pair in indexed_order]

        raw_geom = route_obj.get("geometry", {}).get("coordinates") or []
        geometry_points = [(round(float(pt[1]), 6), round(float(pt[0]), 6)) for pt in raw_geom if len(pt) >= 2]
        legs = route_obj.get("legs") or []
        expected_legs = len(ordered_indices) + (1 if return_to_hub else 0)
        if len(legs) != expected_legs:
            raise ValueError(f"OSRM returned {len(legs)} legs, expected {expected_legs}")

        leg_distances_km = [round(float(leg.get("distance", 0.0)) / 1000.0, 3) for leg in legs]
        leg_durations_min = []
        for i, leg in enumerate(legs):
            drive_min = float(leg.get("duration", 0.0)) / 60.0
            if i < len(ordered_indices):
                drive_min += STOP_SERVICE_MINUTES
            leg_durations_min.append(round(drive_min, 2))

        total_dist = round(sum(leg_distances_km), 2)
        total_dur = round(sum(leg_durations_min), 1)
        baseline_dist = baseline_plan.baseline_distance_km
        saved_km = round(max(0.0, baseline_dist - total_dist), 2)
        saved_pct = round((saved_km / baseline_dist) * 100.0, 1) if baseline_dist > 0 else 0.0

        return RouteComputationResult(
            provider_used=self.provider_name,
            is_fallback=False,
            fallback_reason=None,
            ordered_indices=ordered_indices,
            leg_distances_km=leg_distances_km,
            leg_durations_min=leg_durations_min,
            total_distance_km=total_dist,
            total_duration_min=total_dur,
            baseline_distance_km=baseline_dist,
            distance_saved_km=saved_km,
            distance_saved_pct=saved_pct,
            geometry_points=geometry_points or baseline_plan.geometry_points,
        )


class RoutingEngine:
    """Facade selecting configured routing adapter with graceful degradation to local 2-opt."""

    @classmethod
    def compute_route(
        cls,
        start: Tuple[float, float],
        waypoints: Sequence[Waypoint],
        vehicle_type: VehicleType = VehicleType.VAN,
        objective: str = "FASTEST",
        provider: Optional[str] = None,
        return_to_hub: bool = True,
        ors_adapter: Optional[OpenRouteServiceAdapter] = None,
        osrm_adapter: Optional[OSRMAdapter] = None,
    ) -> RouteComputationResult:
        requested = (provider or settings.ROUTING_PROVIDER or "local").strip().lower()
        if requested in {"auto", "default"}:
            requested = (settings.ROUTING_PROVIDER or "local").strip().lower()

        if requested in {"local", "local_fallback"}:
            return LocalHaversineOptimizer.compute_route(
                start=start,
                waypoints=waypoints,
                vehicle_type=vehicle_type,
                objective=objective,
                return_to_hub=return_to_hub,
                is_fallback=False,
                fallback_reason=None,
            )

        if requested == "openrouteservice":
            adapter = ors_adapter or OpenRouteServiceAdapter()
            try:
                return adapter.compute_route(
                    start=start,
                    waypoints=waypoints,
                    vehicle_type=vehicle_type,
                    objective=objective,
                    return_to_hub=return_to_hub,
                )
            except ValueError as exc:
                reason = f"OpenRouteService unavailable ({exc}); degraded cleanly to local 2-opt optimizer"
                logger.warning("Routing provider fallback triggered: %s", reason)
                return LocalHaversineOptimizer.compute_route(
                    start=start,
                    waypoints=waypoints,
                    vehicle_type=vehicle_type,
                    objective=objective,
                    return_to_hub=return_to_hub,
                    is_fallback=True,
                    fallback_reason=reason,
                )
            except Exception as exc:
                reason = f"OpenRouteService unavailable ({type(exc).__name__}); degraded cleanly to local 2-opt optimizer"
                logger.warning("Routing provider fallback triggered: %s", reason)
                return LocalHaversineOptimizer.compute_route(
                    start=start,
                    waypoints=waypoints,
                    vehicle_type=vehicle_type,
                    objective=objective,
                    return_to_hub=return_to_hub,
                    is_fallback=True,
                    fallback_reason=reason,
                )

        if requested == "osrm":
            adapter = osrm_adapter or OSRMAdapter()
            try:
                return adapter.compute_route(
                    start=start,
                    waypoints=waypoints,
                    vehicle_type=vehicle_type,
                    objective=objective,
                    return_to_hub=return_to_hub,
                )
            except Exception as exc:
                reason = f"OSRM unavailable ({type(exc).__name__}); degraded cleanly to local 2-opt optimizer"
                logger.warning("Routing provider fallback triggered: %s", reason)
                return LocalHaversineOptimizer.compute_route(
                    start=start,
                    waypoints=waypoints,
                    vehicle_type=vehicle_type,
                    objective=objective,
                    return_to_hub=return_to_hub,
                    is_fallback=True,
                    fallback_reason=reason,
                )

        reason = f"Unknown routing provider '{requested}'; used local 2-opt optimizer"
        return LocalHaversineOptimizer.compute_route(
            start=start,
            waypoints=waypoints,
            vehicle_type=vehicle_type,
            objective=objective,
            return_to_hub=return_to_hub,
            is_fallback=True,
            fallback_reason=reason,
        )
