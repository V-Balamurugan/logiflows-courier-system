# LogiFlows — Master Development Progress Tracker (Stage 1)

**Last Updated:** November 10, 2026  
**Current Phase:** Phase 13 (COMPLETE & VERIFIED) $\rightarrow$ Phase 14 (READY)  
**Base Branch:** `hardening/phase-11`  
**Active Work Branch:** `phase-13/tracking-custody`  
**Pull Request:** [PR #5: Phase 13 Tracking & QR Custody Operations](https://github.com/V-Balamurugan/logiflows-courier-system/pull/5)  

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
| **Docker Daemon** | WSL2 Engine Verified | Verified | Compose and container services operational |
| **PostgreSQL 16** | Service in CI | Verified in CI | SQLite WAL/StaticPool for local unit tests; PG16 authoritative in CI |
| **Network** | Online | Verified | Package registry and GitHub API reachable |

---

## 2. Phase-by-Phase Roadmap & Status

| Phase | Description | Status | Branch / PR | CI Status |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 11** | System Hardening & Verification | **COMPLETE** | `hardening/phase-11.10-final-verification` / [PR #3](https://github.com/V-Balamurugan/logiflows-courier-system/pull/3) | **PASSED (Green)** |
| **Phase 12** | Core Logistics Business Workflows (12.1–12.7) | **COMPLETE** | `phase-12/core-workflows` / [PR #4](https://github.com/V-Balamurugan/logiflows-courier-system/pull/4) | **MERGED into hardening/phase-11** |
| **Phase 13** | Tracking & QR Custody Operations (13.1–13.6) | **COMPLETE** | `phase-13/tracking-custody` / [PR #5](https://github.com/V-Balamurugan/logiflows-courier-system/pull/5) | **VERIFIED (Ready for Review)** |
| **Phase 14** | Branch-to-Branch Linehaul Transfers & Operations | READY | `phase-14/linehaul-transfers` | Pending Phase 13 merge |
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

## 5. Next Steps for Phase 14

1. Review and merge PR #5 (`phase-13/tracking-custody`) into `hardening/phase-11`.
2. Create branch `phase-14/linehaul-transfers` from verified head.
3. Implement Phase 14: Branch-to-Branch Linehaul Transfers & Operations:
   - Linehaul transfer manifests (creation, seal numbers, vehicle assignment).
   - Manifest dispatch, in-transit state transitions, and arrival receiving scans.
   - Bagging / de-bagging consignment consolidation and reconciliation.
   - Discrepancy reporting (missing or damaged consignments upon inward arrival).


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
