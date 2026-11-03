# LogiFlows - Database Schema Specification

## 1. Relational Entity-Relationship Diagram

```
+--------------------+            +------------------------+
|   organizations    | 1        * |        branches        |
|--------------------|<-----------|------------------------|
| id (PK)            |            | id (PK)                |
| name               |            | organization_id (FK)   |
| code (UNIQUE)      |            | branch_code (UNIQUE)   |
| email, phone       |            | name, address, pincode |
| is_active          |            | city, state, country   |
| created_at         |            | latitude, longitude    |
+--------------------+            | is_active, created_at  |
         │                        +------------------------+
         │ 1                                   │ 1
         │                                     │
         ▼ *                                   ▼ *
+--------------------+            +------------------------+
|       users        |            |        vehicles        |
|--------------------|            |------------------------|
| id (PK)            |            | id (PK)                |
| organization_id(FK)|            | organization_id (FK)   |
| branch_id (FK)     |            | branch_id (FK)         |
| email (UNIQUE)     |            | vehicle_number (UNIQUE)|
| hashed_password    |            | vehicle_type, model    |
| full_name, phone   |            | max_weight_kg          |
| role (ENUM)        |            | status (ENUM)          |
| is_active          |            +------------------------+
+--------------------+                         │ 1
         │ 1                                   │
         ├──────────────────────┐              │
         │ (as customer)        │ (as agent)   │
         ▼ *                    ▼ *            ▼ *
+--------------------+     +--------------------------------+
|      parcels       |     |      delivery_assignments      |
|--------------------|     |--------------------------------|
| id (PK)            | 1 * | id (PK)                        |
| tracking_number(UQ)|<----| parcel_id (FK)                 |
| customer_id (FK)   |     | employee_id (FK)               |
| origin_branch_id   |     | vehicle_id (FK, nullable)      |
| dest_branch_id     |     | assignment_type (ENUM)         |
| sender_details(J)  |     | status (ENUM)                  |
| receiver_details(J)|     | assigned_at, completed_at      |
| weight, dimensions |     +--------------------------------+
| service_type (ENUM)|
| status (ENUM)      |
| total_charge       |
+--------------------+
         │ 1
         ├──────────────────────────┐
         ▼ *                        ▼ *
+--------------------+     +--------------------------------+
|  tracking_history  |     |         custody_scans          |
|--------------------|     |--------------------------------|
| id (PK)            |     | id (PK)                        |
| parcel_id (FK)     |     | parcel_id (FK)                 |
| status (ENUM)      |     | scanned_by_id (FK)             |
| branch_id (FK, opt)|     | branch_id (FK, opt)            |
| employee_id(FK,opt)|     | scan_type (ENUM)               |
| location_name      |     | latitude, longitude            |
| notes, timestamp   |     | scan_result, timestamp         |
+--------------------+     +--------------------------------+
```

## 2. Enumerations

- **UserRole**: `SUPER_ADMIN`, `ORG_ADMIN`, `BRANCH_MANAGER`, `DELIVERY_AGENT`, `CUSTOMER`
- **ParcelStatus**: `BOOKED`, `PICKUP_SCHEDULED`, `PICKED_UP`, `AT_ORIGIN_BRANCH`, `IN_TRANSIT`, `AT_DESTINATION_BRANCH`, `OUT_FOR_DELIVERY`, `DELIVERED`, `DELIVERY_FAILED`, `RETURN_TO_ORIGIN`, `CANCELLED`, `ON_HOLD`
- **ServiceType**: `STANDARD`, `EXPRESS`, `SAME_DAY`, `OVERNIGHT`
- **PaymentStatus**: `PENDING`, `PAID`, `REFUNDED`
- **VehicleStatus**: `AVAILABLE`, `ASSIGNED`, `IN_TRANSIT`, `MAINTENANCE`, `RETIRED`
- **AssignmentStatus**: `ASSIGNED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`
- **ScanType**: `PICKUP_VERIFICATION`, `ORIGIN_INWARD`, `HUB_OUTWARD`, `DEST_INWARD`, `OUT_FOR_DELIVERY`, `DELIVERY_CONFIRMATION`

## 3. Database Indexes & Constraints
- `tracking_number`: Unique index, B-Tree indexed for $O(1)$ fast lookups
- `branch_code`: Unique index per organization
- `users.email`: Unique index
- Composite Index: `parcels (customer_id, created_at)`
- Composite Index: `tracking_history (parcel_id, created_at ASC)`
- Composite Index: `delivery_assignments (employee_id, status)`

