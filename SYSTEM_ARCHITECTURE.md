# LogiFlows - System Architecture Documentation

## 1. High-Level Architecture Overview

LogiFlows is built following a decoupled, layered micro-modular architecture designed for scalability, operational auditability, multi-tenant organization isolation, and seamless real-time tracking.

```
+-----------------------------------------------------------------------------------+
|                                  CLIENT LAYER                                     |
|                                                                                   |
|  [ Customer Web App ]     [ Staff & Ops Portal ]    [ Public Tracking Portal ]     |
|   React + TS + Tailwind    React + TS + Leaflet      React + OpenStreetMap        |
|                                     │                                             |
+-------------------------------------┼---------------------------------------------+
                                      │ HTTPS / REST JSON
                                      ▼
+-----------------------------------------------------------------------------------+
|                             API GATEWAY / FASTAPI                                 |
|                                                                                   |
|  - CORS & Security Headers Middleware                                             |
|  - JWT Authentication & RBAC Policy Enforcement                                   |
|  - Multi-tenant Organization & Branch Isolation Interceptors                      |
|  - Request Validation (Pydantic v2)                                               |
|  - Global Exception Handling & Uniform Response Formatting                        |
+-------------------------------------┼---------------------------------------------+
                                      │ Dependency Injection
                                      ▼
+-----------------------------------------------------------------------------------+
|                                SERVICE LAYER                                      |
|                                                                                   |
|  [ AuthService ]     [ OrgService ]       [ BranchService ]  [ EmployeeService ]  |
|  [ ParcelService ]   [ TrackingService ]  [ CustodyService ] [ FleetService ]     |
|  [ PricingEngine ]   [ QRLabelService ]   [ ReportService ]  [ AnalyticsService ] |
+-------------------------------------┼---------------------------------------------+
                                      │ Repository Pattern
                                      ▼
+-----------------------------------------------------------------------------------+
|                              REPOSITORY LAYER                                     |
|                                                                                   |
|  [ UserRepository ]  [ BranchRepository ] [ ParcelRepository ]                    |
|  [ TrackingRepo ]    [ AssignmentRepo ]   [ VehicleRepository ]                   |
+-------------------------------------┼---------------------------------------------+
                                      │ SQLAlchemy 2.0 ORM
                                      ▼
+-----------------------------------------------------------------------------------+
|                               PERSISTENCE LAYER                                   |
|                                                                                   |
|  PostgreSQL 16 (Production) / SQLite with WAL (Local Dev & Automated CI/Test)     |
|  - Alembic Schema Migrations                                                      |
|  - Transactional Isolation (ACID)                                                 |
|  - Full Spatial Coordinates (Latitude/Longitude) for Branch Geolocation           |
+-----------------------------------------------------------------------------------+
```

---

## 2. Security Architecture & RBAC Matrix

The system implements Role-Based Access Control (RBAC) across 5 distinct roles:

| Feature / Resource | Super Admin | Org Admin | Branch Manager | Delivery Agent | Customer | Public |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Manage Organizations | Full | Read-Own | Denied | Denied | Denied | Denied |
| Manage Branches | Full | Full (Own Org) | Read-Own | Read-Assigned | Denied | Denied |
| Manage Employees | Full | Full (Own Org) | Read/Assign (Own Branch) | Profile Only | Denied | Denied |
| Book Parcels | Yes | Yes | Yes | Denied | Yes (Self) | Denied |
| Manage / Edit Parcels | Full | Full (Own Org) | Branch Parcels | Status Updates Only | Cancel If Booked | Denied |
| Assign Delivery / Fleet | Full | Full (Own Org) | Own Branch | Denied | Denied | Denied |
| Scan QR Custody Events | Full | Full | Yes (At Branch) | Yes (Pickup/Delivery) | Denied | Denied |
| Public Tracking Page | Full | Full | Full | Full | Full | Read (Sanitized) |
| Analytics & Reports | Global | Organization | Branch | Personal Stats | Booking Stats | Denied |

---

## 3. Shipment Lifecycle State Machine

```
              [ BOOKED ]
                  │
                  │ (Dispatch/Pickup Request)
                  ▼
         [ PICKUP_SCHEDULED ]
                  │
                  │ (Agent Scans at Pickup)
                  ▼
            [ PICKED_UP ]
                  │
                  │ (Received at Local Hub)
                  ▼
         [ AT_ORIGIN_BRANCH ]
                  │
                  │ (Dispatched in Bulk Trunk/Vehicle)
                  ▼
            [ IN_TRANSIT ]
                  │
                  │ (Arrived at Destination Hub)
                  ▼
       [ AT_DESTINATION_BRANCH ]
                  │
                  │ (Assigned to Last-Mile Agent)
                  ▼
         [ OUT_FOR_DELIVERY ]
             │            │
 (Delivered) │            │ (Failed attempt)
             ▼            ▼
       [ DELIVERED ]   [ DELIVERY_FAILED ]
                              │
                              ▼
                     [ RETURN_TO_ORIGIN ]
```

*Cancellation Rule:* A parcel can only be cancelled by a customer if it remains in `BOOKED` state and no pickup activity has commenced.
*Immutability Rule:* Any status update automatically creates an append-only `tracking_history` record with the actor, branch, timestamp, coordinates, and event remarks.

