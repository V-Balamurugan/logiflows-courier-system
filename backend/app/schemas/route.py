"""Pydantic v2 request and response schemas for Phase 15 route optimization & execution."""
from datetime import datetime
import math
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    CoordinateSource,
    CoordinateVerificationStatus,
    RouteObjective,
    RouteStatus,
    RouteStopStatus,
    RouteStopType,
)


def _check_finite(val: Optional[float], name: str) -> Optional[float]:
    if val is not None and (math.isnan(val) or math.isinf(val)):
        raise ValueError(f"{name} must be a valid finite number")
    return val


class RouteStopInput(BaseModel):
    """Single pickup/delivery waypoint or parcel stop supplied during route planning."""

    model_config = ConfigDict(extra="forbid")

    parcel_id: Optional[int] = None
    stop_type: RouteStopType = RouteStopType.DELIVERY
    location_name: Optional[str] = Field(None, min_length=2, max_length=255)
    address: Optional[str] = Field(None, max_length=500)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("latitude", "longitude")
    @classmethod
    def validate_finite_coords(cls, v: Optional[float], info) -> Optional[float]:
        return _check_finite(v, info.field_name)

    @model_validator(mode="after")
    def validate_stop_requirements(self) -> "RouteStopInput":
        has_lat = self.latitude is not None
        has_lng = self.longitude is not None
        if has_lat != has_lng:
            raise ValueError("latitude and longitude must both be provided together")
        if self.parcel_id is None:
            if not has_lat or not has_lng:
                raise ValueError("Ad-hoc stops without parcel_id must specify latitude and longitude")
            if not self.location_name:
                raise ValueError("Ad-hoc stops without parcel_id must specify location_name")
        return self


class RoutePreviewRequest(BaseModel):
    """Stateless route optimization preview input without persisting locks or entities."""

    model_config = ConfigDict(extra="forbid")

    branch_id: int
    vehicle_id: Optional[int] = None
    objective: RouteObjective = RouteObjective.FASTEST
    provider: str = Field(
        "auto", pattern="^(auto|local|local_fallback|openrouteservice|osrm)$"
    )
    return_to_hub: bool = True
    parcel_ids: Optional[List[int]] = Field(None, min_length=1, max_length=100)
    stops: Optional[List[RouteStopInput]] = Field(None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_stops_present(self) -> "RoutePreviewRequest":
        if not self.parcel_ids and not self.stops:
            raise ValueError("Provide either parcel_ids or stops to optimize a route")
        if self.parcel_ids and len(set(self.parcel_ids)) != len(self.parcel_ids):
            raise ValueError("Duplicate parcel_id values are not allowed in the same route")
        if self.stops:
            pids = [s.parcel_id for s in self.stops if s.parcel_id is not None]
            if len(set(pids)) != len(pids):
                raise ValueError("Duplicate parcel_id values are not allowed in stops")
        return self


class RouteCreateRequest(RoutePreviewRequest):
    """Persist an optimized multi-stop route plan anchored to a branch hub."""

    driver_id: Optional[int] = None
    notes: Optional[str] = Field(None, max_length=1000)


class RouteReoptimizeRequest(BaseModel):
    """Re-optimize or manually reorder stops on an active route."""

    model_config = ConfigDict(extra="forbid")

    objective: RouteObjective = RouteObjective.FASTEST
    provider: str = Field(
        "auto", pattern="^(auto|local|local_fallback|openrouteservice|osrm)$"
    )
    return_to_hub: Optional[bool] = None
    manual_stop_ids: Optional[List[int]] = None
    expected_version_id: Optional[int] = None
    idempotency_key: Optional[str] = Field(None, max_length=128)

    @model_validator(mode="after")
    def validate_manual_order(self) -> "RouteReoptimizeRequest":
        if self.objective == RouteObjective.MANUAL and not self.manual_stop_ids:
            raise ValueError("manual_stop_ids is required when objective is MANUAL")
        if self.manual_stop_ids and len(set(self.manual_stop_ids)) != len(self.manual_stop_ids):
            raise ValueError("manual_stop_ids cannot contain duplicates")
        return self


class RouteDispatchRequest(BaseModel):
    """Atomically claim vehicle, link driver assignments, and dispatch route."""

    model_config = ConfigDict(extra="forbid")

    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    expected_version_id: Optional[int] = None
    idempotency_key: Optional[str] = Field(None, max_length=128)
    low_confidence_override_reason: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=500)


class RouteStopUpdateRequest(BaseModel):
    """Update individual stop arrival/completion/failure progression with optional GPS."""

    model_config = ConfigDict(extra="forbid")

    status: RouteStopStatus
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    failure_reason: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("latitude", "longitude")
    @classmethod
    def validate_finite_coords(cls, v: Optional[float], info) -> Optional[float]:
        return _check_finite(v, info.field_name)

    @model_validator(mode="after")
    def validate_gps_pair_and_failure(self) -> "RouteStopUpdateRequest":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must both be provided together")
        if self.status == RouteStopStatus.FAILED and not (self.failure_reason and self.failure_reason.strip()):
            raise ValueError("failure_reason is required when marking a stop FAILED")
        return self


class RouteCancelRequest(BaseModel):
    """Cancel a planned or dispatched route and restore vehicle/parcel locks."""

    model_config = ConfigDict(extra="forbid")

    cancellation_reason: str = Field(..., min_length=3, max_length=500)


