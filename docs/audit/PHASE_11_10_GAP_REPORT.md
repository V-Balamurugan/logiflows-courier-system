# LogiFlows — Phase 11.10 Gap Analysis & CI Failure Diagnosis Report

**Date:** 2026-11-09  
**Branch:** `hardening/phase-11.10-final-verification` (branched from `hardening/phase-11`)  
**Base Commit:** `7fae988`  
**Report Status:** PREFLIGHT & AUDIT COMPLETE  

---

## 1. Preflight Verification Results

| Tool / Check | Version / State | Verification Command | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Git** | 2.55.0.windows.5 | `git --version` | Available | Clean working tree; branched to `hardening/phase-11.10-final-verification` |
| **Python** | 3.14.7 | `python --version`, `backend/venv/Scripts/python --version` | Available | System & venv available; pytest 9.2 installed |
| **Node.js** | v24.21.0 | `node --version` | Available | Modern runtime available locally |
| **npm** | 11.19.0 | `npm --version` | Available | Dependency installs & scripts operational |
| **GitHub CLI (gh)** | 2.103.3 | `gh --version`, `gh auth status` | Available | Authenticated as `V-Balamurugan`; repo/org/gist scopes active |
| **Docker Engine** | 29.7.2 (Client) | `docker --version`, `docker ps` | Manually Paused | Docker Desktop installed but manually paused by user in Dashboard GUI. Marked `NOT VERIFIED` for local daemon execution per Rule #3; commands provided. |
| **Docker Compose** | v5.5.1 | `docker compose version` | Available | Compose CLI available for syntax & config validation |
| **PostgreSQL CLI (psql)**| N/A (Host PATH) | `psql --version` | Not in PATH | Python `psycopg` driver available for PG connectivity; psql inside container |
| **Network Access** | Active | `npm ping` (PONG 378ms), pip | Verified | Public registries accessible |

---

## 2. GitHub Actions Failure Diagnosis

Real CI Failure logs retrieved via `gh run view 42389767793 --log-failed`:

### 2.1 Backend CI Job (`ID 128454693741`)
- **Failing Step:** `Run Database Migrations` (`alembic upgrade head`)
- **Captured Error Output:**
  ```text
  sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: parcels
  [SQL: ALTER TABLE parcels ADD COLUMN version_id INTEGER DEFAULT '1' NOT NULL]
  ```
- **Diagnosis:** `71e88bd3018e_initial_schema_migration.py` has an empty `upgrade()` body (`pass`). Core tables (`parcels`, `organizations`, `branches`, etc.) were never declared in the initial Alembic migration because the project previously relied on `Base.metadata.create_all()` in `app/main.py`. On an empty database in CI, `a1b2c3d4e5f6` creates `revoked_tokens`, and `b2c3d4e5f6a7` attempts to alter `parcels`, failing immediately with `no such table: parcels`.

### 2.2 Frontend CI Job (`ID 128454693611`)
- **Failing Step:** `Run Component & Route Tests (Vitest)`
- **Captured Error Output:**
  ```text
  npm warn EBADENGINE package: 'undici@8.12.3', required: { node: '>=22.19.0' }, current: { node: 'v20.20.2' }
  Caused by: TypeError: Cannot read properties of undefined (reading 'bind')
      at Object.<anonymous> (node_modules/undici/lib/interceptor/decompress.js:78:30)
  Error: [vitest-pool]: Failed to start forks worker for test files
  ```
- **Diagnosis:** `.github/workflows/ci.yml` specified `node-version: 20`. Vitest 5.1 / jsdom transitive dependency `undici@8.12.3` strictly requires Node >= 22.19.0. Running on Node 20 triggers an unhandled `TypeError` in undici stream decompression binding.

---

## 3. Prioritized Gap Matrix (Tasks 1 – 10)

