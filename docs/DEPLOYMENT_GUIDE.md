# LogiFlows — Production Deployment & Operations Guide

This guide details the deployment, scaling, security hardening, and database migration lifecycle for the **LogiFlows Courier Management System**.

---

## 1. Architecture & Container Topology

The platform deploys as an isolated multi-tier topology managed via Docker Compose or Kubernetes:

```
                      ┌───────────────────────────────┐
                      │    Nginx Reverse Proxy (80)   │
                      │  (Security Headers, Gzip, SPA)│
                      └──────────────┬────────────────┘
                                     │
                 ┌───────────────────┴───────────────────┐
                 │                                       │
                 ▼                                       ▼
       [Frontend React SPA]                   [FastAPI Backend (8000)]
   Static assets / HTML5 routing          (REST API, Auth, State Machine)
                                                         │
                                    ┌────────────────────┴────────────────────┐
                                    │                                         │
                                    ▼                                         ▼
                        [PostgreSQL 16 (5432)]                       [n8n Workflow (5678)]
                     (ACID, Indexes, Foreign Keys)               (Webhooks, SMTP notifications)
```

### Services Matrix

| Service | Image | User | Ports | Healthcheck |
| :--- | :--- | :--- | :--- | :--- |
| `postgres` | `postgres:16-alpine` | `postgres` | 5432 (internal) | `pg_isready` |
| `migration` | Custom (`backend/Dockerfile`) | `appuser` (1000) | None (one-shot) | Exits 0 on completion |
| `backend` | Custom (`backend/Dockerfile`) | `appuser` (1000) | 8000 | `curl -f /health` |
| `frontend` | Custom (`frontend/Dockerfile`) | `nginx` | 80 $\rightarrow$ 3000, 5173 | `wget --spider /` |
| `n8n` | `docker.n8n.io/n8nio/n8n:latest`| `node` | 5678 | Process check |

---

## 2. Security & Environment Configuration

### Fail-Fast Production Validation

The backend enforces strict fail-fast validation in `app/core/config.py`:
- In `ENVIRONMENT=production`, setting default or weak `SECRET_KEY` (e.g. `<SET_ME>`, `secret`, or strings $< 32$ chars) immediately halts startup.
- In `ENVIRONMENT=production`, default passwords (`SuperAdmin@LogiFlows2026!`) are prohibited.
- `app.cli seed-demo` blocks execution in `production` unless explicitly overridden.

### Mandatory Environment Variables

Create `.env` in the project root based on this template:

```ini
# Environment Mode
ENVIRONMENT=production
PROJECT_NAME="LogiFlows Courier Management System"
API_V1_STR=/api/v1

# Security & JWT (Must be at least 32 characters of high-entropy randomness)
# Generate with: openssl rand -hex 32
SECRET_KEY=<SET_ME_PRODUCTION_SECRET_KEY_MIN_32_CHARS>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=7

# Rate Limiting (Sliding Window IP limiter)
RATE_LIMIT_MAX_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# Database Credentials
POSTGRES_USER=logiflows_admin
POSTGRES_PASSWORD=<SET_ME_STRONG_DATABASE_PASSWORD>
POSTGRES_DB=logiflows_prod_db
DATABASE_URL=postgresql://logiflows_admin:<SET_ME_STRONG_DATABASE_PASSWORD>@postgres:5432/logiflows_prod_db

# CORS Allowed Origins (JSON array or comma-separated)
CORS_ORIGINS=["https://courier.logiflows.com","https://app.logiflows.com"]

# Initial Super Admin (Seeded only if database is completely empty)
FIRST_SUPERADMIN_EMAIL=admin@logiflows.com
FIRST_SUPERADMIN_PASSWORD=<SET_ME_STRONG_SUPERADMIN_PASSWORD>
```

---

## 3. Deployment Lifecycle

### Step 1: Clone Repository & Select Branch
```bash
git clone https://github.com/V-Balamurugan/logiflows-courier-system.git
cd logiflows-courier-system
git checkout hardening/phase-11
```

### Step 2: Validate Docker Compose Configuration
```bash
docker compose config -q
```
*Zero output indicates a valid syntax and dependency graph.*

### Step 3: Deploy Stack
```bash
docker compose up --build -d
```
The startup sequence automatically executes in this order:
1. `postgres` starts and reaches `healthy` state.
2. `migration` one-shot container starts, runs `alembic upgrade head`, and completes successfully.
3. `backend` starts, passes internal `SELECT 1` connectivity check, and serves `/health`.
4. `frontend` starts Nginx with security headers and proxies `/api/` to `backend`.

---

## 4. Database Migrations & Rollback Procedures

### Checking Schema Drift
```bash
# In backend container or virtual environment:
alembic check
```
Output must read:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
No new upgrade operations detected.
```

### Upgrading to Latest Migration
```bash
alembic upgrade head
```

### Rollback (Downgrade) Procedure
Every migration in `backend/alembic/versions/` provides an authoritative `downgrade()` function:
```bash
# Downgrade 1 revision:
alembic downgrade -1

# Downgrade to baseline:
alembic downgrade base
```

---

## 5. Backup & Disaster Recovery

### Automated Database Backup
```bash
# Snapshot live database into compressed SQL dump
docker exec -t logiflows_postgres pg_dump -U logiflows_user -d logiflows_db -F c -b -v -f /var/lib/postgresql/data/backup_$(date +%Y%m%d_%H%M%S).dump
```

### Database Restore Procedure
```bash
# Restore from dump
docker exec -i logiflows_postgres pg_restore -U logiflows_user -d logiflows_db -v -c /var/lib/postgresql/data/backup_YYYYMMDD_HHMMSS.dump
```

---

## 6. Health & Observability

- **Liveness & Readiness:** `GET /health`  
  Validates both FastAPI process health and active PostgreSQL query execution (`SELECT 1`). Returns HTTP 200 `{"status": "healthy", "database": "connected"}` or HTTP 503 `{"status": "degraded"}`.
- **API Documentation:** `GET /docs` (Swagger UI), `GET /redoc` (ReDoc), `GET /api/v1/openapi.json`.
- **Logs Inspection:**
  ```bash
  docker compose logs -f backend
  docker compose logs -f frontend
  docker compose logs -f postgres
  ```
