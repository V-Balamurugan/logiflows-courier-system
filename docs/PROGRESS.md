# LogiFlows — Master Development Progress Tracker (Stage 1)

**Last Updated:** November 12, 2026  
**Current Phase:** Phase 14 (COMPLETE & CI VERIFIED) $\rightarrow$ Phase 15 (READY AFTER MERGE)  
**Base Branch:** `hardening/phase-11`  
**Active Work Branch:** `phase-14/linehaul-transfers`  
**Pull Request:** [PR #6: Phase 14 Branch-to-Branch Linehaul Transfers, Consolidation Bags & Reconciliation](https://github.com/V-Balamurugan/logiflows-courier-system/pull/6)  

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
| **Phase 14** | Branch-to-Branch Linehaul Transfers & Operations | **COMPLETE (CI Verified)** | `phase-14/linehaul-transfers` / [PR #6](https://github.com/V-Balamurugan/logiflows-courier-system/pull/6) | **PASSED ([Run #43171799190](https://github.com/V-Balamurugan/logiflows-courier-system/actions/runs/43171799190))** |
| **Phase 15** | Dynamic Route Optimization & Map Integration | NOT STARTED | — | — |
| **Phase 16** | AI Delay Prediction & Machine Learning | NOT STARTED | — | — |
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

## 7. Next Steps for Phase 15

1. Review and merge Phase 14 PR (`phase-14/linehaul-transfers` $\rightarrow$ `hardening/phase-11`) once user authorizes merge.
2. Create branch `phase-15/route-optimization` from verified `hardening/phase-11` head.
3. Implement Phase 15: Dynamic Route Optimization & Map Integration.


---

## 4. Phase 12 Modules & Acceptance Criteria Audit

- [x] **12.1 Organization Management:**
  - `POST /organizations/register`: Atomic organization and initial Org Admin user registration with transactional rollback on conflict.
  - Suspended organization (`is_active=False`) enforces hard 403 lockout at login and token authentication dependencies.
  - Tenant-scoped settings validation and Super Admin status toggling.
- [x] **12.2 Branch Management:**
  - Branch deactivation protection: Soft-deletion blocked with HTTP 409 Conflict if active parcels or assignments exist.
  - Unique branch codes enforced per organization.
  - Branch Manager scoping strictly restricts views to their assigned branch.
  - Real-time Branch Sorting Hub metrics (`GET /branches/{id}/dashboard`).
- [x] **12.3 Employee Management:**
  - Cryptographic single-use invite tokens (`POST /employees/{id}/invite`, `POST /employees/accept-invite`) with automatic `jti` revocation in `revoked_tokens`.
  - Strict privilege ceiling enforcement (`SUPER_ADMIN > ORG_ADMIN > BRANCH_MANAGER > DELIVERY_AGENT > CUSTOMER`).
  - Deactivated staff (`is_active=False`) immediately locked out of all authenticated endpoints.
  - Employee workload and assignment analytics (`GET /employees/{id}/dashboard`).
- [x] **12.4 Vehicle Management:**
  - Vehicle registration numbers normalized (whitespace/hyphen stripped, uppercase canonical).
  - Maintenance locking (`PATCH /vehicles/{id}/maintenance`): Active dispatches block maintenance state with HTTP 409 Conflict.
  - Payload and volumetric capacity limits enforced with overlapping assignment conflict prevention.
- [x] **12.5 Customer Management:**
  - Public registration (`POST /auth/register`) strictly forbids role or organization injection (`extra="forbid"`), always provisioning `CUSTOMER`.
  - Customer Address Book & Corporate Profile (`GET /customers/me/profile`, `PUT /customers/me/profile`).
- [x] **12.6 Parcel Booking:**
  - Deterministic `Decimal` pricing engine with service type multipliers.
  - Postal code validation format regex `^\d{4,10}$` rejecting malformed inputs with HTTP 422.
  - Prohibited cargo filter in notes rejecting contraband materials with HTTP 422.
  - Physical payload bounds (weight $\le$ 500 kg, dimensions $\le$ 300 cm) and geographic hub serviceability check.
- [x] **12.7 Delivery Assignment:**
  - Atomic double-dispatch prevention under concurrency (`uq_active_parcel_assignment`).
  - Assignment cancellation (`POST /assignments/{id}/cancel`): Restores parcel to hub inventory, vehicle to `AVAILABLE`, and logs audit trail.
  - Explainable dispatch recommendation engine (`GET /assignments/suggestions/{parcel_id}`): Workload utilization scores and vehicle capacity fit.

---

## 5. Next Steps for Phase 13

1. Review and merge PR #4 (`phase-12/core-workflows`) into `hardening/phase-11`.
2. Create branch `phase-13/tracking-custody` from verified head.
3. Implement Phase 13: Tracking & QR Custody Operations (Modules 13.1–13.6).
