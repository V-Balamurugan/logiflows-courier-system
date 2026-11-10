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
