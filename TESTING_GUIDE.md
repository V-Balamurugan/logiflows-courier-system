# LogiFlows - Comprehensive Testing Guide

This document describes the automated and manual testing strategies for LogiFlows across backend, frontend, and integration layers.

---

## 1. Backend Testing with Pytest

### Running the Test Suite
Activate the backend virtual environment and execute pytest:

```powershell
# Windows
cd backend
.\venv\Scripts\pytest -v

# Or from project root
.\backend\venv\Scripts\pytest backend/app/tests -v
```

### Coverage Goals
- **Authentication & RBAC:** Verifies token generation, password hashing, role enforcement, and token rejection.
- **Branch & Organization Services:** Tests multi-tenant isolation, branch geocoding persistence, and branch code uniqueness.
- **Employee Management:** Tests role assignment, password safety, and active workload tracking.
- **Parcel Booking & Pricing Engine:** Tests dimensional weight formulas, zone calculations, unique tracking numbers, and cancellation rules.
- **Shipment Lifecycle & QR Custody:** Verifies sequential state machine constraints and QR verification logic.
- **Assignments & Fleet Availability:** Verifies conflict detection when assigning vehicles or delivery agents.

---

## 2. Frontend Testing with Vitest & Testing Library

### Running the Frontend Unit & Component Tests
```powershell
cd frontend
npm run test
```

### Areas Covered
- Form validation (Zod schema checking for booking, login, branch creation).
- Role-based route guard redirects.
- Component state handling for tracking search and Leaflet map rendering.

---

## 3. End-to-End Testing with Playwright

### Running E2E Tests
```powershell
cd frontend
npx playwright test
```

### Workflows Tested
1. **Public Tracking Journey:** Guest enters a valid tracking number and views real-time status steps.
2. **Customer Booking Journey:** Customer registers, logs in, calculates quote, books a parcel, and downloads confirmation.
3. **Staff Dispatch & QR Custody:** Admin assigns parcel to branch, delivery agent scans QR, status updates to `OUT_FOR_DELIVERY`, and agent marks `DELIVERED`.

