# LogiFlows — Phase 12 Architectural Proposal & Roadmap

> [!NOTE]
> This document is an architectural proposal for Phase 12. No code has been written or modified for this phase. All features described herein represent forward-looking capabilities designed to extend the verified Phase 11 foundation.

---

## 1. Executive Summary

Phase 11 established a rock-solid, audited, and verified foundation: zero schema drift, full optimistic concurrency locking, partial unique indexes preventing dispatch collisions, 100% RBAC multi-tenant isolation, 89% backend test coverage, and a full 30-test Playwright E2E suite across Desktop, Mobile, and Tablet form factors.

Phase 12 builds upon this stable bedrock to introduce real-time logistics automation, field mobility enhancements, automated routing, and external messaging gateways.

---

## 2. Proposed Feature Modules for Phase 12

### Module 1: Real-Time WebSocket Telemetry & Live Driver Map
- **Objective:** Move from polling-based tracking to sub-second bidirectional streaming updates.
- **Components:**
  - FastAPI WebSocket endpoint: `/ws/tracking/{tracking_number}`.
  - Redis Pub/Sub backplane for scaling across multiple backend worker processes.
  - React hook `useShipmentSocket` providing live courier movement animations on Leaflet maps without full page refreshes.

### Module 2: Enhanced Mobile e-PoD (Electronic Proof of Delivery)
- **Objective:** Enable delivery agents to collect high-fidelity proof of delivery in the field.
- **Components:**
  - Touch-friendly HTML5 Canvas signature pad component with SVG vector export.
  - Camera-based package photo capture with client-side image compression.
  - S3/MinIO/GCS presigned URL upload pipeline for tamper-proof storage of delivery evidence.

### Module 3: Dynamic Route Optimization & Dispatch Batches
- **Objective:** Optimize last-mile delivery sequences to reduce fuel consumption and transit times.
- **Components:**
  - Integration with Open Source Routing Machine (OSRM) or Google OR-Tools.
  - Traveling Salesperson Problem (TSP) solver clustering stops within a branch's delivery polygon.
  - Interactive manifest re-ordering with drag-and-drop in the Branch Manager dashboard.

### Module 4: Multi-Channel Customer Notification Gateway
- **Objective:** Notify customers at key milestones via their preferred channels.
- **Components:**
  - Webhook dispatch via the containerized n8n workflow engine.
  - WhatsApp Business Cloud API & SMS gateway integrations (Twilio, Gupshup).
  - Transactional email templates for booking confirmations and delivery OTP receipts via Brevo/SendGrid.

### Module 5: Warehouse Batch Barcode Processing (High-Throughput Mode)
- **Objective:** Support high-speed hub sorting operations using physical Bluetooth/USB HID scanners.
- **Components:**
  - Dedicated "Fast-Scan" UI with audio feedback (distinct chimes for success, route mismatch, or state error).
  - Rapid buffering pipeline accepting 60+ scans per minute without UI lag.
  - Automatic manifest reconciliation flagging missing or misrouted consignments in real time.

---

## 3. Recommended Phasing & Governance

| Milestone | Scope | Estimated Effort |
| :--- | :--- | :--- |
| **Phase 12.1** | Redis Pub/Sub backplane + WebSocket Tracking Endpoint | 1 Sprint |
| **Phase 12.2** | Mobile e-PoD with Signature Canvas & Photo Storage | 1 Sprint |
| **Phase 12.3** | OSRM / Route Sequence Dispatch Engine | 1 Sprint |
| **Phase 12.4** | n8n Webhooks & Multi-Channel SMS/WhatsApp Alerts | 1 Sprint |
| **Phase 12.5** | High-Throughput Warehouse Fast-Scan Hub Portal | 1 Sprint |
