"""Base routing abstractions, circuit breakers, and waypoint structures."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import logging
import math
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import httpx

from app.models.enums import VehicleType
from app.schemas.route_plan import (
    DistanceBasis,
    OptimizationStatus,
    PerStopETAResult,
    RouteLegResult,
    RoutePlanResult,
    RouteProvenance,
)

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
CLIENT_ERROR_STATUS_CODES = {400, 401, 403, 404, 422}


@dataclass(frozen=True)
class Waypoint:
    """Normalized geographic stop input passed into routing providers."""

    index: int
    latitude: float
    longitude: float
    label: str = ""
    priority: int = 0  # higher priority favors earlier service under BALANCED / PRIORITY_FIRST
    pickup_parcel_id: Optional[int] = None
    delivery_parcel_id: Optional[int] = None
    time_window_start_min: Optional[float] = None
    time_window_end_min: Optional[float] = None
    service_duration_min: float = STOP_SERVICE_MINUTES


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


class CircuitState(str, Enum):
    """Operational states for routing provider circuit breakers."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Fault-tolerance circuit breaker preventing cascading failures and latency spikes.

    - CLOSED: Normal operation; requests pass through.
    - OPEN: Tripped after `failure_threshold` consecutive failures; fails immediately without network calls.
    - HALF_OPEN: Entered after `recovery_timeout_seconds`; allows one probe request to test provider health.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 30.0,
        time_fn: Callable[[], float] = time.time,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.time_fn = time_fn

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_state_change: float = self.time_fn()
        self.last_error_message: Optional[str] = None

    def can_execute(self) -> bool:
        """Evaluate if an outbound request should be permitted."""
        now = self.time_fn()
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            elapsed = now - (self.last_failure_time or self.last_state_change)
            if elapsed >= self.recovery_timeout_seconds:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                logger.info(
                    "CircuitBreaker[%s]: recovery timeout expired (%.1fs). Entering HALF_OPEN probe state.",
                    self.name,
                    elapsed,
                )
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            # Allow only single probe execution
            return True

        return False

    def record_success(self) -> None:
        """Record successful execution and reset state to CLOSED."""
        self.success_count += 1
        self.failure_count = 0
        self.last_error_message = None
        if self.state != CircuitState.CLOSED:
            logger.info("CircuitBreaker[%s]: provider probe succeeded; resetting state to CLOSED.", self.name)
            self.state = CircuitState.CLOSED
            self.last_state_change = self.time_fn()

    def record_failure(self, error: Exception) -> None:
        """Record failure and trip to OPEN if threshold reached."""
        now = self.time_fn()
        self.failure_count += 1
        self.last_failure_time = now
        self.last_error_message = str(error)

        if self.state == CircuitState.HALF_OPEN:
            logger.warning(
                "CircuitBreaker[%s]: probe call failed in HALF_OPEN state (%s); returning to OPEN.",
                self.name,
                self.last_error_message,
            )
            self.state = CircuitState.OPEN
            self.last_state_change = now
        elif self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            logger.warning(
                "CircuitBreaker[%s]: failure threshold reached (%d); tripping circuit to OPEN.",
                self.name,
                self.failure_count,
            )
            self.state = CircuitState.OPEN
            self.last_state_change = now

    def reset(self) -> None:
        """Manually reset circuit breaker to clean CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.last_error_message = None
        self.last_state_change = self.time_fn()

    def get_health(self) -> Dict[str, Any]:
        """Return structured diagnostic health report."""
        now = self.time_fn()
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_seconds": self.recovery_timeout_seconds,
            "last_error": self.last_error_message,
            "seconds_since_last_failure": (
                round(now - self.last_failure_time, 1) if self.last_failure_time else None
            ),
        }


class BaseRoutingProvider(ABC):
    """Abstract base class for all routing and optimization provider adapters."""

    name: str

    @abstractmethod
    def compute_route(
        self,
        start: Tuple[float, float],
        waypoints: Sequence[Waypoint],
        vehicle_type: VehicleType = VehicleType.VAN,
        objective: str = "FASTEST",
        return_to_hub: bool = True,
    ) -> RoutePlanResult:
        """Compute sequenced route plan, distance, duration, and optional road geometry."""
        ...
