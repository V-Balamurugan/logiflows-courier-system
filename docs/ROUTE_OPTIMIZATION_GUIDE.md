# LogiFlows Route Optimization & Multi-Stop Dispatch Guide

## 1. Overview and Architecture

The LogiFlows Route Optimization engine provides constraint-aware, multi-stop pickup and delivery optimization for branch operations and logistics hubs. Anchored to a branch depot, the system optimizes delivery sequences, balances vehicle capacities, resolves precedence constraints, monitors live driver telemetry, and exposes real-time Server-Sent Events (SSE).

### 1.1 Normalized Routing Schema Contract (`RoutePlanResult`)

All routing engines and external adapters conform to a unified, immutable Pydantic schema:

```text
RoutePlanResult
 ├── waypoints: List[Waypoint] (ordered stop sequence with ETA and cumulative distance)
 ├── geometry: Optional[List[List[float]]] ([lat, lng] polyline; None if straight-line estimate)
 ├── total_distance_km: float (road distance in km)
 ├── baseline_distance_km: float (distance before optimization in km)
 ├── distance_saved_km: float (savings in km)
 ├── total_duration_min: float (estimated total transit + service duration)
 ├── provider_used: str ("ors" | "osrm" | "local_fallback" | pluggable adapter)
 ├── is_fallback: bool (true if circuit breaker tripped or external API failed)
 ├── fallback_reason: Optional[str]
 ├── warnings: List[str] (capacity, vicinity estimate, time-window warnings)
 ├── steps: List[RouteStep] (turn-by-turn navigation instructions)
 └── coordinate_quality: CoordinateQualitySummary (counts of VERIFIED_GPS, GEOCODED, VICINITY)
```

> [!IMPORTANT]
> **Zero Geometry Fabrication**: If an external provider fails or road geometry cannot be resolved, the engine returns `geometry=None`. The system **never** synthesizes straight chords between stops as false road polylines.

---

## 2. Pluggable Routing Engine & Circuit Breakers

The system features a thread-safe registry supporting multiple simultaneous mapping providers:

```
                  ┌───────────────────────────────┐
                  │    RoutingEngine (Registry)   │
                  └──────────────┬────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
  ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
  │ OpenRouteSvc │        │  OSRM Engine │        │Local Fallback│
  │ (Circuit Brk)│        │ (Circuit Brk)│        │ (Haversine & │
  │              │        │              │        │   Solvers)   │
  └──────────────┘        └──────────────┘        └──────────────┘
```

### 2.1 Circuit Breaker Mechanics
- **Failure Threshold**: 3 consecutive network/provider errors transitions the provider to `OPEN`.
- **Cooldown**: 30-second recovery timeout before entering `HALF_OPEN`.
- **Degradation**: When an external provider trips, requests seamlessly degrade to the local fallback without raising 500 errors to operators.
- **Provider Health Diagnostics**: Available via `GET /api/v1/routes/providers/health`.

---

## 3. Coordinate Provenance & Address Geocoding

### 3.1 Geocoding Hierarchy
1. **Explicit GPS Verification**: Verified physical GPS coordinates (`VERIFIED_GPS`, confidence $\ge 0.95$).
2. **Address Geocoding**: Normalizes address segments (`normalize_address`), queries geocoding cache (LRU + TTL), and computes confidence score ($0.0 - 1.0$).
3. **Branch Vicinity Estimate**: Deterministic pseudo-random jitter around the branch depot ($\pm 0.008^\circ \approx 800\text{m}$) tagged explicitly as `BRANCH_VICINITY_ESTIMATE` with confidence $0.50$ and status `UNVERIFIED`.

### 3.2 Low-Confidence Dispatch Safety Guard (ADR-015)
- Any route containing one or more stops with confidence $< 0.60$ or `BRANCH_VICINITY_ESTIMATE` is automatically flagged with `has_low_confidence_stops = True`.
- **Dispatch Prevention**: `POST /api/v1/routes/{id}/dispatch` rejects automatic dispatch with **HTTP 422 Unprocessable Content**.
- **Manager Override**: An authorized `BRANCH_MANAGER` or `ORG_ADMIN` can override by supplying `low_confidence_override_reason` ($\ge 10$ characters), recorded immutably in the route audit trail.

---

## 4. Constraint-Aware Optimization & Solver Decision Gate

### 4.1 3-Phase Constraint Pipeline
1. **Pre-Validation**: Verifies stop coordinates, vehicle weight ($kg$) and volume ($m^3$) capacities, branch depot reachability, and pairwise pickup-delivery precedence constraints.
2. **Solver Execution**: Runs the selected objective solver with vehicle speed profiling.
3. **Post-Validation**: Guarantees that pickups strictly precede their corresponding deliveries, total vehicle weight never exceeds chassis limits at any point in the tour, and all stops are visited exactly once.

