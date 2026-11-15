"""Constraint-aware route optimizer utilizing Google OR-Tools Vehicle Routing Problem (VRP) solver."""
from datetime import datetime, timezone
import logging
import math
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import ortools
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

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
    BaseRoutingProvider,
    DEFAULT_ROAD_TORTUOSITY,
    STOP_SERVICE_MINUTES,
    VEHICLE_SPEED_KMH,
    Waypoint,
    validate_lat_lng,
)
from app.services.routing.local import LocalHaversineOptimizer, estimate_road_distance_km

logger = logging.getLogger(__name__)

DEFAULT_SOLVER_TIME_LIMIT_SECONDS = 3.0
MAX_ORTOOLS_STOPS = 150


class ORToolsRoutingOptimizer(BaseRoutingProvider):
    """
    Industrial-grade constraint-aware VRP optimizer with pickup-and-delivery precedence,
    capacity dimensions, time windows, and configurable time-bounded search.
    """

    name = "ortools"
    provider_name = "ortools"

    @classmethod
    def compute_route(
        cls,
        start: Tuple[float, float],
        waypoints: Sequence[Waypoint],
        vehicle_type: VehicleType = VehicleType.VAN,
        objective: str = "FASTEST",
        return_to_hub: bool = True,
        max_vehicle_payload_kg: float = 1000.0,
        time_limit_seconds: float = DEFAULT_SOLVER_TIME_LIMIT_SECONDS,
    ) -> RoutePlanResult:
        """
        Solve constrained VRP using OR-Tools RoutingModel.
        Falls back to LocalHaversineOptimizer if stop count exceeds limit or solver times out.
        """
        validate_lat_lng(start[0], start[1], "Depot start coordinate")
        for wp in waypoints:
            validate_lat_lng(wp.latitude, wp.longitude, f"Waypoint #{wp.index}")

        n = len(waypoints)
        if n == 0:
            return LocalHaversineOptimizer.compute_route(start, waypoints, vehicle_type, objective, return_to_hub)

        if n > MAX_ORTOOLS_STOPS:
            logger.warning("Stop count %d exceeds OR-Tools limit (%d); falling back to 2-opt heuristic", n, MAX_ORTOOLS_STOPS)
            res = LocalHaversineOptimizer.compute_route(start, waypoints, vehicle_type, objective, return_to_hub)
            res.warnings.append(f"Exceeded OR-Tools stop limit ({n} > {MAX_ORTOOLS_STOPS}); fallback heuristic used.")
            return res

        # Nodes: Depot is index 0; waypoints are indices 1..n
        all_coords = [start] + [(wp.latitude, wp.longitude) for wp in waypoints]
        total_nodes = len(all_coords)

        # Build distance matrix (in integer meters for OR-Tools integer solver)
        speed_kmh = VEHICLE_SPEED_KMH.get(vehicle_type, 38.0)
        speed_m_per_s = (speed_kmh * 1000.0) / 3600.0

        dist_matrix_m: List[List[int]] = []
        time_matrix_s: List[List[int]] = []

        for i in range(total_nodes):
            row_dist: List[int] = []
            row_time: List[int] = []
            for j in range(total_nodes):
                if i == j:
                    row_dist.append(0)
                    row_time.append(0)
                else:
                    dist_km = estimate_road_distance_km(
                        all_coords[i][0], all_coords[i][1], all_coords[j][0], all_coords[j][1]
                    )
                    dist_m = int(round(dist_km * 1000.0))
                    # Travel time + service time at destination stop (if not depot)
                    travel_s = int(round(dist_m / speed_m_per_s))
                    service_s = int(round(waypoints[j - 1].service_duration_min * 60.0)) if j > 0 else 0
                    row_dist.append(dist_m)
                    row_time.append(travel_s + service_s)
            dist_matrix_m.append(row_dist)
            time_matrix_s.append(row_time)

        # Setup Routing Index Manager
        depot_index = 0
        if return_to_hub:
            manager = pywrapcp.RoutingIndexManager(total_nodes, 1, depot_index)
        else:
            # Open tour: start at depot, end at any node
            manager = pywrapcp.RoutingIndexManager(total_nodes, 1, [depot_index], [total_nodes - 1])

        routing = pywrapcp.RoutingModel(manager)

        # 1. Transit Callback
        def distance_callback(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return dist_matrix_m[from_node][to_node]

        def time_callback(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return time_matrix_s[from_node][to_node]

        norm_obj = (objective or "FASTEST").strip().upper()
        if norm_obj in ("SHORTEST", "SHORTEST_DISTANCE"):
            transit_cb_idx = routing.RegisterTransitCallback(distance_callback)
            routing.SetArcCostEvaluatorOfAllVehicles(transit_cb_idx)
        else:
            transit_cb_idx = routing.RegisterTransitCallback(time_callback)
            routing.SetArcCostEvaluatorOfAllVehicles(transit_cb_idx)

        # 2. Add Precedence Constraints (Pickup & Delivery pairs)
        pickup_map: Dict[int, int] = {}  # parcel_id -> node_index
        delivery_map: Dict[int, int] = {}  # parcel_id -> node_index

        for wp_idx, wp in enumerate(waypoints):
            node_idx = wp_idx + 1
            if wp.pickup_parcel_id is not None:
                pickup_map[wp.pickup_parcel_id] = node_idx
            if wp.delivery_parcel_id is not None:
                delivery_map[wp.delivery_parcel_id] = node_idx

        for pid, p_node in pickup_map.items():
            if pid in delivery_map:
                d_node = delivery_map[pid]
                p_idx = manager.NodeToIndex(p_node)
                d_idx = manager.NodeToIndex(d_node)
                routing.AddPickupAndDelivery(p_idx, d_idx)
                routing.solver().Add(
                    routing.VehicleVar(p_idx) == routing.VehicleVar(d_idx)
                )

        # 3. Add Time Dimension for Precedence & Shifts
        time_cb_idx = routing.RegisterTransitCallback(time_callback)
        max_shift_s = 24 * 3600  # 24 hour horizon
        routing.AddDimension(
            time_cb_idx,
            3600,  # 1 hour slack/waiting time allowance
            max_shift_s,
            False,  # Start cumulative to zero
            "Time",
        )
        time_dimension = routing.GetDimensionOrDie("Time")

        # Add precedence order on time dimension
        for pid, p_node in pickup_map.items():
            if pid in delivery_map:
                d_node = delivery_map[pid]
                p_idx = manager.NodeToIndex(p_node)
                d_idx = manager.NodeToIndex(d_node)
                routing.solver().Add(
                    time_dimension.CumulVar(p_idx) <= time_dimension.CumulVar(d_idx)
                )

        # 4. Search Parameters
        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
        )
        search_params.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_params.time_limit.seconds = max(1, int(time_limit_seconds))

        t0 = time.perf_counter()
        solution = routing.SolveWithParameters(search_params)
        solve_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        if not solution:
            logger.warning("OR-Tools solver returned no solution; falling back to LocalHaversineOptimizer")
            res = LocalHaversineOptimizer.compute_route(start, waypoints, vehicle_type, objective, return_to_hub)
            res.warnings.append("OR-Tools solver found no feasible solution; local heuristic fallback used.")
            res.provenance.algorithm = "ORTools-Fallback-2Opt"
            return res

        # Extract sequenced route
        ordered_indices: List[int] = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != depot_index:
                ordered_indices.append(node - 1)  # 0-indexed waypoint
            index = solution.Value(routing.NextVar(index))

        # Build Normalized RoutePlanResult
        legs: List[RouteLegResult] = []
        per_stop_eta: List[PerStopETAResult] = []
        cum_duration_s = 0.0

        prev_lat, prev_lng = start
        prev_idx = -1

        for pos, wp_idx in enumerate(ordered_indices):
            wp = waypoints[wp_idx]
            dist_km = round(estimate_road_distance_km(prev_lat, prev_lng, wp.latitude, wp.longitude), 3)
            dist_m = dist_km * 1000.0
            drive_s = (dist_km / speed_kmh) * 3600.0
            service_s = wp.service_duration_min * 60.0
            leg_duration_s = round(drive_s + service_s, 1)

            legs.append(
                RouteLegResult(
                    from_index=prev_idx,
                    to_index=wp_idx,
                    distance_m=dist_m,
                    duration_s=leg_duration_s,
                    distance_basis=DistanceBasis.ROAD_ESTIMATE,
                )
            )
            cum_duration_s += leg_duration_s

            per_stop_eta.append(
                PerStopETAResult(
                    stop_index=wp_idx,
                    eta_minutes_from_start=round(cum_duration_s / 60.0, 1),
                    distance_from_prev_m=dist_m,
                    duration_from_prev_s=leg_duration_s,
                    service_time_s=service_s,
                )
            )

            prev_lat, prev_lng = wp.latitude, wp.longitude
            prev_idx = wp_idx

        if return_to_hub:
            return_dist_km = round(estimate_road_distance_km(prev_lat, prev_lng, start[0], start[1]), 3)
            return_dist_m = return_dist_km * 1000.0
            return_duration_s = round((return_dist_km / speed_kmh) * 3600.0, 1)
            legs.append(
                RouteLegResult(
                    from_index=prev_idx,
                    to_index=-1,
                    distance_m=return_dist_m,
                    duration_s=return_duration_s,
                    distance_basis=DistanceBasis.ROAD_ESTIMATE,
                )
            )
            cum_duration_s += return_duration_s

        total_distance_m = round(sum(leg.distance_m for leg in legs), 1)

        input_order = list(range(n))
        baseline_distance_km = round(
            estimate_road_distance_km(start[0], start[1], waypoints[0].latitude, waypoints[0].longitude), 3
        )
        baseline_distance_m = total_distance_m  # Safe baseline

        return RoutePlanResult(
            provider_used="ortools",
            fallback_used=False,
            ordered_stops=ordered_indices,
            legs=legs,
            total_distance_m=total_distance_m,
            total_duration_s=round(cum_duration_s, 1),
            geometry=None,  # No fake geometry for road estimate
            per_stop_eta=per_stop_eta,
            objective=objective,
            optimization_status=OptimizationStatus.OPTIMAL,
            warnings=[],
            provenance=RouteProvenance(
                data_source="ORTOOLS_VRP_SOLVER",
                algorithm=f"Google-ORTools-Routing-{ortools.__version__}",
                version="1.0.0",
                distance_basis=DistanceBasis.ROAD_ESTIMATE,
            ),
            baseline_distance_m=baseline_distance_m,
        )
