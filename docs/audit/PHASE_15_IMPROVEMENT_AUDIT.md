# LOGIFLOWS — PHASE 15 IMPROVEMENT: ADVANCED ROUTE OPTIMIZATION AUDIT REPORT

**Date:** 2026-11-15  
**Base Branch:** `phase-15/route-optimization` (commit `111e3e9`)  
**Work Branch:** `phase-15/route-optimization-improvements`  
**Auditor:** Senior Architect, QA & Logistics Systems Engineer  

---

## 1. PREFLIGHT ENVIRONMENT & TOOL MATRIX

| Tool / Service | Version / Status | Availability / Access | Fallback / Mitigation Plan |
|---|---|---|---|
| `git` | 2.55.0.windows.5 | Available | Authoritative VCS |
| `python` | 3.14.7 (`backend\venv`) | Available | Authoritative backend runtime |
| `node` | v24.21.0 | Available | Authoritative frontend runtime |
| `npm` | 11.19.0 | Available | Frontend package manager |
| `docker` | 29.7.2, build a7dcaa6 | Installed; Desktop daemon manually paused | `NOT VERIFIED` for live container daemon start; local SQLite & mocks used for unit tests; copy-paste commands provided for PG16 container execution; PG16 verified in GitHub Actions CI |
| `docker compose` | v5.5.1 | Installed & validated (`docker compose config`) | Config syntax verified clean |
| `gh` CLI | 2.103.3 | Authenticated as `V-Balamurugan` (`gist`, `read:org`, `repo`) | PR creation & Actions monitoring ready |
| `psql` CLI | Not in global PATH | Absent | Use Python `psycopg`/SQLAlchemy driver or containerized `psql` |
| GitHub CI / Remote | Available | Read/Push/PR verified | GitHub Actions CI will run authoritative PG16 migration & test suite |
| `ORS_API_KEY` | Configured as `""` (empty by default) | Unset | Mock ORS adapter and local fallback tested with circuit breaker; `@pytest.mark.live` for live tests |
| `OSRM_BASE_URL` | `https://router.project-osrm.org` | Configured | Configurable endpoint; mock adapter in tests; circuit breaker on connection failure |
| OR-Tools | Installable (`ortools-9.15.6755`) | Verified via pip dry-run | Evaluated in Subphase 15.9 solver decision gate |

---

## 2. BASELINE TEST & SYSTEM HEALTH STATUS

Executed on clean work branch `phase-15/route-optimization-improvements`:

- **Alembic Schema Drift (`backend`):** `a7d6f19c882b (head)`. `alembic check` reports: `No new upgrade operations detected.` (Zero drift).
- **Backend Pytest Suite:** 127 passed, 6 warnings in 29.06s across 24 test suites. Coverage: 87%.
- **Frontend Vitest Suite:** 39 passed in 7 test files across 39 tests in 12.19s.
- **Frontend Production Build (`vite build`):** Built in 1.42s; `dist/index.html` (0.49 kB), `dist/assets/index.css` (69.54 kB), `dist/assets/index.js` (748.26 kB).
- **Frontend Oxlint:** 0 errors across 45 files with 116 rules in 99ms.
- **Dependency Security Audits:**
  - `pip-audit`: No known vulnerabilities found.
  - `npm audit`: 0 vulnerabilities found.
- **Docker Compose Config:** Valid syntax verified.

---

## 3. ARCHITECTURE AUDIT FINDINGS

