"""Unit tests for Module 15.1 routing provider adapters, 2-opt TSP solver, and graceful fallback."""
import json
import httpx
import pytest

from app.models.enums import VehicleType
from app.services.routing_providers import (
    LocalHaversineOptimizer,
    OpenRouteServiceAdapter,
    OSRMAdapter,
    RoutingEngine,
    Waypoint,
    derive_branch_vicinity_coords,
    haversine_km,
    validate_lat_lng,
)


def test_haversine_and_coord_validation():
    # Mumbai (19.0760, 72.8777) -> Pune (18.5204, 73.8567) ~ 118-120 km straight-line
    dist = haversine_km(19.0760, 72.8777, 18.5204, 73.8567)
    assert 115.0 < dist < 125.0

    with pytest.raises(ValueError, match="out of bounds"):
        validate_lat_lng(95.0, 72.0, "Test")
    with pytest.raises(ValueError, match="out of bounds"):
        validate_lat_lng(19.0, 181.0, "Test")
    with pytest.raises(ValueError, match="finite"):
        validate_lat_lng(float("nan"), 72.0, "Test")


def test_local_two_opt_improves_criss_cross_route():
    # Arrange deliberately suboptimal zigzag order around Mumbai
    depot = (19.0760, 72.8777)
    waypoints = [
        Waypoint(index=0, latitude=19.2000, longitude=72.9700, label="Far North-East"),
        Waypoint(index=1, latitude=19.0800, longitude=72.8800, label="Very Near Hub"),
        Waypoint(index=2, latitude=18.9200, longitude=72.8300, label="South"),
        Waypoint(index=3, latitude=19.1900, longitude=72.9600, label="Next to NE"),
    ]
    manual = LocalHaversineOptimizer.compute_route(
        start=depot, waypoints=waypoints, objective="MANUAL", return_to_hub=True
    )
    optimized = LocalHaversineOptimizer.compute_route(
        start=depot, waypoints=waypoints, objective="SHORTEST", return_to_hub=True
    )

    assert manual.ordered_indices == [0, 1, 2, 3]
    assert optimized.total_distance_km < manual.total_distance_km
    assert optimized.distance_saved_km > 0
    assert optimized.distance_saved_pct > 0
    assert len(optimized.leg_distances_km) == 5  # 4 stops + return to hub
    assert len(optimized.geometry_points) == 6
    assert optimized.provider_used == "local_fallback"


def test_ors_adapter_with_mock_transport_and_retry():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert request.headers["Authorization"] == "fake-ors-key"
        # Simulate transient 503 on first call, then HTTP 200
        if calls["count"] == 1:
            return httpx.Response(503, json={"error": "rate/upstream busy"})
        body = {
            "features": [
                {
                    "geometry": {
                        "coordinates": [
                            [72.8777, 19.0760],
                            [72.8900, 19.0900],
                            [72.9100, 19.1200],
                            [72.8777, 19.0760],
                        ]
                    },
                    "properties": {
                        "segments": [
                            {"distance": 3200.0, "duration": 420.0},
                            {"distance": 4800.0, "duration": 600.0},
                            {"distance": 7100.0, "duration": 900.0},
                        ]
                    },
                }
            ]
        }
        return httpx.Response(200, json=body)

    adapter = OpenRouteServiceAdapter(
        api_key="fake-ors-key",
        max_retries=2,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    )
    waypoints = [
        Waypoint(index=0, latitude=19.0900, longitude=72.8900, label="S1"),
        Waypoint(index=1, latitude=19.1200, longitude=72.9100, label="S2"),
    ]
    res = RoutingEngine.compute_route(
        start=(19.0760, 72.8777),
        waypoints=waypoints,
        vehicle_type=VehicleType.VAN,
        objective="FASTEST",
        provider="openrouteservice",
        return_to_hub=True,
        ors_adapter=adapter,
    )
    assert calls["count"] == 2
    assert res.provider_used == "openrouteservice"
    assert res.is_fallback is False
    assert res.total_distance_km == 15.1
    assert len(res.geometry_points) == 4


def test_osrm_adapter_mock_and_graceful_fallback():
    def ok_handler(request: httpx.Request) -> httpx.Response:
        assert "/trip/v1/driving/" in str(request.url)
        return httpx.Response(
            200,
            json={
                "waypoints": [
                    {"waypoint_index": 0},
                    {"waypoint_index": 2},
                    {"waypoint_index": 1},
                ],
                "trips": [
                    {
                        "geometry": {
                            "coordinates": [
                                [72.8777, 19.0760],
                                [72.9100, 19.1200],
                                [72.8900, 19.0900],
                            ]
                        },
                        "legs": [
                            {"distance": 6000.0, "duration": 600.0},
                            {"distance": 4500.0, "duration": 480.0},
                        ],
                    }
                ],
            },
        )

    adapter = OSRMAdapter(
        transport=httpx.MockTransport(ok_handler),
        sleep_fn=lambda _: None,
    )
    waypoints = [
        Waypoint(index=0, latitude=19.0900, longitude=72.8900, label="S1"),
        Waypoint(index=1, latitude=19.1200, longitude=72.9100, label="S2"),
    ]
    res = RoutingEngine.compute_route(
        start=(19.0760, 72.8777),
        waypoints=waypoints,
        provider="osrm",
        return_to_hub=False,
        osrm_adapter=adapter,
    )
    assert res.provider_used == "osrm"
    assert res.ordered_indices == [1, 0]
    assert res.total_distance_km == 10.5

    # Now test timeout -> graceful degradation to local_fallback
    def fail_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("OSRM read timed out", request=request)

    failing_osrm = OSRMAdapter(
        max_retries=1,
        transport=httpx.MockTransport(fail_handler),
        sleep_fn=lambda _: None,
    )
    degraded = RoutingEngine.compute_route(
        start=(19.0760, 72.8777),
        waypoints=waypoints,
        provider="osrm",
        return_to_hub=True,
        osrm_adapter=failing_osrm,
    )
    assert degraded.provider_used == "local_fallback"
    assert degraded.is_fallback is True
    assert degraded.fallback_reason is not None
    assert "ReadTimeout" in degraded.fallback_reason

    # Missing ORS_API_KEY also degrades cleanly without failing
    no_key_ors = OpenRouteServiceAdapter(api_key="")
    degraded_ors = RoutingEngine.compute_route(
        start=(19.0760, 72.8777),
        waypoints=waypoints,
        provider="openrouteservice",
        ors_adapter=no_key_ors,
    )
    assert degraded_ors.provider_used == "local_fallback"
    assert degraded_ors.is_fallback is True
    assert "ORS_API_KEY" in (degraded_ors.fallback_reason or "")


def test_deterministic_branch_vicinity_coords():
    c1 = derive_branch_vicinity_coords(19.0760, 72.8777, "400069", "LF-2026-001")
    c2 = derive_branch_vicinity_coords(19.0760, 72.8777, "400069", "LF-2026-001")
    c3 = derive_branch_vicinity_coords(19.0760, 72.8777, "400021", "LF-2026-002")
    assert c1 == c2
    assert c1 != c3
    assert -90 <= c1[0] <= 90 and -180 <= c1[1] <= 180
