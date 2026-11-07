# Phase 11 Audit & Stabilization Tracker

**Repository:** `https://github.com/V-Balamurugan/logiflows-courier-system`  
**Working Branch:** `hardening/phase-11`  
**Current Phase:** Sub-Phase 11.2 (Shipment State Machine & Concurrency)

---

## 1. Sub-Phase Progress Summary

| Sub-Phase | Title | Status | Completion Date | Evidence / Key Artifacts |
|---|---|---|---|---|
| **11.0** | Repository Audit (Read-Only) | **COMPLETE** | 2026-11-04 | Stack audit, 38-endpoint inventory, 13 defects cataloged, 15/15 Pytest passed |
| **11.1** | Security & Tenant Isolation | **COMPLETE** | 2026-11-04 | Tenant scoping across all services, 404 anti-leakage, JWT revocation store & rotation, fail-fast production config, `docs/PERMISSIONS.md` |
| **11.2** | State Machine & Concurrency | **COMPLETE** | 2026-11-04 | Centralized `ShipmentStateMachine`, optimistic locking (`version_id`), signed QR custody, atomic tracking events, `docs/SHIPMENT_STATE_MACHINE.md` |
| **11.3** | Pricing & Quotation Engine | **COMPLETE** | 2026-11-07 | Decimal pricing engine, bounds & NaN validation, bounded collision retry, explicit payment state machine, payment verification endpoint |
| **11.4** | Assignments & Operations | *Pending* | - | Scheduled |
| **11.5** | Real-Time Tracking & Maps | *Pending* | - | Scheduled |
| **11.6** | Frontend Polish & React 19 UI | *Pending* | - | Scheduled |
| **11.7** | End-to-End Integration Testing | *Pending* | - | Scheduled |
| **11.8** | Docker, N8N & Production Hardening | *Pending* | - | Scheduled |
| **11.9** | Final Verification & Readiness | *Pending* | - | Scheduled |

---

## 2. Defect Resolution Matrix

| Defect ID | Severity | Description | Sub-Phase | Status | Resolution Detail |
|---|---|---|---|---|---|
| **DEF-C1** | Critical | Cross-tenant data leakage on branches, parcels, vehicles, employees, assignments, custody history, and analytics export. | 11.1 | **RESOLVED** | Implemented reusable tenant scoping; cross-tenant requests return 404 Not Found to prevent existence enumeration. |
| **DEF-H2** | High | Hardcoded secret fallbacks and lack of fail-fast validation in production. | 11.1 | **RESOLVED** | Added Pydantic `model_validator` in `Settings` that enforces non-default minimum 32-char SECRET_KEY, PostgreSQL URL, and non-wildcard CORS in production. |
| **DEF-H3** | High | Missing JWT revocation store and refresh token single-use rotation. | 11.1 | **RESOLVED** | Added `RevokedToken` model and Alembic migration `a1b2c3d4e5f6`, added `jti` to all JWTs, implemented `POST /api/v1/auth/logout`, and enforced single-use refresh token rotation. |
| **DEF-C2** | Critical | Race conditions in parcel status transitions without optimistic locking. | 11.2 | **RESOLVED** | Implemented `ShipmentStateMachine` with optimistic locking (`version_id`), atomic conditional SQL updates, and 409 Conflict handling. |
| **DEF-C3** | Critical | Non-atomic assignment workflows and rollback vulnerability. | 11.4 | *Deferred to 11.4* | Transaction atomicity and unit of work patterns. |
| **DEF-H1** | High | Missing rate limiting on authentication routes (login/register). | 11.8 | *Deferred to 11.8* | SlowAPI / Redis rate limiting. |
| **DEF-H4** | High | Lack of geofence and coordinate validation on GPS scans. | 11.5 | *Deferred to 11.5* | Haversine distance and coordinate bounds checking. |
| **DEF-M1** | Medium | Absence of pagination on parcel, employee, and vehicle lists. | 11.4 | *Deferred to 11.4* | Standardized pagination parameters `limit` and `offset`. |
| **DEF-M2** | Medium | Incomplete customer isolation on booking and cancelation. | 11.1 | **RESOLVED** | Customers strictly restricted to `customer_id == current_user.id`; returns 404 on others' parcels. |
| **DEF-M3** | Medium | Hardcoded default superadmin credentials in repository. | 11.1 | **RESOLVED** | Initial credentials isolated to `.env.example` templates; production checks prevent insecure defaults. |
| **DEF-M4** | Medium | Frontend type-checking bypass via loose tsconfig options. | 11.6 | *Deferred to 11.6* | Frontend strict type-checking and cleanup. |
| **DEF-L1** | Low | QR generation memory overhead without streaming. | 11.5 | *Deferred to 11.5* | SVG/Base64 streaming response optimization. |
| **DEF-L2** | Low | Missing structured JSON logging for audit trails. | 11.8 | *Deferred to 11.8* | Structlog / JSON formatter middleware. |

---

## 3. Sub-Phase 11.1 Acceptance Criteria Verification

