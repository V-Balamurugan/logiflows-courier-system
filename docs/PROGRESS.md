# LogiFlows — Master Development Progress Tracker (Stage 1)

**Last Updated:** November 14, 2026  
**Current Phase:** Phase 15 (`COMPLETE` — Pending PR Merge) — Dynamic Route Optimization & Map Integration  
**Base Branch:** `hardening/phase-11` (`69e7cf2`)  
**Active Work Branch:** `phase-15/route-optimization`  
**Pull Request:** Pending (`phase-15/route-optimization` $\rightarrow$ `hardening/phase-11`)  

---

## 1. Preflight Inspection Status

| Tool / Check | Version / Result | Availability | Fallback / Mitigation |
| :--- | :--- | :--- | :--- |
| **Git** | 2.55.0.windows.5 | Verified | Native Windows CLI |
| **Node.js** | v24.21.0 | Verified | Node 22 CI target / LTS compatible |
| **npm** | 11.19.0 | Verified | Clean package-lock.json |
| **Python** | 3.14.7 (system), 3.14 (venv) | Verified | Active virtual environment at `backend/venv` |
| **GitHub CLI (gh)** | 2.103.3 | Verified | Full read/write/PR authenticated |
| **Docker CLI** | 29.7.2 | Verified | Compose v5.5.1 syntax validated |
| **Docker Daemon** | Manually paused locally during Phase 14 | Blocked locally | Local Compose syntax validated (`docker compose config -q`); PG16 authoritative verification executed in GitHub Actions `backend-ci` |
| **PostgreSQL 16** | Service in CI | Verified in CI | SQLite WAL/StaticPool for local unit tests; PG16 authoritative in CI |
| **Network** | Online | Verified | Package registry and GitHub API reachable |

---

## 2. Phase-by-Phase Roadmap & Status

