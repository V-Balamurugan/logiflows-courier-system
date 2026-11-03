# LogiFlows - Courier Management System
## Master Project Plan & Implementation Roadmap

### 1. Project Overview
LogiFlows is an enterprise-grade, full-stack Courier Management System engineered for logistics organizations, branch managers, delivery personnel, and retail/corporate customers. The system manages the full lifecycle of courier shipments: booking, pricing, parcel dispatch, branch custody, in-transit fleet assignment, QR code scanning for physical custody changes, proof of delivery (POD), public tracking, and real-time operational analytics.

---

### 2. Implementation Methodology & Phased Sequence

Following an Agile iterative methodology, each module is delivered with its database models, schemas, repositories, service layers, REST APIs, unit/integration tests, and frontend React interfaces before advancing to the next:

- **Phase 1: Architecture & Foundation (Core Auth & Org/Branch Management - Module A)**
  - Database engine configuration (SQLAlchemy 2.x, PostgreSQL/SQLite compatibility, Alembic migrations)
  - Security & Authentication (JWT access & refresh tokens, bcrypt, RBAC, tenant isolation)
  - Organizations & Branches (Complete CRUD, geolocation coordinates, branch codes, search & filters)
  - Frontend foundation: Vite + React 18/19, TypeScript, Tailwind CSS, React Router v6, TanStack Query, Axios, AuthContext, Protected Routes, Main Navigation Layout.

- **Phase 2: Employee & Staff Management (Module B)**
  - Employee models, branch assignment, role management (Org Admin, Branch Manager, Delivery Agent)
  - Workload tracking, active deliveries count, employee profile & status
  - Frontend Employee Management directory, modal form, branch assignment dropdown, role badge.

- **Phase 3: Customer Management (Module C)**
  - Customer profile, address book (pickup & delivery defaults), booking history
  - Customer registration & portal interface, profile editing.

- **Phase 4: Parcel Booking & Shipment Pricing Engine (Module D)**
  - Unique tracking number generation (`LF-XXXX-XXXXXX`)
  - Dynamic dimensional weight & volumetric pricing calculation
  - Sender/Receiver validation, pickup & destination addresses, origin/destination branch resolution
  - Booking confirmation & parcel management (eligible cancellations, status guards)
  - Frontend Booking wizard with price calculation preview, address selection, and booking confirmation.

- **Phase 5: Delivery & Fleet Assignment (Module E & Module H)**
  - Vehicle management: CRUD, registration, model, payload capacity, operational status, maintenance
  - Delivery assignment engine: pairing parcels with delivery agents and vehicles
  - Availability validation, conflict prevention, assignment lifecycle (`ASSIGNED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`)
  - Frontend Assignment modal, active assignments table, vehicle fleet dashboard.

- **Phase 6: Shipment Lifecycle, QR Custody & Tracking (Module F & Module G)**
  - Comprehensive status lifecycle: `BOOKED` → `PICKUP_SCHEDULED` → `PICKED_UP` → `AT_ORIGIN_BRANCH` → `IN_TRANSIT` → `AT_DESTINATION_BRANCH` → `OUT_FOR_DELIVERY` → `DELIVERED`
  - Exception states: `DELIVERY_FAILED`, `RETURN_TO_ORIGIN`, `CANCELLED`, `ON_HOLD`
  - Immutable audit tracking history with timestamp, actor, branch, geolocation, notes
  - QR Code generation (data URL & PDF shipping label generation)
  - QR Scanning interface with custody transfer validation (branch verification, staff authorization)
  - Public tracking portal with OpenStreetMap/Leaflet visualization and milestone timeline.

- **Phase 7: Role-Specific Dashboards & Analytics (Module I)**
  - Super Admin Dashboard (system-wide stats, organization health, volume)
  - Org Admin Dashboard (branch KPIs, revenue, active fleet, deliveries)
  - Branch Manager Dashboard (incoming/outgoing parcels, agent assignment, branch inventory)
  - Delivery Agent Dashboard (my assignments, quick scan, delivery attempt / POD upload)
  - Customer Dashboard (active shipments, tracking cards, quick booking)
  - Operational Reports: Date-filtered parcel metrics, delivery success rate, CSV export.

- **Phase 8: End-to-End Testing, Dockerization & Final Polish**
  - Pytest test suite covering Auth, Branches, Employees, Parcels, Assignments, Tracking
  - Vitest + RTL frontend tests
  - Dockerfile for Backend (multi-stage Python 3.12/3.14 slim)
  - Dockerfile for Frontend (Vite build + Nginx alpine)
  - Docker Compose orchestration with PostgreSQL and healthchecks
  - Comprehensive documentation suite.

---

### 3. Acceptance Criteria by Module

#### Core Auth & Module A: Organizations & Branches
- [ ] Users can register as Customer; Admins can invite/create employees.
- [ ] JWT tokens issued with expiration; refresh tokens rotate securely.
- [ ] Role-Based Access Control enforced on backend endpoints.
- [ ] Organizations and Branches can be created, updated, filtered, searched, and soft-deleted.
- [ ] Branch coordinates (lat/lng) validated for map rendering.

#### Module B: Employee Management
- [ ] Organization Admins and Branch Managers can manage employees according to permissions.
- [ ] Employees can be assigned to branches and roles.
- [ ] Active workload counter reflects active delivery assignments.

#### Module C: Customer Management
- [ ] Customers can update profile and manage addresses.
- [ ] Customers view only their own bookings; Admins view organizational customers.

#### Module D: Parcel Booking & Management
- [ ] Auto-generates unique collision-free tracking number.
- [ ] Shipping charges calculated based on weight, dimensions, service speed, and distance/branch tier.
- [ ] Customer can book parcel and receive confirmation.
- [ ] Customers can cancel only `BOOKED` parcels; status transitions strictly guarded.

#### Module E & H: Delivery Assignment & Vehicle Fleet
- [ ] Delivery agents and vehicles assigned to deliveries without conflicts.
- [ ] Vehicles tracked with capacity limits, status (`AVAILABLE`, `IN_TRANSIT`, `MAINTENANCE`).
- [ ] Status updates cascade correctly to parcel status.

#### Module F & G: Tracking & QR Custody
- [ ] Every status change writes an immutable `TrackingHistory` record.
- [ ] Unique QR code generated for every parcel; PDF shipping label exportable.
- [ ] QR code scan validates employee, destination, and custody transition rules before recording.
- [ ] Public tracking endpoint returns sanitized data without customer email/phone.
- [ ] Leaflet.js map displays transit progress between origin branch, checkpoints, and destination.

#### Module I: Dashboards & Reporting
- [ ] 5 distinct role-based dashboard experiences.
- [ ] Filterable reports by date range, branch, status.
- [ ] One-click CSV export of parcel and delivery logs.

