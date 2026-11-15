"""
Legacy compatibility module for routing provider adapters and TSP optimizer.
All core components are partitioned under `app.services.routing`.
"""
from app.schemas.route_plan import (
    DistanceBasis,
    OptimizationStatus,
    PerStopETAResult,
    RouteComputationResult,
    RouteLegResult,
    RoutePlanResult,
    RouteProvenance,
)
from app.services.routing import (
    BaseRoutingProvider,
    CircuitBreaker,
    CircuitState,
    LocalHaversineOptimizer,
    OpenRouteServiceAdapter,
    OSRMAdapter,
    RoutingEngine,
    Waypoint,
    derive_branch_vicinity_coords,
    estimate_road_distance_km,
    haversine_km,
    validate_lat_lng,
)
from app.services.routing.base import (
    DEFAULT_ROAD_TORTUOSITY,
    EARTH_RADIUS_KM,
    MAX_TWO_OPT_ITERATIONS,
    ORS_PROFILES,
    RETRYABLE_STATUS_CODES,
    STOP_SERVICE_MINUTES,
    VEHICLE_SPEED_KMH,
)

__all__ = [
    "BaseRoutingProvider",
    "CircuitBreaker",
    "CircuitState",
    "DEFAULT_ROAD_TORTUOSITY",
    "DistanceBasis",
    "EARTH_RADIUS_KM",
    "LocalHaversineOptimizer",
    "MAX_TWO_OPT_ITERATIONS",
    "ORS_PROFILES",
    "OSRMAdapter",
    "OptimizationStatus",
    "PerStopETAResult",
    "RETRYABLE_STATUS_CODES",
    "RouteComputationResult",
    "RouteLegResult",
    "RoutePlanResult",
    "RouteProvenance",
    "RoutingEngine",
    "STOP_SERVICE_MINUTES",
    "VEHICLE_SPEED_KMH",
    "Waypoint",
    "derive_branch_vicinity_coords",
    "estimate_road_distance_km",
    "haversine_km",
    "validate_lat_lng",
]
