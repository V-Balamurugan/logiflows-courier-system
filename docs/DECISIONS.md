# LogiFlows — Architectural Decisions & Assumptions Log

This document records architectural decisions, assumptions, and design patterns adopted across the LogiFlows Courier Management System, maintained in compliance with the **Master Development Prompt (Stage 1)**.

---

## ADR-001: Multi-Tenant Architecture & Resource Leakage Policy

- **Context:** LogiFlows serves multiple logistics organizations with hierarchical branches. A user belonging to Organization A must never view or mutate data belonging to Organization B.
- **Decision:**
  - Every tenant-scoped entity (`Branch`, `Vehicle`, `User`, `Parcel`, `DeliveryAssignment`) contains an `organization_id` foreign key.
  - Queries must filter by `organization_id` at the database layer before applying user filters.
  - **Resource Leakage Policy:** If a user requests an ID belonging to another organization, the API returns HTTP 404 (`Not Found`) rather than HTTP 403 (`Forbidden`) to prevent resource enumeration.
- **Status:** Adopted & Verified (Phase 11).

---

## ADR-002: Concurrency & Double-Dispatch Prevention

- **Context:** High-throughput logistics hubs experience race conditions where two operators might dispatch the same consignment to different delivery agents or vehicles simultaneously.
- **Decision:**
  - Adopted a two-tier concurrency control strategy:
    1. **Optimistic Locking:** Added `version_id` integer column to `parcels` mapped via SQLAlchemy `version_id_col`. Conflicting concurrent status updates raise `StaleDataError` which returns HTTP 409.
    2. **Partial Unique Index:** Created `uq_active_parcel_assignment` on `delivery_assignments(parcel_id) WHERE status IN ('ASSIGNED', 'ACCEPTED', 'IN_TRANSIT')`. The database engine rejects duplicate active dispatches atomically.
- **Status:** Adopted & Verified (Phase 11).

---

## ADR-003: Database Lifecycle & Migration Strategy

- **Context:** Automated `Base.metadata.create_all()` in application startup masks missing migrations, creates schema drift, and risks accidental schema changes in production.
- **Decision:**
  - Removed all `create_all()` calls from the application `lifespan`.
  - Alembic migrations in `backend/alembic/versions/` are the authoritative source of truth for the schema.
  - Initial schema DDL reconstructed with full table definitions and reversible downgrades.
  - In Docker Compose, a one-shot `migration` container runs `alembic upgrade head` before the backend container starts.
  - Database seeding is isolated in `backend/app/cli.py` (`seed-demo`), which strictly refuses to run when `ENVIRONMENT=production`.
- **Status:** Adopted & Verified (Phase 11).

---

## ADR-004: Authentication, Token Rotation & Single-Flight Refresh

- **Context:** JWT authentication requires secure revocation and smooth client-side refresh without race conditions when multiple concurrent requests trigger refresh simultaneously.
- **Decision:**
  - Short-lived access tokens (24 hours in dev, configurable in prod) and refresh tokens (7 days).
  - Refresh token rotation stores revoked tokens in the `revoked_tokens` table.
  - Frontend Axios interceptor implements a single-flight mutex: if a 401 occurs, subsequent requests queue behind a single refresh promise rather than firing multiple duplicate refresh calls.
- **Status:** Adopted & Verified (Phase 11).

---

## ADR-005: Security Hardening & Input Sanitization

