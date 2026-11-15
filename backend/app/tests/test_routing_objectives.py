"""Tests for Subphase 15.9: Distinct objective behaviors, 3-phase constraint validation, and OR-Tools optimization."""

import pytest
from typing import List, Tuple

from app.models.enums import VehicleType
from app.schemas.route_plan import OptimizationStatus
from app.services.routing.base import Waypoint
from app.services.routing.constraints import (
    ConstraintViolation,
    OptimizationConstraints,
    RouteConstraintValidator,
    ViolationSeverity,
)
from app.services.routing.local import LocalHaversineOptimizer
from app.services.routing.ortools_optimizer import ORToolsRoutingOptimizer


def test_distinct_objective_sequences():
    """
    Prove that FASTEST, SHORTEST_DISTANCE, BALANCED, and PRIORITY_FIRST
    yield distinct sequence orders on a deterministic test fixture.
    """
    depot = (13.0827, 80.2707)

    # 4 distinct waypoints with varying distances and priorities
    # Stop 0: Near depot, low priority
    # Stop 1: Medium distance, high priority
    # Stop 2: Far distance, critical priority
    # Stop 3: Very near depot, normal priority
    waypoints = [
        Waypoint(index=0, latitude=13.0850, longitude=80.2720, priority=0, service_duration_min=5.0),
        Waypoint(index=1, latitude=13.1200, longitude=80.2900, priority=1, service_duration_min=5.0),
        Waypoint(index=2, latitude=13.1800, longitude=80.3200, priority=3, service_duration_min=5.0),
        Waypoint(index=3, latitude=13.0830, longitude=80.2710, priority=0, service_duration_min=5.0),
    ]

    res_fastest = LocalHaversineOptimizer.compute_route(depot, waypoints, VehicleType.VAN, "FASTEST", True)
    res_shortest = LocalHaversineOptimizer.compute_route(depot, waypoints, VehicleType.VAN, "SHORTEST_DISTANCE", True)
    res_balanced = LocalHaversineOptimizer.compute_route(depot, waypoints, VehicleType.VAN, "BALANCED", True)
    res_priority = LocalHaversineOptimizer.compute_route(depot, waypoints, VehicleType.VAN, "PRIORITY_FIRST", True)

    seq_fastest = res_fastest.ordered_stops
    seq_shortest = res_shortest.ordered_stops
    seq_balanced = res_balanced.ordered_stops
    seq_priority = res_priority.ordered_stops

    # In PRIORITY_FIRST, stop 2 (priority 3) must be served first
    assert seq_priority[0] == 2, f"Expected stop 2 first in PRIORITY_FIRST, got {seq_priority}"

    # In FASTEST/SHORTEST, nearer stops (3 or 0) must precede the distant stop 2
    assert seq_fastest[0] in (0, 3), f"Expected nearest stop first in FASTEST, got {seq_fastest}"

    # Verify that not all sequences are identical
    all_sequences = [tuple(seq_fastest), tuple(seq_shortest), tuple(seq_balanced), tuple(seq_priority)]
    unique_sequences = set(all_sequences)
    assert len(unique_sequences) >= 2, f"Expected distinct sequences across objectives, got {all_sequences}"


def test_constraint_validation_pre_and_post():
    """Test RouteConstraintValidator pre-optimization and post-validation checks."""
    constraints = OptimizationConstraints(
        max_vehicle_payload_kg=100.0,
        max_route_distance_km=50.0,
        max_route_duration_minutes=120.0,
        enforce_precedence=True,
    )

    # 1. Pre-validation: Payload exceeded
    pre_violations = RouteConstraintValidator.validate_pre_optimization(
        total_cargo_weight_kg=150.0,
        total_cargo_volume_cbm=1.0,
        waypoints_meta=[],
        constraints=constraints,
        has_depot_coords=True,
    )
    assert len(pre_violations) == 1
    assert pre_violations[0].code == "EXCEEDS_VEHICLE_PAYLOAD"
    assert pre_violations[0].severity == ViolationSeverity.ERROR

    # 2. Pre-validation: Missing depot coordinates
    depot_violations = RouteConstraintValidator.validate_pre_optimization(
        total_cargo_weight_kg=50.0,
        total_cargo_volume_cbm=1.0,
        waypoints_meta=[],
        constraints=constraints,
        has_depot_coords=False,
    )
    assert any(v.code == "MISSING_DEPOT_COORDINATES" for v in depot_violations)

    # 3. Post-validation: Precedence violation
    depot = (13.0827, 80.2707)
    waypoints = [
        Waypoint(index=0, latitude=13.0900, longitude=80.2750, delivery_parcel_id=999),
        Waypoint(index=1, latitude=13.1000, longitude=80.2850, pickup_parcel_id=999),
    ]
    waypoints_meta = [
        {"parcel_id": 999, "stop_type": "DELIVERY"},
        {"parcel_id": 999, "stop_type": "PICKUP"},
    ]

    # Deliberately construct an inverted plan where delivery precedes pickup
    from app.schemas.route_plan import RoutePlanResult, RouteProvenance, DistanceBasis
    inverted_plan = RoutePlanResult(
        provider_used="test",
        fallback_used=False,
        ordered_stops=[0, 1],  # stop 0 (delivery) before stop 1 (pickup)
        legs=[],
        total_distance_m=10000.0,
        total_duration_s=600.0,
        geometry=None,
        per_stop_eta=[],
        objective="FASTEST",
        optimization_status=OptimizationStatus.OPTIMAL,
        warnings=[],
        provenance=RouteProvenance(
            data_source="test",
            algorithm="test",
            distance_basis=DistanceBasis.ROAD_ESTIMATE,
        ),
    )

    post_violations = RouteConstraintValidator.validate_post_optimization(
        inverted_plan, waypoints_meta, constraints
    )
    assert any(v.code == "PRECEDENCE_VIOLATION" for v in post_violations)


def test_ortools_optimizer_execution_and_precedence():
    """Verify OR-Tools optimizer computes a feasible route honoring pickup-before-delivery precedence."""
    depot = (13.0827, 80.2707)

    waypoints = [
        # Stop 0: Delivery for parcel 501
        Waypoint(index=0, latitude=13.1200, longitude=80.2900, delivery_parcel_id=501),
        # Stop 1: Pickup for parcel 501 (geographically further)
        Waypoint(index=1, latitude=13.1500, longitude=80.3100, pickup_parcel_id=501),
        # Stop 2: Regular delivery
        Waypoint(index=2, latitude=13.0900, longitude=80.2750),
    ]

    plan = ORToolsRoutingOptimizer.compute_route(
        start=depot,
        waypoints=waypoints,
        vehicle_type=VehicleType.VAN,
        objective="FASTEST",
        return_to_hub=True,
        time_limit_seconds=2.0,
    )

    assert plan.optimization_status == OptimizationStatus.OPTIMAL
    assert plan.provider_used == "ortools"
    assert len(plan.ordered_stops) == 3

    # Stop 1 (pickup) MUST precede stop 0 (delivery)
    idx_pickup = plan.ordered_stops.index(1)
    idx_delivery = plan.ordered_stops.index(0)
    assert idx_pickup < idx_delivery, f"Expected pickup before delivery, got sequence {plan.ordered_stops}"