- [x] **AC1: Tenant Isolation:** All queries filter by `organization_id` or `customer_id`. Cross-tenant requests return 404.
- [x] **AC2: Role & Branch Permissions:** Documented in `docs/PERMISSIONS.md` across all 5 roles.
- [x] **AC3: Ownership Validation:** Updates and deletes verify ownership and return 404 for unowned entities.
- [x] **AC4: JWT Hardening:** Added `jti`, `RevokedToken` table, rotation on refresh, and `/auth/logout`.
- [x] **AC5: Secrets Hardening:** Production environment fails fast on default or weak `SECRET_KEY`.
- [x] **AC6: Database Config:** Production requires PostgreSQL; SQLite triggers startup failure.
- [x] **AC7: Strict CORS:** CORS origins validated and non-wildcard in production.
- [x] **AC8: Documentation:** Created `docs/PERMISSIONS.md` and `docs/PHASE_11_TRACKER.md`.
- [x] **AC9: Test Suite:** Full suite covering cross-tenant denial (404), JWT lifecycle, and config validation.

---

## 4. Sub-Phase 11.2 Acceptance Criteria Verification

- [x] **AC1: Centralized Service:** Every status write in the codebase routes through `ShipmentStateMachine`. Direct status assignments eliminated.
- [x] **AC2: Transition Matrix:** Parametrized test covers full from/to matrix: every allowed pair succeeds, disallowed pairs fail with 400.
- [x] **AC3: Concurrency & 409 Conflict:** Optimistic locking via `version_id` produces exactly 1 success and 1 HTTP 409 Conflict on simultaneous updates.
- [x] **AC4: Tracking Immutability:** Tracking events cannot be updated or deleted via services/APIs; strictly append-only.
- [x] **AC5: QR Security & Custody Audit:** Cryptographically signed tokens (`LFQR.*`); malformed, expired, cross-tenant, and invalid scans rejected and logged in `custody_scans`.
- [x] **AC6: Transaction Atomicity:** State transition and tracking event created atomically in the same database transaction; rollback on failure creates none.



---

## 6. Sub-Phase 11.3 Acceptance Criteria Verification

- [x] **AC1: Cross-Organization Branch Denial:** Origin and Destination branches must belong to the same operating organization; cross-org branch combinations rejected with 400.
- [x] **AC2: Numeric, Range & NaN Validation:** `weight_kg` (0.01 - 1000.0 kg), dimensions (1.0 - 500.0 cm); negative, zero, oversized, NaN, and Inf values rejected with 422 field-level errors.
- [x] **AC3: Bounded Unique Tracking Number Generation:** Cryptographically random generation (`secrets.randbelow`) with database uniqueness check and bounded retry loop (`max_retries=5`); collision retry verified via unit test.
- [x] **AC4: Verified Payment State Machine:** Shipments initialize with `PaymentStatus.PENDING`. Payments verified via `POST /api/v1/parcels/{tracking_number}/payment` with amount validation and audit metadata; illegal transitions rejected.
- [x] **AC5: Shipment Cancellation Protections:** Cancelling shipped (`IN_TRANSIT`) or `DELIVERED` parcels fails with 400; unauthorized user/cross-customer cancellation fails with 404 anti-leakage.
- [x] **AC6: Decimal Precision Pricing Engine:** Exact calculations for all service types (`STANDARD`, `EXPRESS`, `OVERNIGHT`, `SAME_DAY`), volumetric divisor (5000), 18% GST tax, and rounding verified via fixed test benchmarks.


---

## 7. Sub-Phase 11.4 Acceptance Criteria Verification

- [x] **AC1: Concurrent & Active Parcel Assignment Double-Booking Prevention:** Partial unique index `uq_active_parcel_assignment` on `delivery_assignments(parcel_id)` for `status IN ('ASSIGNED', 'IN_PROGRESS')`. Attempting to assign an already actively assigned parcel is rejected with HTTP 409 Conflict.
- [x] **AC2: Vehicle Double-Booking & Status Control:** Vehicles must be in `AVAILABLE` status with 0 active assignments to be assigned. Attempting to assign an already-assigned vehicle returns HTTP 409 Conflict.
- [x] **AC3: Vehicle Payload Capacity Validation:** Decimal validation confirms `parcel.weight_kg <= vehicle.max_weight_kg` and volumetric parcel cube <= vehicle volumetric limit. Overcapacity assignments rejected with HTTP 400 Bad Request.
- [x] **AC4: Delivery Agent Workload Capping:** Maximum concurrent active assignments for an agent capped at 10. Exceeding workload returns HTTP 409 Conflict.
- [x] **AC5: Atomic State Synchronization:** Creating an assignment atomically transitions vehicle status to `ASSIGNED` and parcel status via `ShipmentStateMachine`. Completing/failing an assignment atomically updates assignment, releases vehicle to `AVAILABLE`, and advances parcel state to `DELIVERED` / `DELIVERY_FAILED`.
- [x] **AC6: Tenant & Role Authorization:** Only `SUPER_ADMIN`, `ORG_ADMIN`, and branch-scoped `BRANCH_MANAGER` can assign deliveries. Delivery agents or customers attempting assignments receive HTTP 403 Forbidden. Cross-tenant assignments return HTTP 404 Not Found. Mid-transaction failures rollback cleanly.
