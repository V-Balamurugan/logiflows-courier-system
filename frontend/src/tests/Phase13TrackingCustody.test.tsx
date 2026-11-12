import { describe, it, expect, vi, beforeEach } from 'vitest';
import api from '../api/client';
import { trackingApi, custodyApi } from '../api';

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('Phase 13: Tracking & QR Custody Operations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Module 13.1 & 13.2: Tracking API Client', () => {
    it('fetches sanitized public tracking details via getPublic', async () => {
      const mockPublicData = {
        tracking_number: 'LF-2026-990011',
        status: 'IN_TRANSIT',
        origin_city: 'Mumbai',
        destination_city: 'Delhi',
        booking_date: '2026-11-10T10:00:00Z',
        milestones: [
          {
            status: 'BOOKED',
            location: 'Mumbai Hub',
            remarks: 'Consignment booked',
            timestamp: '2026-11-10T10:00:00Z',
          },
        ],
      };
      (api.get as any).mockResolvedValueOnce({ data: mockPublicData });

      const res = await trackingApi.getPublic('LF-2026-990011');
      expect(api.get).toHaveBeenCalledWith('/tracking/public/LF-2026-990011');
      expect(res.tracking_number).toBe('LF-2026-990011');
      expect(res.origin_city).toBe('Mumbai');
      expect(res.milestones).toHaveLength(1);
    });

    it('fetches detailed authenticated tracking via getAuthenticated', async () => {
      const mockAuthData = {
        tracking_number: 'LF-2026-990011',
        status: 'IN_TRANSIT',
        sender_name: 'Alice Consignor',
        receiver_name: 'Charlie Consignee',
        sender_phone: '9876543210',
        receiver_phone: '9876543211',
        weight_kg: 2.5,
        service_type: 'EXPRESS',
        history: [],
      };
      (api.get as any).mockResolvedValueOnce({ data: mockAuthData });

      const res = await trackingApi.getAuthenticated('LF-2026-990011');
      expect(api.get).toHaveBeenCalledWith('/tracking/LF-2026-990011');
      expect(res.sender_name).toBe('Alice Consignor');
      expect(res.receiver_name).toBe('Charlie Consignee');
    });

    it('generates the correct SSE live event source URL', () => {
      const url = trackingApi.getLiveEventSourceUrl('LF-2026-990011');
      expect(url).toContain('/tracking/live/LF-2026-990011');
    });

    it('posts manual tracking updates via updateStatus', async () => {
      const mockHistory = {
        id: 101,
        parcel_id: 1,
        status: 'OUT_FOR_DELIVERY',
        location_name: 'Delhi North Hub',
        created_at: '2026-11-10T11:00:00Z',
      };
      (api.post as any).mockResolvedValueOnce({ data: mockHistory });

      const res = await trackingApi.updateStatus('LF-2026-990011', {
        status: 'OUT_FOR_DELIVERY' as any,
        location_name: 'Delhi North Hub',
      });
      expect(api.post).toHaveBeenCalledWith('/tracking/LF-2026-990011/update', {
        status: 'OUT_FOR_DELIVERY',
        location_name: 'Delhi North Hub',
      });
      expect(res.id).toBe(101);
    });
  });

  describe('Module 13.4 & 13.5: Custody API & Hash Chain Verification', () => {
    it('submits custody scan and receives record hash', async () => {
      const mockScanResponse = {
        id: 55,
        parcel_id: 10,
        tracking_number: 'LF-2026-990011',
        scan_type: 'ORIGIN_INWARD',
        new_parcel_status: 'AT_ORIGIN_BRANCH',
        scanned_by_id: 5,
        scanned_by_name: 'Agent Ramesh',
        previous_hash: 'GENESIS_CUSTODY_HASH',
        record_hash: 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
        created_at: '2026-11-10T10:00:00Z',
      };
      (api.post as any).mockResolvedValueOnce({ data: mockScanResponse });

      const res = await custodyApi.scan({
        tracking_number: 'LF-2026-990011',
        scan_type: 'ORIGIN_INWARD',
      });
      expect(api.post).toHaveBeenCalledWith('/custody/scan', {
        tracking_number: 'LF-2026-990011',
        scan_type: 'ORIGIN_INWARD',
      });
      expect(res.previous_hash).toBe('GENESIS_CUSTODY_HASH');
      expect(res.record_hash).toHaveLength(64);
    });

    it('cryptographically verifies custody chain via verifyChain', async () => {
      const mockChainVerification = {
        tracking_number: 'LF-2026-990011',
        parcel_id: 10,
        total_scans: 2,
        is_valid: true,
        tamper_detected: false,
        chain: [
          {
            id: 1,
            scan_type: 'ORIGIN_INWARD',
            is_successful: true,
            scanned_by_name: 'Agent Ramesh',
            created_at: '2026-11-10T10:00:00Z',
            previous_hash: 'GENESIS_CUSTODY_HASH',
            record_hash: 'hash1111111111111111111111111111111111111111111111111111111111111111',
            verified: true,
          },
          {
            id: 2,
            scan_type: 'HUB_OUTWARD',
            is_successful: true,
            scanned_by_name: 'Manager Suresh',
            created_at: '2026-11-10T10:05:00Z',
            previous_hash: 'hash1111111111111111111111111111111111111111111111111111111111111111',
            record_hash: 'hash2222222222222222222222222222222222222222222222222222222222222222',
            verified: true,
          },
        ],
      };
      (api.get as any).mockResolvedValueOnce({ data: mockChainVerification });

      const res = await custodyApi.verifyChain('LF-2026-990011');
      expect(api.get).toHaveBeenCalledWith('/custody/LF-2026-990011/verify-chain');
      expect(res.is_valid).toBe(true);
      expect(res.tamper_detected).toBe(false);
      expect(res.chain).toHaveLength(2);
      expect(res.chain[0].previous_hash).toBe('GENESIS_CUSTODY_HASH');
      expect(res.chain[1].previous_hash).toBe(res.chain[0].record_hash);
    });

    it('retrieves custody history via getHistory', async () => {
      (api.get as any).mockResolvedValueOnce({
        data: [{ id: 1, scan_type: 'ORIGIN_INWARD', scanned_by: 'Agent Ramesh' }],
      });
      const res = await custodyApi.getHistory('LF-2026-990011');
      expect(api.get).toHaveBeenCalledWith('/custody/LF-2026-990011/history');
      expect(res).toHaveLength(1);
    });
  });
});