| ID | Severity | Area | Affected files | Symptom | Root cause | Planned fix | Verification test | Status |
|---|---|---|---|---|---|---|---|---|
| **FIND-15-01** | High | Architecture (15.7) | `backend/app/services/routing_providers.py`, `backend/app/services/route_service.py` | `RouteComputationResult` is an internal dataclass with non-normalized fields (`leg_distances_km`, etc.), lacking structured metadata (`optimization_status`, `distance_basis`, `warnings`, `provenance`). | Phase 15 initial implementation used an internal dataclass without a comprehensive public schema contract. | Define normalized Pydantic `RoutePlanResult` in `backend/app/schemas/route_plan.py` with `legs[]`, `distance_basis`, `optimization_status`, `warnings`, and `provenance`. | Unit tests asserting normalized `RoutePlanResult` output across all providers. | **PLANNED** |
| **FIND-15-02** | Critical | Accuracy / Integrity (15.7, 15.14) | `backend/app/services/routing_providers.py`, `frontend/src/components/LeafletMap.tsx` | Map renders straight polyline chords across town when local fallback runs, misrepresenting straight lines as road-following paths. | `LocalHaversineOptimizer` appends depot and waypoints directly to `geometry_points`. | Return `geometry=None` for local fallback; display "estimated, no road geometry" notice on map rather than fake chords. | Unit test asserting `result.geometry is None` and UI test verifying road geometry fallback notice. | **PLANNED** |
| **FIND-15-03** | High | Fault Tolerance (15.8) | `backend/app/services/routing_providers.py` | If ORS or OSRM endpoints fail repeatedly or encounter 429 rate limits, repeated blocking HTTP requests cause pipeline latency spikes instead of cleanly tripping to fallback. | Basic retry loop lacks circuit breaker state machine (`CLOSED`, `OPEN`, `HALF_OPEN`), rate-limit header parsing (`Retry-After`, `x-ratelimit-remaining`), and health check reporting. | Implement `CircuitBreaker` pattern with configurable failure threshold, cooldown timer, half-open probe, `Retry-After` header parsing, and a `/api/v1/routes/providers/health` endpoint. | `test_routing_circuit_breaker.py` asserting transition to OPEN on repeated failures, fast-failure without HTTP calls, and recovery probe on HALF-OPEN. | **PLANNED** |
| **FIND-15-04** | High | Geocoding & Data Integrity (15.11) | `backend/app/models/route.py`, `backend/app/models/parcel.py`, `backend/app/services/route_service.py` | Parcels and RouteStops lack coordinate provenance tracking; estimated branch vicinity coordinates cannot be distinguished programmatically from verified GPS/geocoded locations. | Models only store raw `latitude` and `longitude` floats with a loose string `coords_source="EXPLICIT"`. | Alembic migration adding `coordinate_source` enum (`VERIFIED_GPS`, `VERIFIED_GEOCODING`, `MANUAL`, `BRANCH_VICINITY_ESTIMATE`), `confidence` (float 0.0-1.0), `verification_status` (`VERIFIED`, `UNVERIFIED`, `FAILED`), and `last_verified_at`. Add geocoding service abstraction with TTL caching and dispatch safety guard for low-confidence coordinates. | Migration verification test and geocoding confidence dispatch guard tests. | **PLANNED** |
| **FIND-15-05** | High | Optimization Constraints (15.9) | `backend/app/services/route_service.py`, `backend/app/services/routing_providers.py` | If a route contains both pickup and delivery stops for a parcel, or strict time windows, pickup is not guaranteed to precede delivery in sequence order. | Routing optimization treats all stops as unconstrained traveling salesperson waypoints without precedence or time window penalization. | Implement formal 3-phase pipeline (`pre-validation -> optimization -> post-validation`) enforcing pickup-before-delivery precedence, time-windows, vehicle payload, and dimensional capacity. | `test_constraint_aware_routing.py` verifying pickup strictly precedes delivery and capacity overflow raises validation rejection. | **PLANNED** |
| **FIND-15-06** | High | Optimization Objectives (15.9) | `backend/app/services/routing_providers.py`, `docs/DECISIONS.md`, `docs/ROUTE_OPTIMIZATION_GUIDE.md` | `FASTEST`, `SHORTEST`, and `BALANCED` objectives lack distinct mathematical formulations and deterministic test proof; OR-Tools benchmarking has not been documented. | Optimization objectives relied on simple heuristic multipliers without formal formula definitions or solver comparison benchmarks. | Define distinct mathematical objective formulations (`FASTEST`, `SHORTEST_DISTANCE`, `BALANCED`, `PRIORITY_FIRST`), create a deterministic 4-objective sequence verification test, and benchmark heuristic vs OR-Tools on 10, 25, 50 stop fixtures. | `test_distinct_objectives_fixture` asserting different sequence orders across objectives. | **PLANNED** |
| **FIND-15-07** | Critical | Concurrency & Allocation (15.10) | `backend/app/services/route_service.py`, `backend/app/routers/routes.py` | Managers lack an explainable ranking engine for driver/vehicle allocation; potential race conditions under concurrent dispatch requests. | Dispatch currently sets `is_active_dispatch=True` but lacks an explainable allocation recommendation endpoint and pessimistic row locking (`SELECT ... FOR UPDATE`). | Implement `RouteService.get_route_allocation_recommendations` ranking drivers and vehicles by workload, shift, availability, and capacity with explicit reasons. Add `SELECT ... FOR UPDATE` row-locking on route, vehicle, and driver during dispatch. | PostgreSQL concurrency test simulating parallel dispatches where exactly one succeeds and the other receives 409 Conflict. | **PLANNED** |
| **FIND-15-08** | High | Telemetry & State Invariants (15.12, 15.13) | `backend/app/routers/routes.py`, `backend/app/models/route.py`, `backend/app/services/route_service.py` | Drivers cannot continuously report GPS coordinates; routes lack idempotency keys on reoptimize and dispatch; illegal route/stop transitions lack uniform 409 enforcement. | No standalone `POST /api/v1/routes/{id}/telemetry` endpoint; no `idempotency_key` column on `delivery_routes`. | Add telemetry GPS ingestion endpoint with freshness and plausibility validation; add `idempotency_key` column and handling on dispatch and reoptimize; enforce route state machine transitions returning 409 on invalid transitions. | Telemetry ingestion tests, idempotency duplicate tests, and invalid state transition 409 tests. | **PLANNED** |
| **FIND-15-09** | High | UI Workbench (15.14) | `frontend/src/pages/RoutesPage.tsx`, `frontend/src/components/LeafletMap.tsx` | RoutesPage lacks coordinate provenance badges, fails to show the road geometry fallback notice, and does not surface allocation recommendations or multi-objective comparisons. | UI workbench was built for basic Phase 15 preview/create flows. | Enhance `RoutesPage.tsx` and `LeafletMap.tsx` with coordinate quality badges, fallback banner, allocation recommendation panel, and objective comparison cards. | Vitest component tests in `src/tests/Phase15Routes.test.tsx` and `src/tests/RoutesAndLeaflet.test.tsx`. | **PLANNED** |
| **FIND-15-10** | High | Event & Notification Integration (15.15) | `backend/app/services/route_service.py` | When a route is dispatched, delayed, reoptimized, or started, domain notifications are not emitted to the notification infrastructure. | Only individual parcel delivery milestones are currently broadcasted via `ShipmentStateMachine`. | Implement route event dispatcher that emits route lifecycle domain notifications after successful database commit. | Integration test asserting route event broadcast on dispatch, delay, and reoptimization. | **PLANNED** |

