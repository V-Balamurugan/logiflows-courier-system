# LogiFlows Role-Based Access Control (RBAC) Matrix

**Generated Date**: 2026-11-09  
**Specification Version**: Phase 11.10 Hardening  
**Target Roles**:
1. `SUPER_ADMIN`: System-wide administrator across all organizations.
2. `ORG_ADMIN`: Organization-level administrator managing branches, fleet, staff, and policies.
3. `BRANCH_MANAGER`: Branch supervisor managing assignments, local fleet, branch employees, and inventory.
4. `DELIVERY_AGENT`: Mobile field operative handling pickup, transit, and delivery execution.
5. `CUSTOMER`: End-consumer / shipper booking parcels, tracking shipments, and paying invoices.
6. `UNAUTHENTICATED`: Public internet requests with no token credentials.

---

## Access Control Legend

- **ALLOW**: Permitted with full authorization.
- **ALLOW (SCOPED)**: Permitted, strictly filtered to own tenant organization, assigned branch, or owned parcel records.
- **DENY (401)**: Denied; authentication credentials required.
- **DENY (403)**: Denied; authenticated user lacks the required role or privilege.
- **DENY (404)**: Denied; tenant boundary enforcement returns 404 to avoid leaking record existence across organizations.

---

## Comprehensive Endpoint Permissions Matrix