| ID | Severity | Area | Affected files | Symptom | Root cause | Fix | Verification test | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **GAP-01** | **Critical** | Database / Alembic | `backend/alembic/versions/71e88bd3018e_initial_schema_migration.py`, `backend/app/main.py` | `alembic upgrade head` crashes on fresh database with `no such table: parcels` | Initial Alembic revision contains `pass` instead of DDL for core tables; relied on `create_all()` | Write full initial table schema in `71e88bd3018e` (organizations, branches, users, vehicles, parcels, delivery_assignments, tracking_history, custody_scans). Remove `Base.metadata.create_all()` from production code path | `alembic upgrade head` from empty DB | OPEN |
| **GAP-02** | **High** | CI Pipeline | `.github/workflows/ci.yml` | Vitest crashes in GitHub Actions on Node 20 | Node version 20 violates `undici@8.12.3` requirement (`>=22.19.0`) | Update CI workflow to use `node-version: '22'` | Vitest passes in GitHub Actions runner | OPEN |
| **GAP-03** | **Critical** | Production Security | `backend/app/main.py`, `backend/app/database/init_db.py`, `backend/app/cli.py` | Production app runs DDL `create_all()` and seeds hardcoded demo users/passwords at startup | Seeding and schema creation are embedded in `lifespan` without production gating | Decouple schema creation (Alembic only). Move demo seeding to explicit CLI command `python -m app.cli seed-demo` that refuses to run when `ENVIRONMENT=production` | Startup check in production mode | OPEN |
| **GAP-04** | **High** | Security / Rate Limiting | `backend/app/middleware/rate_limit.py` | `/auth/refresh` and `/tracking/public/{tracking_number}` unthrottled | Middleware only listed `/auth/login` and `/auth/register` | Add refresh and public tracking path patterns to rate limiter | `test_deploy_and_ratelimit.py` | OPEN |
| **GAP-05** | **High** | Security / Data Export | `backend/app/routers/analytics.py` | Cells beginning with `=, +, -, @` exported raw in CSV downloads | Missing CSV formula injection neutralization | Prepend `'` escape to all string values starting with formula trigger characters | Unit test asserting CSV sanitization | OPEN |
| **GAP-06** | **High** | QA / E2E Automation | `e2e/`, `playwright.config.ts`, `package.json` | Zero Playwright end-to-end tests exist | E2E testing deferred from earlier sub-phases | Configure Playwright and implement all 10 user journeys across desktop and mobile viewports | `npx playwright test` | OPEN |
| **GAP-07** | **Medium** | Security Audit | `backend/requirements.txt`, `.github/workflows/ci.yml` | No automated vulnerability scanning for Python dependencies | `pip-audit` missing from build/CI tooling | Add `pip-audit` to requirements and CI security workflow | `pip-audit -r backend/requirements.txt` | OPEN |
| **GAP-08** | **Medium** | DevOps / Compose | `docker-compose.yml`, `.github/workflows/ci.yml` | Compose configuration not validated in automated CI | Missing CI lint step for docker compose | Add `docker compose config` validation to CI pipeline | `docker compose config` | OPEN |
| **GAP-09** | **Medium** | Tenant & RBAC Testing | `backend/app/tests/test_rbac_exhaustive_matrix.py`, `docs/audit/RBAC_MATRIX.md` | Comprehensive negative test coverage for every deny cell in the RBAC matrix needs explicit mapping | Existing tests cover core tenant boundaries, but not every cell of the role-by-endpoint matrix | Produce `docs/audit/RBAC_MATRIX.md` and automated tests proving 403/404 for all deny combinations | `pytest test_rbac_exhaustive_matrix.py` | OPEN |
| **GAP-10** | **Low** | Code Quality | `frontend/src/pages/ParcelDetailPage.tsx`, `frontend/src/components/Badge.tsx` | Oxlint emits 82 warnings on unused imports in frontend | Unused imports leftover from iterative development | Clean unused imports and enforce zero warnings in CI | `npm run lint` | OPEN |

---

## 4. Next Step
Proceed to **Stage B: Tasks 2 & 3** — Fix CI, Database, and Migrations:
1. Complete `71e88bd3018e_initial_schema_migration.py` with full DDL for all core tables.
2. Verify `alembic upgrade head` from empty DB and from migrated DB.
3. Remove `Base.metadata.create_all()` from production startup in `backend/app/main.py`.
4. Fix Node version in `.github/workflows/ci.yml` to Node 22.