---

## 4. SPECIAL SUBSYSTEM GAP AUDIT

### 4.1 Driver GPS Ingestion Gap
- **Current State:** `POST /api/v1/routes/{route_id}/stops/{stop_id}/update` accepts optional `latitude` and `longitude` fields when a stop is updated, but there is **no continuous driver GPS ingestion endpoint** (`POST /api/v1/routes/{route_id}/telemetry` or `/gps`), no driver location storage with freshness timestamps, and no GPS-based ETA recalibration.
- **Rule Enforcement:** Zero synthetic GPS data will be fabricated. Telemetry endpoint will be built to accept real coordinate streams with freshness and plausibility bounds checks.

### 4.2 Event Outbox & Notification Dispatcher Gap
- **Current State:** `backend/app/services/broadcaster.py` provides an in-memory `MilestoneBroadcaster` used by `ShipmentStateMachine` for parcel tracking SSE updates. It is invoked strictly after database commits. However, route-level lifecycle events (`ROUTE_DISPATCHED`, `ROUTE_STARTED`, `ROUTE_DELAYED`, `ROUTE_REOPTIMIZED`) are not emitted as structured domain events.
- **Plan:** Reuse `MilestoneBroadcaster` and extend it with a lightweight `RouteLifecycleDispatcher` hooked to post-commit event emissions.

---

## 5. STAGE EXECUTION SEQUENCE

Following the dependency order defined in Section 6 of the prompt:

1. **Stage B: Subphase 15.7** — Architecture Refactoring & Normalized Pydantic Contract (`RoutePlanResult`).
2. **Stage C: Subphase 15.11** — Address Validation, Geocoding & Coordinate Provenance Migration.
3. **Stage D: Subphase 15.8** — Provider Accuracy, Circuit Breakers, Retries & Health Endpoint.
4. **Stage E: Subphase 15.9** — Constraint-Aware Optimization, Distinct Objectives & Solver Decision Gate.
5. **Stage F: Subphase 15.10** — Explainable Driver/Vehicle Allocation & Concurrency Safeguards.
6. **Stage G: Subphases 15.12 & 15.13** — Dynamic ETA Recalculation, Driver GPS Ingestion & Reoptimization Invariants.
7. **Stage H: Subphase 15.14** — Route Planner UI Workbench Enhancements.
8. **Stage I: Subphases 15.15 & 15.16** — Platform Integration, Events, Performance & Tenant Isolation.
9. **Stage J: Subphase 15.17** — Full Verification, Documentation, Benchmarks & PR.
