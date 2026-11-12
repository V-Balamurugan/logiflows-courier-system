# LogiFlows Permissions & Authorization Matrix

This document defines the Role-Based Access Control (RBAC) and Multi-Tenant Isolation architecture implemented in the LogiFlows Courier Management System.

---

## 1. User Roles

| Role | Value | Description |
|---|---|---|
| **Super Admin** | `super_admin` | Global platform administrator. Manages organizations, system configuration, and views global statistics across all tenants. |
| **Organization Admin** | `org_admin` | Tenant administrator. Manages branches, employees, vehicles, and operations strictly within their own organization. |
| **Branch Manager** | `branch_manager` | Branch operational lead. Manages shipments, delivery personnel, and fleet assigned to their specific branch. |
| **Delivery Agent** | `delivery_agent` | Field delivery employee. Updates parcel status, scans QR custody codes, confirms Proof of Delivery (POD). |
| **Customer** | `customer` | Consignor/Consignee. Books shipments, tracks shipments, cancels eligible bookings, views personal shipment history. |

---

## 2. Tenant Isolation Rules

1. **Anti-Leakage Principle (404 on Cross-Tenant Access):**
   - Attempting to view, update, delete, or scan resources belonging to a different organization returns `HTTP 404 Not Found` (never `403 Forbidden` or `200 OK`). This prevents cross-tenant existence enumeration attacks.
2. **Customer Data Scoping:**
   - Customers can only read and manage shipments where `customer_id == current_user.id`. Access to other customers' orders returns `404 Not Found`.
3. **Public Tracking:**
   - `GET /api/v1/tracking/public/{tracking_number}` is unauthenticated and returns sanitized operational milestones without exposing full sender/recipient contact or financial details.
4. **Token Security & Invalidation:**
   - Both access tokens and refresh tokens contain unique cryptographically random `jti` identifiers.
   - Revocation store (`revoked_tokens`) blacklists tokens upon logout, refresh-token rotation (single-use enforcement), and password reset.

---

## 3. Comprehensive Endpoint-by-Role Matrix

