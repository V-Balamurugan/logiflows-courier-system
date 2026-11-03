# LogiFlows - REST API Specification

All API endpoints are prefixed with `/api/v1` and return JSON. OpenAPI docs interactive UI is available at `/docs` (Swagger) and `/redoc`.

---

## 1. Authentication & Users (`/api/v1/auth`)

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Public | Register new Customer account |
| `POST` | `/api/v1/auth/login` | Public | Authenticate user, returns access & refresh tokens |
| `POST` | `/api/v1/auth/refresh` | Public | Exchange refresh token for fresh access token |
| `GET` | `/api/v1/auth/me` | Authenticated | Retrieve profile details of authenticated user |
| `PUT` | `/api/v1/auth/me` | Authenticated | Update full name, phone number, or preferences |
| `PUT` | `/api/v1/auth/change-password` | Authenticated | Change current password |

---

## 2. Organizations & Branches (`/api/v1/organizations`, `/api/v1/branches`)

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/organizations` | Super Admin | List all organizations |
| `POST` | `/api/v1/organizations` | Super Admin | Create a new organization |
| `GET` | `/api/v1/branches` | Org Staff / Admin | List branches (with filters: city, state, active) |
| `POST` | `/api/v1/branches` | Org Admin | Create a new branch |
| `GET` | `/api/v1/branches/{id}` | Authenticated | Retrieve branch details by ID |
| `PUT` | `/api/v1/branches/{id}` | Org Admin | Update branch information |
| `DELETE`| `/api/v1/branches/{id}` | Org Admin | Soft delete or deactivate branch |

---

## 3. Employee Management (`/api/v1/employees`)

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/employees` | Org Admin / Branch Mgr | List employees (filters: branch, role, status) |
| `POST` | `/api/v1/employees` | Org Admin | Create / onboard new employee with role |
| `GET` | `/api/v1/employees/{id}` | Org Admin / Branch Mgr | Get employee details with active workload |
| `PUT` | `/api/v1/employees/{id}` | Org Admin / Branch Mgr | Update employee branch, role, or active status |
| `GET` | `/api/v1/employees/{id}/workload`| Org Admin / Branch Mgr | View delivery history and current active runs |

---

## 4. Customer Management (`/api/v1/customers`)

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/customers` | Admin / Staff | List registered customers with stats |
| `GET` | `/api/v1/customers/{id}` | Admin / Staff / Self | Customer profile and address book |
| `GET` | `/api/v1/customers/{id}/parcels` | Admin / Staff / Self | Parcel history for specific customer |

---

## 5. Parcel Management & Pricing (`/api/v1/parcels`)

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/parcels/quote` | Public / Auth | Calculate estimated shipping charge |
| `POST` | `/api/v1/parcels` | Customer / Staff | Create a new parcel booking |
| `GET` | `/api/v1/parcels` | Staff / Customer | List parcels (role-filtered, status, date, branch) |
| `GET` | `/api/v1/parcels/{tracking_number}` | Authenticated | Retrieve full parcel details |
| `PUT` | `/api/v1/parcels/{tracking_number}` | Staff | Update parcel details |
| `POST` | `/api/v1/parcels/{tracking_number}/cancel` | Customer / Staff | Cancel eligible booking |
| `GET` | `/api/v1/parcels/{tracking_number}/label` | Authenticated | Download PDF shipping label |

---

## 6. Delivery Assignments (`/api/v1/assignments`)

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/assignments` | Branch Mgr / Admin | Assign parcel to delivery agent & vehicle |
| `GET` | `/api/v1/assignments` | Staff | List delivery assignments |
| `GET` | `/api/v1/assignments/my` | Delivery Agent | List assignments for logged-in agent |
| `PUT` | `/api/v1/assignments/{id}/status` | Staff / Agent | Update assignment status |

---

## 7. Tracking & Custody Scans (`/api/v1/tracking`, `/api/v1/custody`)

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/tracking/public/{tracking_number}` | Public | Public sanitized milestone tracking |
| `POST` | `/api/v1/tracking/{tracking_number}/update` | Staff / Agent | Manual tracking status update |
| `POST` | `/api/v1/custody/scan` | Staff / Agent | Process QR scan with custody validation |
| `GET` | `/api/v1/custody/{tracking_number}/history` | Staff / Admin | Complete chain-of-custody audit logs |

---

## 8. Fleet Management (`/api/v1/vehicles`)

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/vehicles` | Staff | List vehicles with filters (branch, status) |
| `POST` | `/api/v1/vehicles` | Org Admin / Branch Mgr | Register new vehicle |
| `PUT` | `/api/v1/vehicles/{id}` | Org Admin / Branch Mgr | Update vehicle status / maintenance |

---

## 9. Reports & Dashboards (`/api/v1/reports`, `/api/v1/analytics`)

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/analytics/dashboard` | Authenticated | Returns role-specific KPI cards & charts |
| `GET` | `/api/v1/reports/parcels` | Staff / Admin | Filtered parcel report |
| `GET` | `/api/v1/reports/parcels/export` | Staff / Admin | Export parcel report as CSV |

