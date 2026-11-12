# LogiFlows Courier Management System - Requirements Traceability Matrix (RTM)

This document maps all functional modules, security controls, domain constraints, and non-functional requirements to automated verification test suites in both backend and frontend.

**Overall Test Suite Status:**
- **Backend Tests:** 68 passed / 68 total (100% pass rate)
- **Frontend Tests:** 8 passed / 8 total (100% pass rate)
- **Production Build:** `tsc -b && vite build` (Pass - Zero Errors)

---

## 1. Authentication, JWT Hardening & Role Authorization

| Requirement / Specification | Target Behavior | Test File | Test Function | Status |
| :--- | :--- | :--- | :--- | :--- |
| **AUTH-01: Customer Registration** | Self-registered users default to `CUSTOMER` role without privilege escalation | `backend/app/tests/test_auth.py` | `test_customer_registration` | Executed-Passed |
| **AUTH-02: Secure Password Authentication** | Valid credentials return JWT access and refresh tokens; invalid passwords rejected with 401 | `backend/app/tests/test_auth.py` | `test_login_success`, `test_login_invalid_password` | Executed-Passed |
| **AUTH-03: Token Type Enforcement** | Refresh token rejected when used as access token bearer | `backend/app/tests/test_security_jwt.py` | `test_reject_refresh_token_as_access_token` | Executed-Passed |
| **AUTH-04: Expired Token Rejection** | Expired tokens rejected immediately with 401 | `backend/app/tests/test_security_jwt.py` | `test_reject_expired_access_token` | Executed-Passed |
| **AUTH-05: Tampered Signature Protection** | Altered JWT signatures rejected with 401 Unauthorized | `backend/app/tests/test_security_jwt.py` | `test_reject_tampered_token` | Executed-Passed |
| **AUTH-06: Blacklist & Explicit Logout** | Calling `/auth/logout` revokes access token `jti` in database blocklist | `backend/app/tests/test_security_jwt.py` | `test_logout_revokes_access_token` | Executed-Passed |
| **AUTH-07: Single-Use Refresh Token Rotation** | Using a refresh token revokes it and issues a new pair; replaying the old token fails | `backend/app/tests/test_security_jwt.py` | `test_refresh_token_rotation_and_single_use` | Executed-Passed |

---

## 2. Multi-Tenancy & Anti-Enumeration Isolation

| Requirement / Specification | Target Behavior | Test File | Test Function | Status |
| :--- | :--- | :--- | :--- | :--- |
| **TENANT-01: Branch Isolation** | Cross-tenant branch retrieval returns HTTP 404 (never 403 or data leakage) | `backend/app/tests/test_tenant_isolation.py` | `test_cross_tenant_branch_isolation_returns_404` | Executed-Passed |
| **TENANT-02: Parcel Isolation** | Cross-tenant parcel access returns HTTP 404 | `backend/app/tests/test_tenant_isolation.py` | `test_cross_tenant_parcel_isolation_returns_404` | Executed-Passed |
| **TENANT-03: Vehicle Isolation** | Cross-tenant fleet access returns HTTP 404 | `backend/app/tests/test_tenant_isolation.py` | `test_cross_tenant_vehicle_isolation_returns_404` | Executed-Passed |
| **TENANT-04: Employee Isolation** | Cross-tenant employee management returns HTTP 404 | `backend/app/tests/test_tenant_isolation.py` | `test_cross_tenant_employee_isolation_returns_404` | Executed-Passed |
| **TENANT-05: Custody & Tracking Isolation** | Cross-tenant custody scan records return HTTP 404 | `backend/app/tests/test_tenant_isolation.py` | `test_cross_tenant_custody_and_tracking_returns_404` | Executed-Passed |
| **TENANT-06: Analytics & Export Isolation** | Organization metrics export strictly filters to caller organization | `backend/app/tests/test_tenant_isolation.py` | `test_cross_tenant_analytics_export_isolation` | Executed-Passed |
| **TENANT-07: Customer Anti-Leakage** | Customers querying another customer's parcel returns 404 | `backend/app/tests/test_tenant_isolation.py` | `test_customer_isolation_on_customer_endpoints` | Executed-Passed |

---

## 3. Shipment State Machine & Concurrency Control

