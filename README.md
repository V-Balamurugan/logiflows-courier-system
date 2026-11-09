# LogiFlows - Enterprise Full-Stack Courier Management System

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%2019%20%2B%20TypeScript-61DAFB?style=flat-square&logo=react)](https://reactjs.org/)
[![Tailwind CSS](https://img.shields.io/badge/Styling-Tailwind%20CSS%20v4-38B2AC?style=flat-square&logo=tailwind-css)](https://tailwindcss.com/)
[![SQLAlchemy](https://img.shields.io/badge/ORM-SQLAlchemy%202.x-D71F00?style=flat-square)](https://www.sqlalchemy.org/)
[![Docker](https://img.shields.io/badge/Deployment-Docker%20Compose-2496ED?style=flat-square&logo=docker)](https://www.docker.com/)

LogiFlows is a production-oriented, full-stack Courier and Logistics Management Platform inspired by modern supply chain systems. Built with clean modular architecture, it powers end-to-end parcel booking, automated volumetric pricing, physical branch management, fleet assignment, QR code chain-of-custody tracking, and real-time interactive OpenStreetMap geo-tracking.

---

## 🚀 Key Features by Module

### 1. Role-Based Access Control (RBAC) & Authentication
- **5 Distinct Roles:** Super Admin, Organization Admin, Branch Manager, Delivery Agent, Customer.
- Cryptographically secure password hashing with Bcrypt ($12$ salt rounds).
- JWT access tokens (1 day) and refresh tokens (7 days) with automated token rotation.
- Pre-seeded 1-click demo login buttons for rapid persona evaluation.

### 2. Organization & Physical Branch Hub Management (Module A)
- Multi-tenant organization isolation.
- Regional hub management: branch codes, physical address, pincode, contact email/phone, operating status (`ACTIVE`, `INACTIVE`, `UNDER_MAINTENANCE`).
- Spatial coordinates (latitude / longitude) for map rendering.

### 3. Staff & Delivery Agent Management (Module B)
- Onboard branch managers, dispatchers, and field delivery agents.
- Real-time active workload counter and completed deliveries count per employee.

### 4. Customer Management (Module C)
- Customer registration portal with company name, GST registration, and default address book.
- Full consignment booking history with individual shipment tracking.

### 5. Consignment Booking & Volumetric Pricing Engine (Module D)
- Unique, collision-free tracking number format (`LF-YYYY-XXXXXX`).
- Dimensional volumetric weight calculation ($L \times W \times H / 5000$).
- Real-time pricing quotation based on chargeable weight, distance, and service speed (`STANDARD`, `EXPRESS`, `OVERNIGHT`, `SAME_DAY`).
- Official 4x6 / Letter PDF Shipping Label generation with QR codes using ReportLab.
- Safe cancellation workflow guarded strictly for `BOOKED` state shipments.

### 6. Delivery Fleet & Assignment Dispatch (Module E & Module H)
- Fleet registry: registration number, vehicle model, type (`BIKE`, `VAN`, `TRUCK`), and payload capacity in kg.
- Conflict-free parcel dispatch pairing parcels with delivery agents and vehicles.
- Status synchronization updating parcel lifecycle and vehicle availability.

### 7. Physical QR Custody & Real-Time Tracking (Module F & Module G)
- Base64 QR code generation per parcel for scanning with handheld scanners or mobile cameras.
- Six verified custody transitions:
  - `PICKUP_VERIFICATION` $\rightarrow$ `PICKED_UP`
  - `ORIGIN_INWARD` $\rightarrow$ `AT_ORIGIN_BRANCH`
  - `HUB_OUTWARD` $\rightarrow$ `IN_TRANSIT`
  - `DEST_INWARD` $\rightarrow$ `AT_DESTINATION_BRANCH`
  - `OUT_FOR_DELIVERY` $\rightarrow$ `OUT_FOR_DELIVERY`
  - `DELIVERY_CONFIRMATION` $\rightarrow$ `DELIVERED`
- Public sanitized tracking page with Leaflet.js / OpenStreetMap route rendering and chronological milestone history.

### 8. Analytics & CSV Export (Module I)
- Role-tailored dashboards with summary KPIs, status mix charts, and branch throughput rankings.
- 1-click filtered CSV export of parcel records.

---

## 👥 Pre-Seeded Demo User Accounts

Use the quick 1-click buttons on the Login page or log in with these credentials:

| Role | Email | Password | Scope |
| :--- | :--- | :--- | :--- |
| **Super Admin** | `superadmin@logiflows.com` | `SuperAdmin@LogiFlows2026!` | Global System Control |
| **Org Admin** | `orgadmin@logiflows.com` | `OrgAdmin@123` | LogiFlows Global Logistics |
| **Branch Manager**| `manager.mumbai@logiflows.com` | `Manager@123` | Mumbai Sorting Hub |
| **Delivery Agent**| `agent.rahul@logiflows.com` | `Agent@123` | Mumbai Last-Mile Fleet |
| **Customer** | `customer@example.com` | `Customer@123` | Retail Consignments |

---

## 🛠️ Technology Stack

- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, React Router v7, TanStack Query, Axios, Lucide React, Leaflet.js with OpenStreetMap.
- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic, PyJWT, Bcrypt, ReportLab, QRCode.
- **Databases:** PostgreSQL 16 (Production) / SQLite with WAL & StaticPool (Local Dev / Pytest).
- **Testing:** Pytest (Backend: 77 tests, 89% coverage), Vitest & RTL (Frontend: 8 tests), Playwright (E2E: 30 tests across Desktop, Mobile, Tablet).
- **Security & Quality:** pip-audit (0 vulnerabilities), npm audit (0 high/critical), Oxlint (0 errors), tsc (0 errors).
- **DevOps:** Docker Compose with automated one-shot migration service, Nginx reverse proxy with security headers (CSP, HSTS, X-Frame-Options), GitHub Actions CI.

---

## 💻 Local Development Setup

### 1. Backend Setup
```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
python -m app.cli seed-demo
uvicorn app.main:app --reload --port 8000
```
API Documentation will be live at `http://localhost:8000/docs`.

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Web application will be live at `http://localhost:5173`.

---

## 🧪 Running Automated Tests

### Backend Unit & Integration Tests (Pytest)
```bash
cd backend
.\venv\Scripts\pytest -v --cov=app --cov-report=term-missing
```
*Current test suite: 77/77 tests passing (89% total coverage; auth, security, state machine, tenant isolation, and RBAC matrix).*

### Frontend Component Tests (Vitest)
```bash
cd frontend
npm test
```
*Current test suite: 8/8 tests passing (Badge, Leaflet maps, routing, error handling).*

### End-to-End User Journeys (Playwright)
```bash
cd frontend
npx playwright test
```
*Current test suite: 30/30 tests passing across Desktop Chrome, Mobile Chrome (iPhone), and Tablet (iPad).*

### Security & Linter Verification
```bash
# Backend dependency audit
pip-audit -r backend/requirements.txt

# Frontend linter and typecheck
cd frontend
npm run lint
npx tsc -b
npm audit --audit-level=high
```

---

## 🐳 Docker Compose Deployment

Run the complete production-grade stack with PostgreSQL 16, automated Alembic migration service, FastAPI, and Nginx frontend in containers:

```bash
docker compose up --build -d
```

Services will be accessible at:
- **Frontend Portal:** `http://localhost:5173` or `http://localhost:3000`
- **FastAPI OpenAPI Swagger:** `http://localhost:8000/docs`
- **PostgreSQL Database:** `localhost:5432`
- **N8N Automation:** `http://localhost:5678`

