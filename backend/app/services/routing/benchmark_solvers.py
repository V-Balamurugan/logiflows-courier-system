"""Benchmark suite comparing Nearest-Neighbor + 2-Opt vs Google OR-Tools VRP Solver."""
from datetime import datetime
import json
import math
import random
import time
from typing import Dict, List, Tuple

from app.models.enums import VehicleType
from app.services.routing.base import Waypoint
from app.services.routing.local import LocalHaversineOptimizer
from app.services.routing.ortools_optimizer import ORToolsRoutingOptimizer


def generate_seeded_fixture(num_stops: int, seed: int = 42, with_precedence: bool = False) -> Tuple[Tuple[float, float], List[Waypoint]]:
    """Generate deterministic synthetic waypoints around Chennai hub depot (13.0827, 80.2707)."""
    rng = random.Random(seed)
    depot = (13.0827, 80.2707)

    waypoints: List[Waypoint] = []
    num_pickups = num_stops // 4 if with_precedence else 0

    for i in range(num_stops):
        # Scatter within 0.15 degrees (~16 km)
        angle = rng.uniform(0, 2 * math.pi)
        radius = rng.uniform(0.02, 0.12)
        lat = round(depot[0] + radius * math.cos(angle), 6)
        lng = round(depot[1] + radius * math.sin(angle), 6)

        pickup_pid = None
        delivery_pid = None

        if with_precedence:
            if i < num_pickups:
                pickup_pid = 1000 + i
            elif i < 2 * num_pickups:
                delivery_pid = 1000 + (i - num_pickups)

        priority = rng.choice([0, 0, 1, 2])

        waypoints.append(
            Waypoint(
                index=i,
                latitude=lat,
                longitude=lng,
                service_duration_min=5.0,
                priority=priority,
                pickup_parcel_id=pickup_pid,
                delivery_parcel_id=delivery_pid,
            )
        )

    return depot, waypoints


def verify_precedence(order: List[int], waypoints: List[Waypoint]) -> Tuple[bool, int]:
    """Check pickup-before-delivery precedence and count violations."""
    seen_pickups = set()
    violations = 0
    for idx in order:
        wp = waypoints[idx]
        if wp.pickup_parcel_id is not None:
            seen_pickups.add(wp.pickup_parcel_id)
        if wp.delivery_parcel_id is not None:
            has_matching_pickup = any(w.pickup_parcel_id == wp.delivery_parcel_id for w in waypoints)
            if has_matching_pickup and wp.delivery_parcel_id not in seen_pickups:
                violations += 1
    return violations == 0, violations


def run_benchmark():
    test_cases = [
        {"stops": 10, "precedence": False, "label": "10 Stops - Basic TSP"},
        {"stops": 10, "precedence": True, "label": "10 Stops - With Precedence"},
        {"stops": 25, "precedence": False, "label": "25 Stops - Basic TSP"},
        {"stops": 25, "precedence": True, "label": "25 Stops - With Precedence"},
        {"stops": 50, "precedence": False, "label": "50 Stops - Basic TSP"},
        {"stops": 50, "precedence": True, "label": "50 Stops - With Precedence"},
    ]

    results = []

    print("| Fixture | Solver | Runtime (ms) | Distance (km) | Duration (min) | Precedence Valid |")
    print("|---|---|---|---|---|---|")

    for tc in test_cases:
        depot, waypoints = generate_seeded_fixture(tc["stops"], seed=42, with_precedence=tc["precedence"])

        # 1. Benchmark 2-Opt Heuristic
        t0 = time.perf_counter()
        res_2opt = LocalHaversineOptimizer.compute_route(depot, waypoints, VehicleType.VAN, "FASTEST", True)
        time_2opt_ms = (time.perf_counter() - t0) * 1000.0
        prec_ok_2opt, v_2opt = verify_precedence(res_2opt.ordered_stops, waypoints)
        dist_2opt_km = res_2opt.total_distance_m / 1000.0
        dur_2opt_min = res_2opt.total_duration_s / 60.0

        print(
            f"| {tc['label']} | NearestNeighbor+2-Opt | {time_2opt_ms:.2f} ms | {dist_2opt_km:.2f} km | {dur_2opt_min:.1f} min | {'YES' if prec_ok_2opt else f'NO ({v_2opt})'} |"
        )

        # 2. Benchmark OR-Tools
        t0 = time.perf_counter()
        res_ortools = ORToolsRoutingOptimizer.compute_route(depot, waypoints, VehicleType.VAN, "FASTEST", True, time_limit_seconds=3.0)
        time_ortools_ms = (time.perf_counter() - t0) * 1000.0
        prec_ok_ortools, v_ortools = verify_precedence(res_ortools.ordered_stops, waypoints)
        dist_ortools_km = res_ortools.total_distance_m / 1000.0
        dur_ortools_min = res_ortools.total_duration_s / 60.0

        print(
            f"| {tc['label']} | Google OR-Tools | {time_ortools_ms:.2f} ms | {dist_ortools_km:.2f} km | {dur_ortools_min:.1f} min | {'YES' if prec_ok_ortools else f'NO ({v_ortools})'} |"
        )

        results.append({
            "fixture": tc["label"],
            "heuristic": {
                "time_ms": round(time_2opt_ms, 2),
                "dist_km": round(dist_2opt_km, 2),
                "dur_min": round(dur_2opt_min, 1),
                "precedence_ok": prec_ok_2opt,
            },
            "ortools": {
                "time_ms": round(time_ortools_ms, 2),
                "dist_km": round(dist_ortools_km, 2),
                "dur_min": round(dur_ortools_min, 1),
                "precedence_ok": prec_ok_ortools,
            },
        })

    return results


if __name__ == "__main__":
    run_benchmark()