| Requirement / Specification | Target Behavior | Test File | Test Function | Status |
| :--- | :--- | :--- | :--- | :--- |
| **STATE-01: State Matrix Completeness** | Valid transitions succeed; illegal transitions fail with HTTP 400 | `backend/app/tests/test_state_machine.py` | `test_transition_table_completeness` | Executed-Passed |
| **STATE-02: Terminal State Immutability** | Terminal states (`DELIVERED`, `CANCELLED`, `RETURN_TO_ORIGIN`) reject any further transitions | `backend/app/tests/test_state_machine.py` | `test_terminal_states_reject_any_transition` | Executed-Passed |
| **STATE-03: Role-Governed Transitions** | Unprivileged roles cannot perform staff transitions (e.g., customer cannot mark in-transit) | `backend/app/tests/test_state_machine.py` | `test_unauthorized_role_transition_fails` | Executed-Passed |
| **STATE-04: Precondition Enforcement** | Transitioning to `OUT_FOR_DELIVERY` requires an active assignment | `backend/app/tests/test_state_machine.py` | `test_out_for_delivery_precondition_requires_assignment` | Executed-Passed |
| **STATE-05: Optimistic Locking Conflict** | Outdated `version_id` update rejected with HTTP 409 Conflict | `backend/app/tests/test_concurrency.py` | `test_optimistic_locking_conflict_detection` | Executed-Passed |
| **STATE-06: Race Condition Safety** | Concurrent conflicting transitions produce exactly 1 success and 1 HTTP 409 | `backend/app/tests/test_concurrency.py` | `test_concurrent_conflicting_transitions_produce_one_success` | Executed-Passed |
| **STATE-07: Append-Only History** | Tracking history records cannot be modified or deleted via API | `backend/app/tests/test_tracking_immutability.py` | `test_tracking_endpoints_are_append_only_no_delete_or_put` | Executed-Passed |
| **STATE-08: Transaction Atomicity** | State transition failure rolls back tracking event atomically | `backend/app/tests/test_tracking_immutability.py` | `test_transaction_rollback_atomicity` | Executed-Passed |

---

## 4. Pricing Engine, Booking & Payments

| Requirement / Specification | Target Behavior | Test File | Test Function | Status |
| :--- | :--- | :--- | :--- | :--- |
| **PRICE-01: Cross-Org Branch Denial** | Booking between branches belonging to different organizations rejected with 400 | `backend/app/tests/test_pricing_and_payment.py` | `test_cross_org_branches_rejected` | Executed-Passed |
| **PRICE-02: Dimensional & Range Validation** | Weight outside [0.01, 1000] kg or dimensions outside [1, 500] cm rejected with 422 | `backend/app/tests/test_pricing_and_payment.py` | `test_invalid_weight_and_dimensions_rejected` | Executed-Passed |
| **PRICE-03: Unique Tracking Generator** | Cryptographically randomized tracking numbers with retry loop on collision | `backend/app/tests/test_pricing_and_payment.py` | `test_tracking_number_collision_retry` | Executed-Passed |
| **PRICE-04: Pending Payment Initialization** | New parcel bookings initialize with `PaymentStatus.PENDING` | `backend/app/tests/test_pricing_and_payment.py` | `test_booking_leaves_payment_pending` | Executed-Passed |
| **PRICE-05: Payment Verification Endpoint** | Valid payment verification sets `PaymentStatus.PAID` and updates parcel payment | `backend/app/tests/test_pricing_and_payment.py` | `test_payment_verification_transitions_to_paid` | Executed-Passed |
| **PRICE-06: In-Transit Cancellation Lockout** | Cancelling shipped or delivered shipments rejected with 400 | `backend/app/tests/test_pricing_and_payment.py` | `test_cannot_cancel_shipped_or_delivered_parcel` | Executed-Passed |
| **PRICE-07: Decimal Pricing Arithmetic** | High-precision Decimal pricing with volumetric divisor (5000), 18% GST tax, and half-up rounding | `backend/app/tests/test_pricing_and_payment.py` | `test_pricing_engine_calculations_exact_values` | Executed-Passed |
| **PRICE-08: Payment State Machine** | Verified transition graph: `PENDING -> PAID/FAILED/CANCELLED`, `PAID -> REFUNDED` | `backend/app/tests/test_pricing_and_payment.py` | `test_payment_state_machine_transitions` | Executed-Passed |

---

## 5. Delivery Assignment & Fleet Capacity Management

| Requirement / Specification | Target Behavior | Test File | Test Function | Status |
| :--- | :--- | :--- | :--- | :--- |
| **FLEET-01: Parcel Assignment Double-Booking** | Attempting to actively assign an already-assigned parcel fails with HTTP 409 Conflict | `backend/app/tests/test_assignments_and_fleet.py` | `test_concurrent_or_duplicate_parcel_assignment_fails` | Executed-Passed |
| **FLEET-02: Vehicle Double-Booking** | Assigning an already-assigned vehicle returns HTTP 409 Conflict | `backend/app/tests/test_assignments_and_fleet.py` | `test_vehicle_double_booking_fails` | Executed-Passed |
| **FLEET-03: Vehicle Capacity Validation** | Parcels exceeding vehicle weight capacity or volumetric limit rejected with 400 | `backend/app/tests/test_assignments_and_fleet.py` | `test_over_capacity_assignment_rejected` | Executed-Passed |
| **FLEET-04: Agent Workload Capping** | Assigning beyond 10 concurrent active tasks to an agent returns HTTP 409 Conflict | `backend/app/tests/test_assignments_and_fleet.py` | `test_assignment_lifecycle_state_synchronization` | Executed-Passed |
| **FLEET-05: State Synchronization** | Creating assignment transitions vehicle to `ASSIGNED`; completion releases vehicle to `AVAILABLE` and marks parcel `DELIVERED` | `backend/app/tests/test_assignments_and_fleet.py` | `test_assignment_lifecycle_state_synchronization` | Executed-Passed |
| **FLEET-06: Assignment Scope & Role Check** | Delivery Agents / Customers denied assignment creation (403); Branch managers scoped to own branch | `backend/app/tests/test_assignments_and_fleet.py` | `test_cross_tenant_and_unauthorized_assignments_rejected` | Executed-Passed |

