"""RoutingEngine facade orchestrating provider selection, circuit breakers, and fallback."""
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.core.config import settings
from app.models.enums import VehicleType
from app.schemas.route_plan import (
    DistanceBasis,
    OptimizationStatus,
    RoutePlanResult,
)
from app.services.routing.base import (
    BaseRoutingProvider,
    Waypoint,
)
from app.services.routing.local import LocalHaversineOptimizer
from app.services.routing.ors import OpenRouteServiceAdapter
from app.services.routing.osrm import OSRMAdapter
from app.services.routing.ortools_optimizer import ORToolsRoutingOptimizer

logger = logging.getLogger(__name__)


class RoutingEngine:
    """
    Unified entrypoint managing provider selection, pluggable registry,
    fault-tolerant circuit breakers, and graceful local degradation.
    """

    _registry: Dict[str, BaseRoutingProvider] = {}
    _default_ors: Optional[OpenRouteServiceAdapter] = None
    _default_osrm: Optional[OSRMAdapter] = None

    @classmethod
    def register_provider(cls, name: str, provider: BaseRoutingProvider) -> None:
        """Register a custom routing provider adapter at runtime."""
        clean_name = name.strip().lower()
        cls._registry[clean_name] = provider
        logger.info("Registered routing provider adapter: '%s'", clean_name)

    @classmethod
    def unregister_provider(cls, name: str) -> None:
        """Remove a custom routing provider adapter."""
        clean_name = name.strip().lower()
        if clean_name in cls._registry:
            del cls._registry[clean_name]
            logger.info("Unregistered routing provider adapter: '%s'", clean_name)

    @classmethod
    def get_provider(cls, name: str) -> Optional[BaseRoutingProvider]:
        """Lookup provider by registered name."""
        return cls._registry.get(name.strip().lower())

    @classmethod
    def get_providers_health(cls) -> Dict[str, Any]:
        """Diagnostic health view reporting circuit breakers, quotas, and provider status."""
        ors = cls._default_ors or OpenRouteServiceAdapter()
        osrm = cls._default_osrm or OSRMAdapter()

        return {
            "configured_default_provider": settings.ROUTING_PROVIDER or "local",
            "registered_providers": list(cls._registry.keys()) + ["local", "openrouteservice", "osrm", "ortools"],
            "circuit_breakers": {
                "openrouteservice": ors.circuit_breaker.get_health(),
                "osrm": osrm.circuit_breaker.get_health(),
            },
            "openrouteservice": {
                "configured": bool(ors.api_key and ors.api_key != "<SET_ME>"),
                "base_url": ors.base_url,
                "rate_limit_remaining": ors.rate_limit_remaining,
            },
            "osrm": {
                "base_url": osrm.base_url,
                "reachable": osrm.check_health(),
            },
        }

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
    ) -> RoutePlanResult:
        """
        Compute optimal route across waypoints.

        Graceful Fallback Policy:
        1. Attempt requested provider (or custom registered adapter).
        2. If external provider fails (network timeout, rate limit, circuit breaker OPEN, 5xx),
           log structured warning without leaking credentials and degrade cleanly to local 2-opt.
        """
        requested = (provider or settings.ROUTING_PROVIDER or "local").strip().lower()
        if requested in {"auto", "default"}:
            requested = (settings.ROUTING_PROVIDER or "local").strip().lower()

        # Check pluggable registered custom providers
        if requested in cls._registry:
            custom_provider = cls._registry[requested]
            try:
                return custom_provider.compute_route(
                    start=start,
                    waypoints=waypoints,
                    vehicle_type=vehicle_type,
                    objective=objective,
                    return_to_hub=return_to_hub,
                )
            except Exception as exc:
                reason = f"Custom provider '{requested}' failed ({type(exc).__name__}: {exc}); degraded to local fallback"
                logger.warning("Routing fallback triggered: %s", reason)
                return LocalHaversineOptimizer.compute_route(
                    start=start,
                    waypoints=waypoints,
                    vehicle_type=vehicle_type,
                    objective=objective,
                    return_to_hub=return_to_hub,
                    is_fallback=True,
                    fallback_reason=reason,
                )

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

        if requested == "ortools":
            try:
                return ORToolsRoutingOptimizer.compute_route(
                    start=start,
                    waypoints=waypoints,
                    vehicle_type=vehicle_type,
                    objective=objective,
                    return_to_hub=return_to_hub,
                )
            except Exception as exc:
                reason = f"ORToolsRoutingOptimizer failed ({type(exc).__name__}: {exc}); degraded cleanly to local 2-opt"
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

        if requested == "openrouteservice":
            adapter = ors_adapter or cls._default_ors or OpenRouteServiceAdapter()
            cls._default_ors = adapter
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
            adapter = osrm_adapter or cls._default_osrm or OSRMAdapter()
            cls._default_osrm = adapter
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