| HTTP Method | Endpoint Path | Allowed Roles | Tenant Scoping Rule | Cross-Tenant Response |
|---|---|---|---|---|
| **POST** | `/api/v1/auth/register` | Public | Creates customer profile only | N/A |
| **POST** | `/api/v1/auth/login` | Public | Validates credentials; returns JWT tokens | N/A |
| **POST** | `/api/v1/auth/refresh` | Public (Bearer) | Validates refresh token; rotates and revokes old | `401 Unauthorized` |
| **POST** | `/api/v1/auth/logout` | Authenticated | Revokes access and refresh tokens | `401 Unauthorized` |
| **GET** | `/api/v1/auth/me` | Authenticated | Returns current profile | `401 Unauthorized` |
| **PUT** | `/api/v1/auth/change-password` | Authenticated | Validates old password; revokes active token | `400 Bad Request` |
| **GET** | `/api/v1/organizations` | Super Admin | Global list of organizations | `403 Forbidden` |
| **POST** | `/api/v1/organizations` | Super Admin | Creates new organization | `403 Forbidden` |
| **GET** | `/api/v1/branches` | Authenticated | Scoped to `current_user.organization_id` | Empty list / 404 |
| **POST** | `/api/v1/branches` | Super Admin, Org Admin | Scoped to user's organization | `403 Forbidden` |
| **GET** | `/api/v1/branches/{id}` | Authenticated | Must belong to user's organization | `404 Not Found` |
| **PUT** | `/api/v1/branches/{id}` | Super Admin, Org Admin | Must belong to user's organization | `404 Not Found` |
| **DELETE** | `/api/v1/branches/{id}` | Super Admin, Org Admin | Must belong to user's organization | `404 Not Found` |
| **GET** | `/api/v1/employees` | Branch Manager, Org Admin, Super Admin | Scoped to organization (and branch for Branch Mgr) | Filtered list |
| **POST** | `/api/v1/employees` | Branch Manager, Org Admin, Super Admin | BM can only onboard Delivery Agents for their branch | `403 Forbidden` |
| **GET** | `/api/v1/employees/{id}` | Branch Manager, Org Admin, Super Admin | Must belong to user's organization/branch | `404 Not Found` |
| **PUT** | `/api/v1/employees/{id}` | Branch Manager, Org Admin, Super Admin | Must belong to user's organization/branch | `404 Not Found` |
| **GET** | `/api/v1/employees/{id}/workload` | Branch Manager, Org Admin, Super Admin | Must belong to user's organization/branch | `404 Not Found` |
| **GET** | `/api/v1/customers` | Staff (Super Admin, Org Admin, BM, Agent) | Scoped to customers active in user's organization | Filtered list |
| **GET** | `/api/v1/customers/{id}` | Authenticated | Self (Customer) or Org Staff | `404 Not Found` |
| **GET** | `/api/v1/customers/{id}/parcels` | Authenticated | Self (Customer) or Org Staff (scoped to org) | `404 Not Found` |
| **POST** | `/api/v1/parcels/quote` | Public / All | Pure rate calculator | N/A |
| **POST** | `/api/v1/parcels` | All Roles | Customer creates for self; Staff for their org | `400 Bad Request` |
| **GET** | `/api/v1/parcels` | All Roles | Customer sees own; Staff sees org/branch parcels | Filtered list |
| **GET** | `/api/v1/parcels/{tracking_no}` | All Roles | Customer sees own; Staff sees org parcels | `404 Not Found` |
| **POST** | `/api/v1/parcels/{tracking_no}/cancel` | All Roles | Self or org staff for BOOKED state only | `404 Not Found` / `400` |
| **GET** | `/api/v1/parcels/{tracking_no}/label` | All Roles | Self or org staff only | `404 Not Found` |
| **POST** | `/api/v1/assignments` | Branch Manager, Org Admin, Super Admin | Parcel, agent, and vehicle must belong to tenant | `404 Not Found` |
| **GET** | `/api/v1/assignments` | Staff | Scoped to agent (Agent) or org (Admin/BM) | Filtered list |
| **PUT** | `/api/v1/assignments/{id}/status` | Staff | Agent can only update own; BM/Admin own org | `404 Not Found` |
| **GET** | `/api/v1/vehicles` | Staff | Scoped to organization fleet | Filtered list |
| **POST** | `/api/v1/vehicles` | Branch Manager, Org Admin, Super Admin | Registered under user's organization | `403 Forbidden` |
| **GET** | `/api/v1/vehicles/{id}` | Staff | Must belong to user's organization | `404 Not Found` |
| **PUT** | `/api/v1/vehicles/{id}` | Branch Manager, Org Admin, Super Admin | Must belong to user's organization | `404 Not Found` |
| **GET** | `/api/v1/tracking/public/{tracking_no}` | Public | Sanitized public tracking data | `404 Not Found` |
| **POST** | `/api/v1/tracking/{tracking_no}/update` | Staff | Milestone updates for user's organization parcel | `404 Not Found` |
| **POST** | `/api/v1/custody/scan` | Staff | Scans parcel within staff's organization | `404 Not Found` |
| **GET** | `/api/v1/custody/{tracking_no}/history` | Staff | Audit chain for user's organization parcel | `404 Not Found` |
| **GET** | `/api/v1/analytics/dashboard` | All Roles | Metric cards and charts scoped to role & tenant | Isolated statistics |
| **GET** | `/api/v1/analytics/export/csv` | Staff | Exports parcel rows scoped to organization | Scoped CSV download |
| **POST** | `/api/v1/linehaul/bags` | Branch Manager, Org Admin, Super Admin | BM scoped to `origin_branch_id` in own org | `404 Not Found` / `403` |
| **GET** | `/api/v1/linehaul/bags` | Branch Manager, Org Admin, Super Admin | Scoped to organization (and origin/dest branch for BM) | Filtered list |
| **GET** | `/api/v1/linehaul/bags/{id}` | Branch Manager, Org Admin, Super Admin | Must belong to user's organization/branch | `404 Not Found` |
| **POST** | `/api/v1/linehaul/bags/{id}/parcels` | Branch Manager, Org Admin, Super Admin | Origin branch operator or Org/Super Admin | `404 Not Found` / `403` |
| **DELETE** | `/api/v1/linehaul/bags/{id}/parcels/{parcel_id}` | Branch Manager, Org Admin, Super Admin | Origin branch operator or Org/Super Admin | `404 Not Found` / `403` |
| **POST** | `/api/v1/linehaul/bags/{id}/seal` | Branch Manager, Org Admin, Super Admin | Origin branch operator; non-empty OPEN bag | `404 Not Found` / `403` |
| **POST** | `/api/v1/linehaul/bags/{id}/debag` | Branch Manager, Org Admin, Super Admin | Destination branch operator; RECEIVED bag only | `404 Not Found` / `403` |
| **POST** | `/api/v1/linehaul/manifests` | Branch Manager, Org Admin, Super Admin | BM scoped to `origin_branch_id` in own org | `404 Not Found` / `403` |
| **GET** | `/api/v1/linehaul/manifests` | Staff | Scoped to org (BM: origin/dest branch; Agent: driver_id) | Filtered list |
| **GET** | `/api/v1/linehaul/manifests/{id}` | Staff | Must match org/branch/assigned driver scope | `404 Not Found` |
| **POST** | `/api/v1/linehaul/manifests/{id}/items` | Branch Manager, Org Admin, Super Admin | Origin branch operator; DRAFT manifest | `404 Not Found` / `403` |
| **POST** | `/api/v1/linehaul/manifests/{id}/seal` | Branch Manager, Org Admin, Super Admin | Origin branch operator; non-empty DRAFT manifest | `404 Not Found` / `403` |
| **POST** | `/api/v1/linehaul/manifests/{id}/dispatch` | Branch Manager, Org Admin, Super Admin | Origin branch operator; atomic vehicle CAS lock | `404 Not Found` / `409` |
| **POST** | `/api/v1/linehaul/manifests/{id}/arrive` | Assigned Driver, Dest BM, Org Admin, Super Admin | Assigned `driver_id` or destination branch operator | `404 Not Found` / `403` |
| **POST** | `/api/v1/linehaul/manifests/{id}/reconcile` | Branch Manager, Org Admin, Super Admin | Destination branch operator; inward tally + hold/discrepancies | `404 Not Found` / `403` |
| **POST** | `/api/v1/linehaul/manifests/{id}/cancel` | Branch Manager, Org Admin, Super Admin | Origin branch operator; DRAFT/SEALED only | `404 Not Found` / `409` |
| **GET** | `/api/v1/linehaul/discrepancies` | Branch Manager, Org Admin, Super Admin | Scoped to org (and origin/dest branch for BM) | Filtered list |
| **POST** | `/api/v1/linehaul/discrepancies` | Branch Manager, Org Admin, Super Admin | Manifest within org/branch after dispatch | `404 Not Found` / `409` |
| **PATCH** | `/api/v1/linehaul/discrepancies/{id}` | Branch Manager, Org Admin, Super Admin | Scoped to org/branch; optional hold release to dest | `404 Not Found` |