### 4.2 Optimization Objectives
- `FASTEST`: Minimizes total transit time including traffic factors.
- `SHORTEST_DISTANCE`: Minimizes cumulative physical road kilometers.
- `BALANCED`: Balances driving time and delivery density.
- `PRIORITY_FIRST`: Forces express and high-priority consignments into the earliest stops.

### 4.3 Solver Benchmark & Decision Gate (ADR-014)

Benchmark across 10, 25, and 50 stops with precedence constraints:

| Stop Count | Constraints | NearestNeighbor + 2-Opt (ms) | OR-Tools VRP (ms) | Distance Delta | Optimal Choice |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **10 Stops** | Basic TSP | 18.5 ms | 3,102 ms | Identical (18.4 km) | **2-Opt** (168x faster) |
| **25 Stops** | Basic TSP | 78.7 ms | 3,004 ms | Identical (45.2 km) | **2-Opt** (38x faster) |
| **25 Stops** | Precedence (Pickups+Deliveries) | 64.2 ms | 3,150 ms | OR-Tools 27.0% shorter | **OR-Tools** (higher quality) |
| **50 Stops** | Precedence (Pickups+Deliveries) | 182.1 ms | 3,210 ms | OR-Tools 51.7% shorter | **OR-Tools** (vital quality) |

**Decision**:
- $\le 15$ unconstrained stops: Run **NearestNeighbor + 2-Opt** for sub-20ms instant response.
- Precedence constraints or $> 15$ stops: Run **Google OR-Tools VRP** with a 3.0s wall-clock time limit and 2-Opt fallback.

---

## 5. Explainable Driver & Vehicle Allocation Recommendations

Endpoint: `GET /api/v1/routes/{id}/allocation-recommendations`

Calculates ranked, transparent suitability scores ($0 - 100$) for branch personnel and fleet vehicles:
- **Drivers**: Availability (+35), active shift status (+25), low current workload (+25), driving experience (+15). Blocked if assigned to another active dispatch.
- **Vehicles**: Capacity match ratio (+35), vehicle status available (+35), maintenance record clean (+15), optimal vehicle type (+15). Blocked if total route weight exceeds capacity or committed to active linehaul manifest.

---

## 6. Driver GPS Telemetry & Dynamic Recalculation

Endpoint: `POST /api/v1/routes/{id}/telemetry`

- **Freshness Window**: Evaluates GPS age against 15-minute threshold (`is_stale`).
- **Dynamic Recalculation**: Re-estimates ETAs from the driver's live GPS coordinates to all remaining unvisited (`PENDING`, `EN_ROUTE`) stops.
- **Delay Monitoring**: If remaining duration exceeds estimated duration by $> 15$ minutes, an automated `ROUTE_DELAYED` domain event is broadcast.

---

## 7. Platform Integration & Lifecycle Events

### 7.1 Post-Commit Domain Events (SSE)
Endpoint: `GET /api/v1/routes/{id}/events` (Server-Sent Events)

Emits real-time JSON stream post-commit:
- `ROUTE_DISPATCHED`: Dispatched with vehicle and driver IDs.
- `DRIVER_ASSIGNED`: Driver allocation confirmation.
- `ROUTE_STARTED`: Tour commenced; first stop marked `EN_ROUTE`.
- `STOP_COMPLETED`: Delivery/pickup finalized; custody ledger updated.
- `DELIVERY_FAILED`: Consignment failure recorded with cause.
- `ETA_CHANGED`: Dynamic ETAs updated from driver telemetry.
- `ROUTE_DELAYED`: Route experiencing significant transit delay ($> 15\text{ min}$).
- `ROUTE_REOPTIMIZED`: Stops re-ordered and path re-computed.

> [!NOTE]
> All event broadcasts occur **strictly after** the database transaction commit succeeds. Any transaction rollback emits zero events.

### 7.2 Security & Negative Tenant Isolation
- **Tenant Isolation**: An operator in Organization B accessing an Organization A route receives **HTTP 404 Not Found** across all endpoints (`GET`, `dispatch`, `reoptimize`, `telemetry`, `events`).
- **Zero PII Leakage**: Public tracking endpoints omit customer names, phone numbers, and street addresses, returning only city names and milestone timestamps.
- **Fleet Conflict Guards**: Vehicles committed to an active linehaul manifest (`DRAFT`, `SEALED`, `IN_TRANSIT`) are strictly prevented from simultaneous last-mile dispatch (**HTTP 409 Conflict**).