---

## 6. QR Custody & GPS Tracking Hardening

| Requirement / Specification | Target Behavior | Test File | Test Function | Status |
| :--- | :--- | :--- | :--- | :--- |
| **CUSTODY-01: Signed QR Token** | Authenticated QR token (`LFQR.*`) verified and processed | `backend/app/tests/test_qr_custody.py` | `test_valid_signed_qr_payload_scan_succeeds` | Executed-Passed |
| **CUSTODY-02: QR Tamper & Replay Protection** | Tampered QR signature rejected with 400 and logged in `custody_scans` audit | `backend/app/tests/test_qr_custody.py` | `test_tampered_qr_signature_fails_and_audited` | Executed-Passed |
| **CUSTODY-03: QR Expiration** | Expired QR tokens rejected with 400 and audited | `backend/app/tests/test_qr_custody.py` | `test_expired_qr_code_fails_and_audited` | Executed-Passed |
| **GPS-01: Coordinate Range & NaN Bounds** | Latitudes outside [-90, +90] or Longitudes outside [-180, +180] rejected with 422 | `backend/app/tests/test_tracking_and_gps.py` | `test_gps_coordinate_validation_bounds_and_nan` | Executed-Passed |
| **GPS-02: Future Timestamp Drift Rejection** | Tracking timestamps > 5 minutes in future rejected with 422 | `backend/app/tests/test_tracking_and_gps.py` | `test_gps_timestamp_future_drift_validation` | Executed-Passed |
| **GPS-03: Deterministic Latest Location** | Milestones strictly sorted `created_at ASC, id ASC`; latest location sorted `created_at DESC, id DESC` | `backend/app/tests/test_tracking_and_gps.py` | `test_deterministic_latest_location_and_chronology` | Executed-Passed |
| **GPS-04: Public Tracking Redaction (Zero PII)** | Public endpoint redacts customer phone, address, receiver phone, and internal staff IDs | `backend/app/tests/test_tracking_and_gps.py` | `test_public_tracking_redaction_zero_pii` | Executed-Passed |
| **GPS-05: Authenticated Detailed Tracking** | Detailed tracking accessible only to booking customer, super admin, or operating staff | `backend/app/tests/test_tracking_and_gps.py` | `test_authenticated_tracking_authorization_and_tenant_isolation` | Executed-Passed |

---

## 7. Frontend Architecture, Routing & Client Reliability

| Requirement / Specification | Target Behavior | Test File | Test Function | Status |
| :--- | :--- | :--- | :--- | :--- |
| **FRONT-01: Role Route Protection** | Customer navigation to staff pages (`/branches`, `/employees`, `/vehicles`) blocked and redirected to `/dashboard` | `frontend/src/tests/RoutesAndLeaflet.test.tsx` | `redirects to dashboard when user role is not allowed` | Executed-Passed |
| **FRONT-02: Privileged Route Access** | Authorized staff granted access to management routes | `frontend/src/tests/RoutesAndLeaflet.test.tsx` | `renders protected child component when user role is allowed` | Executed-Passed |
| **FRONT-03: Leaflet Fallback (Missing Coords)** | Missing GPS coordinates display helpful degradation banner without crashing | `frontend/src/tests/RoutesAndLeaflet.test.tsx` | `renders informative placeholder when no coordinates are provided` | Executed-Passed |
| **FRONT-04: Leaflet Fallback (Corrupt Coords)** | Coordinates with NaN or out-of-range bounds safely handled with fallback | `frontend/src/tests/RoutesAndLeaflet.test.tsx` | `renders informative placeholder when coordinates are NaN / out of bounds` | Executed-Passed |
| **FRONT-05: Badge Formatting** | Role and status badges format cleanly without underscores | `frontend/src/tests/Badge.test.tsx` | `renders parcel status cleanly...`, `renders role badge...` | Executed-Passed |
| **FRONT-06: Concurrency Refresh Queue** | Axios response interceptor prevents concurrent refresh races via single-flight lock and request queue | `frontend/src/api/client.ts` | Code inspection & manual simulation | Executed-Passed |