class RoutePreviewStop(BaseModel):
    """Computed preview stop position, ETA, and coordinate provenance."""

    sequence_order: int
    parcel_id: Optional[int] = None
    tracking_number: Optional[str] = None
    stop_type: RouteStopType
    location_name: str
    address: Optional[str] = None
    latitude: float
    longitude: float
    coords_source: str
    coordinate_source: CoordinateSource = CoordinateSource.BRANCH_VICINITY_ESTIMATE
    confidence: Optional[float] = None
    verification_status: CoordinateVerificationStatus = CoordinateVerificationStatus.UNVERIFIED
    parcel_weight_kg: float = 0.0
    distance_from_prev_km: float
    eta_minutes_from_start: float


class RoutePreviewResponse(BaseModel):
    """Stateless route optimization comparison preview."""

    branch_id: int
    branch_name: str
    start_latitude: float
    start_longitude: float
    vehicle_id: Optional[int] = None
    vehicle_number: Optional[str] = None
    vehicle_max_weight_kg: Optional[float] = None
    total_weight_kg: float
    utilization_pct: Optional[float] = None
    capacity_exceeded: bool = False
    objective: RouteObjective
    return_to_hub: bool
    provider_used: str
    is_fallback: bool
    fallback_reason: Optional[str] = None
    has_low_confidence_stops: bool = False
    low_confidence_stops_count: int = 0
    baseline_distance_km: float
    total_distance_km: float
    distance_saved_km: float
    distance_saved_pct: float
    estimated_duration_min: float
    geometry_points: List[List[float]]
    stops: List[RoutePreviewStop]


class RouteStopResponse(BaseModel):
    """Persisted stop representation with parcel & assignment linkage."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    route_id: int
    parcel_id: Optional[int] = None
    tracking_number: Optional[str] = None
    receiver_name: Optional[str] = None
    parcel_weight_kg: Optional[float] = None
    assignment_id: Optional[int] = None
    sequence_order: int
    stop_type: RouteStopType
    status: RouteStopStatus
    is_active: bool
    location_name: str
    address: Optional[str] = None
    latitude: float
    longitude: float
    coords_source: str
    coordinate_source: CoordinateSource = CoordinateSource.BRANCH_VICINITY_ESTIMATE
    confidence: Optional[float] = None
    verification_status: CoordinateVerificationStatus = CoordinateVerificationStatus.UNVERIFIED
    last_verified_at: Optional[datetime] = None
    normalized_address: Optional[str] = None
    distance_from_prev_km: float
    eta_minutes_from_start: float
    estimated_arrival_at: Optional[datetime] = None
    arrived_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    notes: Optional[str] = None


class DeliveryRouteResponse(BaseModel):
    """Full persisted DeliveryRoute with ordered stops and route polyline geometry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    route_code: str
    organization_id: int
    branch_id: int
    branch_name: Optional[str] = None
    vehicle_id: Optional[int] = None
    vehicle_number: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_max_weight_kg: Optional[float] = None
    driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    status: RouteStatus
    is_active_dispatch: bool
    optimization_objective: RouteObjective
    provider_used: str
    is_fallback: bool
    fallback_reason: Optional[str] = None
    return_to_hub: bool
    start_latitude: Optional[float] = None
    start_longitude: Optional[float] = None
    total_distance_km: float
    baseline_distance_km: float
    distance_saved_km: float
    distance_saved_pct: float = 0.0
    estimated_duration_min: float
    total_weight_kg: float
    utilization_pct: Optional[float] = None
    total_stops: int
    completed_stops: int
    geometry_points: List[List[float]] = []
    notes: Optional[str] = None
    version_id: int
    idempotency_key: Optional[str] = None
    has_low_confidence_stops: bool = False
    low_confidence_override_reason: Optional[str] = None
    low_confidence_overridden_by_id: Optional[int] = None
    low_confidence_overridden_at: Optional[datetime] = None
    dispatched_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    stops: List[RouteStopResponse] = []

class DriverAllocationCandidate(BaseModel):
    """Explainable evaluation of a delivery driver candidate for route dispatch."""

    driver_id: int
    driver_name: str
    employee_code: Optional[str] = None
    is_eligible: bool
    current_active_routes: int = 0
    current_active_assignments: int = 0
    shift: Optional[str] = None
    score: float = 0.0
    suitability_reasons: List[str] = []
    blocking_reasons: List[str] = []


class VehicleAllocationCandidate(BaseModel):
    """Explainable evaluation of a fleet vehicle candidate for route dispatch."""

    vehicle_id: int
    vehicle_number: str
    vehicle_type: str
    max_weight_kg: float
    is_eligible: bool
    capacity_utilization_pct: Optional[float] = None
    status: str
    score: float = 0.0
    suitability_reasons: List[str] = []
    blocking_reasons: List[str] = []


class RouteAllocationRecommendationResponse(BaseModel):
    """Explainable ranked driver and vehicle allocation recommendations."""

    route_id: int
    route_code: str
    total_weight_kg: float
    estimated_duration_min: float
    recommended_drivers: List[DriverAllocationCandidate]
    recommended_vehicles: List[VehicleAllocationCandidate]

class DriverTelemetryInput(BaseModel):
    """Driver location telemetry stream update."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    speed_kmh: Optional[float] = Field(None, ge=0.0, le=250.0)
    heading_deg: Optional[float] = Field(None, ge=0.0, le=360.0)
    accuracy_m: Optional[float] = Field(None, ge=0.0, le=500.0)
    timestamp: Optional[datetime] = None


class DriverTelemetryResponse(BaseModel):
    """Dynamic ETA recalibration response derived from driver GPS telemetry."""

    route_id: int
    current_latitude: float
    current_longitude: float
    freshness_seconds: float
    is_stale: bool
    next_stop_id: Optional[int] = None
    next_stop_eta_minutes: Optional[float] = None
    remaining_stops_count: int
    remaining_distance_km: float
    remaining_duration_min: float
    eta_source: str = "GPS_ADJUSTED"
    recalculated_at: datetime