- **Context:** Production deployments require defense-in-depth against credential theft, CSV injection, and brute-force denial of service.
- **Decision:**
  - **Fail-Fast Configuration:** `app/core/config.py` raises validation errors on boot in `production` if default secret keys or passwords are used.
  - **Rate Limiting:** Sliding-window rate limiter in `app/middleware/rate_limit.py` protects `/auth/login`, `/auth/register`, `/auth/refresh`, and public tracking.
  - **CSV Formula Sanitization:** Prepend single quote `'` to text fields beginning with `=`, `+`, `-`, `@`, `\t`, `\r` before CSV export.
  - **Nginx Security Headers:** Nginx adds `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, and `Content-Security-Policy`.
- **Status:** Adopted & Verified (Phase 11).

---

## ADR-006: Atomic Multi-Tenant Organization & Admin Registration

- **Context:** Self-service organization onboarding must create both the enterprise organization entity and its initial Organization Administrator atomically. Partial registrations where an organization is created but user creation fails (e.g. duplicate email) leave orphaned tenant records.
- **Decision:**
  - Implemented `POST /organizations/register` with strict transactional rollback: both `Organization` and `User(role=ORG_ADMIN)` records are flushed in a single transaction block. If the admin email or organization code conflicts, the transaction rolls back cleanly without persisting orphaned records.
  - Organization suspension (`is_active=False`) immediately enforces a hard lockout at both login (`auth_service.py`) and token dependency layers (`auth_deps.py`), returning HTTP 403 to prevent any suspended tenant access.
- **Status:** Adopted & Verified (Phase 12).

---

## ADR-007: Cryptographic Single-Use Employee Activation & Instant Session Lockout

- **Context:** Dispersed field logistics workers and branch staff require secure onboarding without transmitting unencrypted static passwords. When an employee is deactivated, their active sessions must be invalidated immediately.
- **Decision:**
  - Employee provisioning utilizes cryptographically signed one-time invite tokens (`token_type="invite"`, 48-hour expiration) generated via `employeeApi.invite`.
  - When the employee consumes the token via `/employees/accept-invite`, their credentials are set and the token's unique identifier (`jti`) is written to `revoked_tokens`, preventing replay attacks.
  - Staff deactivation immediately revokes authentication: `get_current_user` verifies `is_active=True` on each protected request, preventing deactivated staff from performing further operations.
  - Role hierarchy enforces a privilege ceiling: an administrator cannot provision or elevate a user to a role higher than or equal to their own rank (`SUPER_ADMIN > ORG_ADMIN > BRANCH_MANAGER > DELIVERY_AGENT > CUSTOMER`).
- **Status:** Adopted & Verified (Phase 12).

---

## ADR-008: Explainable Dispatch Workload Engine & Fleet Capacity Allocation

- **Context:** Branch dispatchers require data-driven intelligence when assigning parcels to delivery agents and vehicles to prevent delivery agent overload and vehicle capacity violations.
- **Decision:**
  - Implemented `get_dispatch_suggestions(parcel_id)` returning an explainable recommendation model:
    - **Delivery Agent Ranking:** Evaluates current active assignments against agent maximum capacity ($10$ concurrent runs) to generate an explainable score with utilization percentages.
    - **Fleet Payload Fit:** Validates parcel weight and volumetric dimensions against stationed available vehicles, providing an explicit capacity fit boolean and spare capacity explanation.
    - **Zero Parcel Drop:** If an assignment is cancelled, `cancel_assignment` restores the parcel state to hub inventory, restores vehicle status to `AVAILABLE`, and records a structured audit event.
- **Status:** Adopted & Verified (Phase 12).

---

## ADR-009: Strict Cargo & Postal Code Integrity Safeguards

- **Context:** Logistics operations must reject prohibited contraband cargo, malformed postal codes, and unserviceable hub routes at booking time.
- **Decision:**
  - **Postal Code Validation:** Enforced regex `^\d{4,10}$` rejecting alphanumeric or malformed pincodes with HTTP 422.
  - **Prohibited Cargo Filter:** Keyword scan in parcel notes rejecting contraband materials (`explosives`, `firearms`, `hazardous`, `contraband`, `biohazard`, `flammable`, `radioactive`, `weapons`) with HTTP 422.
  - **Physical Payload Bounds:** Capped maximum single consignment weight at 500 kg and dimensions at 300 cm.
  - **Hub Serviceability:** Validates that origin and destination hubs belong to the same multi-tenant organization and possess valid, non-null geographic coordinates within standard finite bounds ($[-90, 90]$ latitude, $[-180, 180]$ longitude).
- **Status:** Adopted & Verified (Phase 12).

---

## ADR-010: Tamper-Evident Hash-Chained Custody Ledger

- **Context:** Consignment custody transfers across linehaul hubs, delivery vehicles, and agents require cryptographic immutability so that database modifications, altered scan types, or forged timestamps can be detected deterministically.
- **Decision:**
  - Added `previous_hash` (VARCHAR 64) and `record_hash` (VARCHAR 64) columns to `custody_scans` table via Alembic migration `f6a7b8c9d0e1`.
  - For each successful scan, `record_hash` is computed as the SHA-256 digest of:
    `f"{prev_hash}:{parcel.id}:{scan_type.value}:{scanned_by_id}:{branch_id}:{iso_timestamp}"`.
  - The first scan for any parcel binds to `GENESIS_CUSTODY_HASH`. Subsequent scans link strictly to the preceding successful scan's `record_hash`.
  - Added `GET /api/v1/custody/{tracking_number}/verify-chain` which recomputes hashes across the sequence: any direct DB modification or broken link sets `tamper_detected=True`, `is_valid=False`.
  - Failed scan attempts (tampered signatures, expired QR codes, unauthorized role transitions) are recorded in `custody_scans` for security auditing with `is_successful=False`, but do not advance the chain, preserving audit history while keeping the valid chain unbroken.
- **Status:** Adopted & Verified (Phase 13).

---

## ADR-011: Server-Sent Events (SSE) Real-Time Milestone Streaming

- **Context:** Shippers, consignees, and hub staff require real-time tracking updates as parcels transition between physical checkpoints without high-frequency polling.
- **Decision:**
  - Implemented `MilestoneBroadcaster` pub/sub service with in-memory subscriber queues per tracking number.
  - Linked `ShipmentStateMachine.transition` to automatically broadcast milestone events upon state mutation.
  - Provided `GET /api/v1/tracking/live/{tracking_number}` endpoint returning `text/event-stream`:
    - Immediately pushes an `INITIAL_STATE` event containing current parcel status and location.
    - Emits live milestone payloads as state transitions occur.
    - Yields periodic `: keep-alive\n\n` comments every 15 seconds to prevent proxy or browser timeouts.
    - Automatically cleans up listener queues when client disconnects.
  - Frontend `PublicTrackingPage` establishes an `EventSource` connection to update checkpoints and display an active "Live GPS Stream" status indicator.
- **Status:** Adopted & Verified (Phase 13).

---

## ADR-012: Atomic Branch-to-Branch Linehaul Manifests, Consolidation Bags & Reconciliation

- **Context:** Inter-branch transfers move multiple parcels and sealed consolidation bags across fleet vehicles, creating risks of double-dispatching vehicles, conflicting last-mile delivery assignments, inconsistent parcel states on partial failure, and unrecorded inward shortages or damages.
- **Decision:**
  - Introduced `linehaul_manifests`, `consolidation_bags`, `bag_items`, `linehaul_manifest_items`, and `transfer_discrepancies` via Alembic migration `fe12bb91cbb7`.
  - Enforced partial unique indexes (`uq_active_parcel_in_bag`, `uq_active_parcel_on_manifest`) so a parcel cannot concurrently reside in two active bags or two active manifests, and blocked last-mile `DeliveryAssignment` creation while a parcel is actively on a linehaul manifest.
  - Added optional `commit: bool = True` to `ShipmentStateMachine.transition(...)` so `LinehaulService.dispatch_manifest` and `LinehaulService.reconcile_manifest` transition all manifest parcels, lock/release the fleet vehicle via conditional CAS `UPDATE`, update bag statuses, and append discrepancy records inside a single ACID transaction, broadcasting SSE milestones only after commit succeeds.
  - Destination inward reconciliation strictly verifies expected tracking numbers, marks damaged/missing items as `ParcelStatus.ON_HOLD`, creates `TransferDiscrepancy` records (including `EXCESS` and `SEAL_BROKEN`), and supports audited discrepancy resolution with optional destination hold release.
- **Status:** Adopted & Verified (Phase 14).

---

## ADR-013: Pluggable Routing Provider Adapter, 2-Opt Local Optimizer & Multi-Stop Delivery Routes

- **Context:** Phase 15 introduces dynamic multi-stop route optimization and Leaflet map integration. External routing providers (OpenRouteService, OSRM) require outbound network access or optional API keys and must degrade gracefully without breaking branch dispatch when offline, rate-limited, or unconfigured.
- **Decision:**
  - Defined an abstract routing provider adapter interface (`RoutingEngine` in `backend/app/services/routing_providers.py`) supporting:
    1. `OpenRouteServiceAdapter` (optional env `ORS_API_KEY`, configurable `ORS_BASE_URL`, timeouts and exponential-backoff retries).
    2. `OSRMAdapter` (configurable `OSRM_BASE_URL`, public/self-hosted OSRM Trip & Route APIs).
    3. `LocalHaversineOptimizer` (Nearest-Neighbor + 2-opt TSP refinement over Haversine distances with road tortuosity factor `1.30x` and `VehicleType` speed profiles, plus `MANUAL` sequence evaluation).
  - Configured requests default to graceful degradation: missing API keys, network timeouts, or HTTP 429/5xx failures automatically fall back to `LocalHaversineOptimizer` while explicitly returning `is_fallback=True` and `fallback_reason` (never silently fabricating external responses).
  - Added persisted `DeliveryRoute` (`version_id` optimistic locking + partial unique index `uq_active_vehicle_route`) and `RouteStop` (partial unique index `uq_active_parcel_on_route`), plus optional origin/destination coordinate fields on `Parcel`. Stops without explicit coordinates disclose `coords_source="BRANCH_VICINITY_ESTIMATE"` transparently.
  - Added cross-module conflict guards across `BranchService`, `VehicleService`, `LinehaulService`, and atomic dispatch synchronization with `DeliveryAssignment` and `ShipmentStateMachine`.
- **Status:** Adopted & Verified (Phase 15).