| Endpoint Route | HTTP Method | Public / Unauth | CUSTOMER | DELIVERY_AGENT | BRANCH_MANAGER | ORG_ADMIN | SUPER_ADMIN |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Authentication & Profile** | | | | | | | |
| `/api/v1/auth/register` | `POST` | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW |
| `/api/v1/auth/login` | `POST` | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW |
| `/api/v1/auth/me` | `GET` | DENY (401) | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW |
| `/api/v1/auth/refresh` | `POST` | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW |
| `/api/v1/auth/logout` | `POST` | DENY (401) | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW |
| **Organizations (Multi-Tenant Management)** | | | | | | | |
| `/api/v1/organizations` | `GET` | DENY (401) | DENY (403) | DENY (403) | DENY (403) | DENY (403) | ALLOW |
| `/api/v1/organizations` | `POST` | DENY (401) | DENY (403) | DENY (403) | DENY (403) | DENY (403) | ALLOW |
| **Branches** | | | | | | | |
| `/api/v1/branches` | `GET` | DENY (401) | ALLOW | ALLOW (SCOPED) | ALLOW (SCOPED) | ALLOW (SCOPED) | ALLOW |
| `/api/v1/branches` | `POST` | DENY (401) | DENY (403) | DENY (403) | DENY (403) | ALLOW (SCOPED) | ALLOW |
| `/api/v1/branches/{id}` | `GET` | DENY (401) | ALLOW | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| `/api/v1/branches/{id}` | `PUT` | DENY (401) | DENY (403) | DENY (403) | DENY (403) | ALLOW (SCOPED/404) | ALLOW |
| **Employees & Staff Management** | | | | | | | |
| `/api/v1/employees` | `GET` | DENY (401) | DENY (403) | DENY (403) | ALLOW (SCOPED) | ALLOW (SCOPED) | ALLOW |
| `/api/v1/employees` | `POST` | DENY (401) | DENY (403) | DENY (403) | ALLOW (SCOPED) | ALLOW (SCOPED) | ALLOW |
| `/api/v1/employees/{id}` | `GET` | DENY (401) | DENY (403) | DENY (403) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| `/api/v1/employees/{id}/workload` | `GET` | DENY (401) | DENY (403) | DENY (403) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| **Customers** | | | | | | | |
| `/api/v1/customers` | `GET` | DENY (401) | DENY (403) | ALLOW (STAFF) | ALLOW (STAFF) | ALLOW (STAFF) | ALLOW |
| `/api/v1/customers/{id}` | `GET` | DENY (401) | ALLOW (OWN/404) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| `/api/v1/customers/{id}/parcels` | `GET` | DENY (401) | ALLOW (OWN/404) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| **Vehicles & Fleet** | | | | | | | |
| `/api/v1/vehicles` | `GET` | DENY (401) | DENY (403) | ALLOW (STAFF) | ALLOW (SCOPED) | ALLOW (SCOPED) | ALLOW |
| `/api/v1/vehicles` | `POST` | DENY (401) | DENY (403) | DENY (403) | ALLOW (SCOPED) | ALLOW (SCOPED) | ALLOW |
| `/api/v1/vehicles/{id}` | `GET` | DENY (401) | DENY (403) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| `/api/v1/vehicles/{id}` | `PUT` | DENY (401) | DENY (403) | DENY (403) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| **Parcels & Bookings** | | | | | | | |
| `/api/v1/parcels/quote` | `POST` | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW |
| `/api/v1/parcels` | `POST` | DENY (401) | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW |
| `/api/v1/parcels` | `GET` | DENY (401) | ALLOW (OWN) | ALLOW (SCOPED) | ALLOW (SCOPED) | ALLOW (SCOPED) | ALLOW |
| `/api/v1/parcels/{trk}` | `GET` | DENY (401) | ALLOW (OWN/404) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| `/api/v1/parcels/{trk}/cancel` | `POST` | DENY (401) | ALLOW (OWN/404) | DENY (403) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| `/api/v1/parcels/{trk}/payment` | `POST` | DENY (401) | ALLOW (OWN/404) | DENY (403) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| `/api/v1/parcels/{trk}/status` | `PUT` | DENY (401) | DENY (403) | ALLOW (ASSIGNED/404) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| **Assignments** | | | | | | | |
| `/api/v1/assignments` | `GET` | DENY (401) | DENY (403) | ALLOW (SCOPED) | ALLOW (SCOPED) | ALLOW (SCOPED) | ALLOW |
| `/api/v1/assignments` | `POST` | DENY (401) | DENY (403) | DENY (403) | ALLOW (SCOPED) | ALLOW (SCOPED) | ALLOW |
| `/api/v1/assignments/{id}/status` | `PUT` | DENY (401) | DENY (403) | ALLOW (OWN/404) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| **Custody & QR Scanning** | | | | | | | |
| `/api/v1/custody/scan` | `POST` | DENY (401) | DENY (403) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| `/api/v1/custody/{trk}/history` | `GET` | DENY (401) | DENY (403) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| **Tracking & Location Updates** | | | | | | | |
| `/api/v1/tracking/public/{trk}` | `GET` | ALLOW (REDACTED) | ALLOW (REDACTED) | ALLOW (REDACTED) | ALLOW (REDACTED) | ALLOW (REDACTED) | ALLOW (REDACTED) |
| `/api/v1/tracking/{trk}` | `GET` | DENY (401) | ALLOW (OWN/404) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| `/api/v1/tracking/{trk}/update` | `POST` | DENY (401) | DENY (403) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW (SCOPED/404) | ALLOW |
| **Analytics & Reporting** | | | | | | | |
| `/api/v1/analytics/dashboard` | `GET` | DENY (401) | ALLOW (OWN) | ALLOW (ASSIGNED) | ALLOW (BRANCH) | ALLOW (ORG) | ALLOW (GLOBAL) |
| `/api/v1/analytics/export/csv` | `GET` | DENY (401) | DENY (403) | ALLOW (SCOPED) | ALLOW (SCOPED) | ALLOW (SCOPED) | ALLOW |

---

## Key Security Observations

1. **Existence Leak Prevention**: Any attempt by a tenant to query a branch, vehicle, employee, or parcel outside their organization responds with `404 Not Found` rather than `403 Forbidden`. This preserves privacy and prevents enumeration of competitor entities.
2. **Public Tracking Redaction**: The `/tracking/public/{tracking_number}` endpoint strips all customer identity (names, phone numbers, addresses, pricing, notes), returning exclusively milestone codes, city/branch labels, timestamps, and status descriptions.
3. **Optimistic Locking Guard**: Parcel state transitions verify the `version_id` to prevent lost updates during concurrent operations.
