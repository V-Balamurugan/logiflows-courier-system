"""Normalized Pydantic schemas for multi-provider route optimization."""
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class DistanceBasis(str, Enum):
    """Methodology utilized to derive distance and travel duration."""

    STRAIGHT_LINE = "STRAIGHT_LINE"
    ROAD_ESTIMATE = "ROAD_ESTIMATE"
    PROVIDER_ROAD = "PROVIDER_ROAD"


class OptimizationStatus(str, Enum):
    """Mathematical convergence and feasibility state of the route solution."""

    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    HEURISTIC = "HEURISTIC"
    INFEASIBLE = "INFEASIBLE"
    TIMEOUT = "TIMEOUT"


class RouteLegResult(BaseModel):
    """Discrete leg traversed between two consecutive waypoints or hub."""

    from_index: int
    to_index: int
    distance_m: float = Field(..., ge=0.0, description="Road or estimated distance in meters")
    duration_s: float = Field(..., ge=0.0, description="Travel and service duration in seconds")
    distance_basis: DistanceBasis = DistanceBasis.ROAD_ESTIMATE

    @property
    def distance_km(self) -> float:
        return round(self.distance_m / 1000.0, 3)

    @property
    def duration_min(self) -> float:
        return round(self.duration_s / 60.0, 2)


class PerStopETAResult(BaseModel):
    """Per-stop estimated time of arrival, duration from previous stop, and waiting time."""

    stop_index: int
    eta_minutes_from_start: float = Field(..., ge=0.0)
    estimated_arrival_at: Optional[datetime] = None
    distance_from_prev_m: float = Field(default=0.0, ge=0.0)
    duration_from_prev_s: float = Field(default=0.0, ge=0.0)
    waiting_time_s: float = Field(default=0.0, ge=0.0)
    service_time_s: float = Field(default=300.0, ge=0.0)  # default 5 minutes service


class RouteProvenance(BaseModel):
    """Auditable data provenance documenting data sources, algorithm, and timestamps."""

    data_source: str
    calculation_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    algorithm: str
    version: str = "2.0.0"


class RoutePlanResult(BaseModel):
    """Standardized normalized contract returned by all routing optimization providers."""

    provider_used: str
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    ordered_stops: List[int]
    legs: List[RouteLegResult]
    total_distance_m: float = Field(..., ge=0.0)
    total_duration_s: float = Field(..., ge=0.0)
    geometry: Optional[List[List[float]]] = None  # None for local fallback; strictly road points when provider returns
    per_stop_eta: List[PerStopETAResult] = Field(default_factory=list)
    objective: str = "FASTEST"
    optimization_status: OptimizationStatus = OptimizationStatus.HEURISTIC
    warnings: List[str] = Field(default_factory=list)
    provenance: RouteProvenance
    baseline_distance_m: float = 0.0

    # Backward compatibility properties for existing RouteComputationResult callers
    @property
    def ordered_indices(self) -> List[int]:
        return self.ordered_stops

    @property
    def is_fallback(self) -> bool:
        return self.fallback_used

    @property
    def total_distance_km(self) -> float:
        return round(self.total_distance_m / 1000.0, 3)

    @property
    def total_duration_min(self) -> float:
        return round(self.total_duration_s / 60.0, 1)

    @property
    def leg_distances_km(self) -> List[float]:
        return [leg.distance_km for leg in self.legs]

    @property
    def leg_durations_min(self) -> List[float]:
        return [leg.duration_min for leg in self.legs]

    @property
    def geometry_points(self) -> List[Tuple[float, float]]:
        if not self.geometry:
            return []
        return [(pt[0], pt[1]) for pt in self.geometry]

    @property
    def baseline_distance_km(self) -> float:
        return round(self.baseline_distance_m / 1000.0, 3)

    @property
    def distance_saved_km(self) -> float:
        saved = max(0.0, self.baseline_distance_km - self.total_distance_km)
        return round(saved, 3)

    @property
    def distance_saved_pct(self) -> float:
        if self.baseline_distance_km <= 0.0:
            return 0.0
        return round((self.distance_saved_km / self.baseline_distance_km) * 100.0, 1)


# Alias for backward-compatible type hints
RouteComputationResult = RoutePlanResult