| Phase | Description | Status | Branch / PR | CI Status |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 11** | System Hardening & Verification | **COMPLETE** | `hardening/phase-11.10-final-verification` / [PR #3](https://github.com/V-Balamurugan/logiflows-courier-system/pull/3) | **PASSED (Green)** |
| **Phase 12** | Core Logistics Business Workflows (12.1–12.7) | **COMPLETE** | `phase-12/core-workflows` / [PR #4](https://github.com/V-Balamurugan/logiflows-courier-system/pull/4) | **MERGED into hardening/phase-11** |
| **Phase 13** | Tracking & QR Custody Operations (13.1–13.6) | **COMPLETE** | `phase-13/tracking-custody` / [PR #5](https://github.com/V-Balamurugan/logiflows-courier-system/pull/5) | **MERGED into hardening/phase-11** |
| **Phase 14** | Branch-to-Branch Linehaul Transfers & Operations | **COMPLETE** | `phase-14/linehaul-transfers` / [PR #6](https://github.com/V-Balamurugan/logiflows-courier-system/pull/6) | **MERGED into hardening/phase-11** |
| **Phase 15** | Dynamic Route Optimization & Map Integration | **COMPLETE** | `phase-15/route-optimization` | Pending PR |
| **Phase 16** | AI Delay Prediction & Machine Learning | NOT STARTED | — | — |
| **Phase 17** | Real-Time Notifications & n8n Workflows | NOT STARTED | — | — |
| **Phase 18** | Billing, Invoicing & Financial Audits | NOT STARTED | — | — |
| **Phase 19** | Business Intelligence, Analytics & Reporting | NOT STARTED | — | — |
| **Phase 20** | Multi-Courier External API Integration | NOT STARTED | — | — |
| **Phase 21** | Production Deployment, Observability & Release | NOT STARTED | — | — |
| **Phase 17** | Real-Time Notifications & n8n Workflows | NOT STARTED | — | — |
| **Phase 18** | Billing, Invoicing & Financial Audits | NOT STARTED | — | — |
| **Phase 19** | Business Intelligence, Analytics & Reporting | NOT STARTED | — | — |
| **Phase 20** | Multi-Courier External API Integration | NOT STARTED | — | — |
| **Phase 21** | Production Deployment, Observability & Release | NOT STARTED | — | — |

---

## 3. Phase 13 Verified Deliverables & Evidence

### Concrete Evidence Summary (Section 8 Global Phase Gate)

| Gate / Command | Command Executed | Result | Evidence |
| :--- | :--- | :--- | :--- |
| **Alembic Drift** | `alembic check` | **PASSED** | `No new upgrade operations detected.` (Exit code 0, head `f6a7b8c9d0e1`) |
| **Backend Pytest** | `pytest backend/app/tests --cov=app` | **PASSED** | `100 passed in 45.17s; Coverage: 85%` (Target $\ge 80\%$, 2935 statements) |
| **Frontend Vitest** | `npm test -- --run` | **PASSED** | `Test Files: 4 passed; Tests: 26 passed (26)` in 6.27s |
| **Type Check** | `tsc -b` | **PASSED** | Exit code 0, 0 type errors |
| **Frontend Build** | `npm run build` | **PASSED** | `✓ built in 1.12s` (Production bundle generated) |
| **pip-audit** | `pip-audit` | **PASSED** | `No known vulnerabilities found` |
| **npm audit** | `npm audit --audit-level=high` | **PASSED** | `found 0 vulnerabilities` |
| **Playwright E2E** | `npx playwright test` | **PASSED** | `45 passed (2.3m)` across Desktop Chrome (15), Mobile Chrome (15), Tablet (15) |
| **Docker Compose** | `docker compose config -q` | **PASSED** | Exit code 0, valid dependency graph |
| **Oxlint** | `oxlint` | **PASSED** | 0 errors |

---

## 4. Phase 13 Modules & Acceptance Criteria Audit

- [x] **13.1 Public Tracking Endpoint:**
  - `GET /api/v1/tracking/public/{tracking_number}` returns sanitized milestone history in chronological order.
  - Strict zero-PII guarantee: excludes sender/receiver names, phone numbers, email addresses, street addresses, and monetary charges.
  - Returns HTTP 404 with standard error contract on invalid or non-existent tracking code.
- [x] **13.2 Authenticated Tracking Endpoint:**
  - `GET /api/v1/tracking/{tracking_number}` returns complete consignment specifications and full tracking event history.
  - Role-based authorization and strict tenant isolation: consignor customer can view their own consignment; cross-tenant staff and unrelated customers receive HTTP 404 (zero resource enumeration).
- [x] **13.3 GPS Coordinate & Drift Validation:**
  - Strict bounding box validation on latitude ($[-90, 90]$) and longitude ($[-180, 180]$).
  - Explicit rejection of `NaN`, `Inf`, and out-of-bounds coordinates with HTTP 422.
  - Future timestamp drift protection: scans and milestone updates timestamped more than 5 minutes in the future are rejected with HTTP 422.
- [x] **13.4 Cryptographic QR Custody Tokens:**
  - Secure QR code payload format `LFQR.<tracking_number>.<issued_at>.<expires_at>.<nonce>.<signature>` with HMAC-SHA256 signature binding.
  - Tampered signatures or expired QR tokens rejected with HTTP 400 and logged to `custody_scans` with `is_successful=False` for security audit.
- [x] **13.5 Immutable Custody Ledger with Hash Chaining:**
  - Alembic migration `f6a7b8c9d0e1` adds `previous_hash` and `record_hash` (SHA-256) columns.
  - Genesis scan links to `GENESIS_CUSTODY_HASH`; each subsequent scan links deterministically to the preceding scan's hash.
  - Audit endpoint `GET /api/v1/custody/{tracking_number}/verify-chain` verifies unbroken cryptographic continuity and detects database tampering (`tamper_detected=True`, `is_valid=False`).
  - Interactive "Audit Hash Chain" modal integrated in `ParcelDetailPage.tsx` and `QRScannerPage.tsx`.
- [x] **13.6 Real-Time Milestone Streaming via SSE:**
  - `GET /api/v1/tracking/live/{tracking_number}` streaming `text/event-stream` with instant `INITIAL_STATE` event and state machine broadcast integration.
  - Automatic 15-second keep-alive heartbeat comments to prevent proxy drops.
  - Real-time client-side synchronization and pulsing "Live GPS Stream" indicator badge in `PublicTrackingPage.tsx`.

---

## 5. Phase 14 Verified Deliverables & Evidence

### Concrete Evidence Summary (Section 8 Global Phase Gate)

| Gate / Command | Command Executed | Result | Evidence |
| :--- | :--- | :--- | :--- |
| **Alembic Drift** | `Set-Location backend; ..\backend\venv\Scripts\python.exe -m alembic check` | **PASSED** | `No new upgrade operations detected.` (Exit code 0, head `fe12bb91cbb7`) |
| **Backend Pytest** | `.\backend\venv\Scripts\pytest.exe backend/app/tests --cov=app --cov-report=term-missing` | **PASSED** | `106 passed, 4 warnings in 60.60s`; `TOTAL Coverage: 86%` (`4053` stmts, `561` missed; Target $\ge 80\%$) |
| **Frontend Vitest** | `npm --prefix frontend test` | **PASSED** | `Test Files 6 passed (6)`, `Tests 32 passed (32)` in `15.31s` |
| **Oxlint** | `npm --prefix frontend run lint` | **PASSED** | `Found 56 warnings and 0 errors.` (43 files) |
| **Type Check & Build** | `npm --prefix frontend run build` | **PASSED** | `tsc -b && vite build` exited 0 (`2190 modules`, `built in 1.50s`) |
| **Playwright E2E** | `Set-Location frontend; npx playwright test` | **PASSED** | `48 passed (2.4m)` across Desktop Chrome (16), Mobile Chrome (16), Tablet (16) |
| **pip-audit** | `.\backend\venv\Scripts\pip-audit.exe` | **PASSED** | `No known vulnerabilities found` (Exit code 0) |
| **npm audit** | `npm --prefix frontend audit --audit-level=high` | **PASSED** | `found 0 vulnerabilities` (Exit code 0) |
| **Docker Compose** | `docker compose config -q` | **PASSED** | Exit code 0 |
| **GitHub Actions CI (PG16 + E2E)** | [CI Run #43171799190](https://github.com/V-Balamurugan/logiflows-courier-system/actions/runs/43171799190) | **PASSED** | All 6 workflow jobs passed: PG16 `alembic upgrade head` & `check` (0 drift), PG16 Pytest `106 passed` (`90.68%` cov), Frontend CI, Audits, Playwright `48 passed`, CI Gate |

## 6. Phase 14 Modules & Acceptance Criteria Audit

- [x] **14.1 Data Schema & Migration (`fe12bb91cbb7`):**
  - Added `linehaul_manifests`, `consolidation_bags`, `bag_items` (with partial unique index `uq_active_parcel_in_bag`), `linehaul_manifest_items` (with partial unique index `uq_active_parcel_on_manifest`), and `transfer_discrepancies` plus supporting enums (`ManifestStatus`, `BagStatus`, `ManifestItemStatus`, `DiscrepancyType`, `DiscrepancySeverity`, `DiscrepancyStatus`).
- [x] **14.2 Consolidation Bagging & De-Bagging:**
  - Lifecycle `OPEN -> SEALED -> IN_TRANSIT -> RECEIVED -> OPENED_AT_DEST`, branch corridor matching, seal validation, and parcel removal from draft bags.
- [x] **14.3 Linehaul Manifest Lifecycle & Concurrency:**
  - Lifecycle `DRAFT -> SEALED -> IN_TRANSIT -> ARRIVED -> RECONCILED | CANCELLED`.
  - Conditional CAS vehicle locking (`IN_USE`) on dispatch, payload capacity enforcement against sum of parcel weights, `AT_ORIGIN_BRANCH` parcel pre-check, single-transaction commit + post-commit SSE broadcast via `ShipmentStateMachine.transition(..., commit=False)` and `broadcast_milestone(...)`, and full DB rollback on dispatch failure.
- [x] **14.4 Inward Arrival, Reconciliation & Discrepancies:**
  - Arrival scanning (assigned driver or destination branch manager), inward reconciliation (`INTACT` $\rightarrow$ `AT_DESTINATION_BRANCH`, `DAMAGED` / `MISSING` / `SEAL_BROKEN` $\rightarrow$ `ON_HOLD`), excess parcel flagging, and full `TransferDiscrepancy` resolution (`OPEN -> UNDER_INVESTIGATION -> RESOLVED | WRITTEN_OFF`).
- [x] **14.5 Cross-Module Guards & RBAC / Tenant Isolation:**
  - HTTP 409 guards preventing branch deactivation with active manifests (`branch_service.py`), maintenance toggle on vehicles assigned to active manifests (`vehicle_service.py`), and last-mile delivery assignment on parcels attached to active manifests (`assignment_service.py`).
  - Strict tenant isolation returning HTTP 404 across organizations and origin/destination branch scoping documented in `docs/PERMISSIONS.md` and `docs/DECISIONS.md` (`ADR-012`).
- [x] **14.6 Frontend Linehaul UI & Tests:**
  - Built `LinehaulPage.tsx` (Manifests, Consolidation Bags, Discrepancies tabs + responsive `p-4 sm:p-12` empty/loading panels verified on 390px Mobile Chrome + modal workflows), `linehaulApi`, `Badge.tsx`, `Sidebar.tsx`, and `AppRoutes.tsx` (`/linehaul`), covered by `Phase14Linehaul.test.tsx`, `LinehaulPage.test.tsx`, and E2E `Journey 16`.

## 7. Phase 15 Verified Deliverables & Evidence

### Concrete Evidence Summary (Section 8 Global Phase Gate)

| Gate / Command | Command Executed | Result | Evidence |
| :--- | :--- | :--- | :--- |
| **Alembic Drift** | `..\backend\venv\Scripts\python.exe -m alembic check` | **PASSED** | `No new upgrade operations detected.` (Exit code 0, single head `a7d6f19c882b`) |
| **Backend Pytest** | `pytest app/tests --cov=app --cov-report=term-missing` | **PASSED** | `117 passed, 4 warnings in 28.36s; TOTAL Coverage: 90%` (`7838` stmts, `781` miss; Target $\ge 80\%$) |
| **Frontend Vitest** | `npm --prefix frontend test` | **PASSED** | `Test Files 7 passed (7)`, `Tests 39 passed (39)` in `21.47s` |
| **Oxlint** | `npm --prefix frontend run lint` | **PASSED** | `Found 57 warnings and 0 errors.` (45 files) |
| **Type Check & Build** | `npm --prefix frontend run build` | **PASSED** | `tsc -b && vite build` exited 0 (`2191 modules transformed`, `built in 3.61s`) |
| **Playwright E2E** | `Set-Location frontend; npx playwright test` | **PASSED** | `51 passed (2.2m)` across Desktop Chrome (17), Mobile Chrome (17), Tablet (17) |
| **pip-audit** | `.\backend\venv\Scripts\pip-audit.exe` | **PASSED** | `No known vulnerabilities found` (Exit code 0; dnspython $\ge 2.9.2$) |
| **npm audit** | `npm --prefix frontend audit --audit-level=high` | **PASSED** | `found 0 vulnerabilities` (Exit code 0) |
| **Docker Compose** | `docker compose config -q` | **PASSED** | Exit code 0, valid configuration graph |

---

## 8. Phase 15 Modules & Acceptance Criteria Audit

- [x] **15.1 Pluggable Routing Engine & Config:**
  - Implemented abstract `RoutingEngine` adapter pattern with `LocalHaversineOptimizer` (Nearest-Neighbor + 2-opt TSP heuristics with `1.30x` road tortuosity factor, vehicle speed profiles, and `MANUAL` sequence support), `OpenRouteServiceAdapter`, and `OSRMAdapter`.
  - Configured graceful offline degradation: missing keys or rate limits fall back automatically with explicit `is_fallback=True` and `fallback_reason`.
- [x] **15.2 Data Schema & Migration (`a7d6f19c882b`):**
  - Added `delivery_routes` (with `version_id` optimistic locking and partial unique index `uq_active_vehicle_route`), `route_stops` (with partial unique index `uq_active_parcel_on_route`), and nullable `origin_lat/origin_lng/dest_lat/dest_lng` on `parcels`.
  - Supporting enums: `DeliveryRouteStatus`, `RouteStopStatus`, `RouteStopType`, `RouteObjective`, `CoordsSource`.
- [x] **15.3 Route Service, Concurrency & State Machine Sync:**
  - Full CRUD & lifecycle management: `preview_route`, `create_route`, `list_routes`, `get_route`, `reoptimize_route`, `dispatch_route`, `start_route`, `update_stop_status`, and `cancel_route`.
  - Concurrency controls: `version_id` optimistic locking on route mutations returning HTTP 409 `CONFLICT_OPTIMISTIC_LOCK_FAILED`, atomic CAS vehicle locking (`IN_USE`) on dispatch, and multi-stop vehicle retention in `IN_TRANSIT` until all stops reach terminal status.
  - Cross-module conflict guards preventing branch soft-deletion, vehicle maintenance toggles, linehaul packing, and duplicate last-mile assignments on active route entities.
- [x] **15.4 FastAPI Router & Permissions:**
  - Endpoints under `/api/v1/routes`: preview, create, list, detail, reoptimize, dispatch, start, update-stop, and cancel.
  - Role-based scoping: `require_branch_manager_or_higher` for planner/dispatch/cancel actions; `require_staff` for stop execution; strict cross-tenant isolation returning HTTP 404.
- [x] **15.5 Frontend Interactive Map & Planner Workbench:**
  - Enhanced `LeafletMap.tsx`: numbered stop markers with status styling, depot anchor marker, route polyline, and HTML sanitization.
  - Built `RoutesPage.tsx`: split workspace with KPI summary cards, filterable route list, interactive Route Planner with eligible parcel selection, custom GPS waypoints, preview metrics, manual stop reordering, dispatch modal, stop execution modal, and cancel modal.
  - Responsive layout: mobile drawer navigation on viewports below 768px, ensuring full layout usability on 390px mobile viewports.
- [x] **15.6 Verification & E2E Testing:**
  - Unit/integration tests: `test_routing_providers.py` (5 tests), `test_phase15_routes.py` (6 comprehensive test suites covering all edge cases), `RoutesAndLeaflet.test.tsx` (8 tests), `Phase15Routes.test.tsx` (4 tests).
  - Playwright E2E: `Journey 17` verified across Desktop Chrome, Mobile Chrome, and Tablet as part of the 51-test suite.

---

## 9. Next Steps for Phase 16

1. Review and merge Phase 15 PR (`phase-15/route-optimization` $\rightarrow$ `hardening/phase-11`) once user authorizes merge.
2. Create branch `phase-16/delay-prediction` from verified `hardening/phase-11` head.
3. Implement Phase 16: AI Delay Prediction & Machine Learning (feature engineering, scikit-learn pipeline, model inference service, and predictive delay intelligence UI).
