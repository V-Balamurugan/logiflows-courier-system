import { describe, it, expect, vi, beforeEach } from 'vitest';
import api from '../api/client';
import { linehaulApi } from '../api';

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('Phase 14: Branch-to-Branch Linehaul Transfers API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('creates, packs, seals, and de-bags consolidation bags cleanly', async () => {
    (api.post as any).mockResolvedValueOnce({
      data: { id: 11, bag_code: 'BAG-20261112-AAA111', status: 'OPEN', parcel_count: 0 },
    });
    const created = await linehaulApi.createBag({ origin_branch_id: 1, dest_branch_id: 2 });
    expect(api.post).toHaveBeenCalledWith('/linehaul/bags', { origin_branch_id: 1, dest_branch_id: 2 });
    expect(created.bag_code).toBe('BAG-20261112-AAA111');

    (api.post as any).mockResolvedValueOnce({
      data: { id: 11, status: 'OPEN', parcel_count: 2, total_weight_kg: 7.5 },
    });
    const packed = await linehaulApi.attachParcelsToBag(11, { parcel_ids: [101, 102] });
    expect(api.post).toHaveBeenCalledWith('/linehaul/bags/11/parcels', { parcel_ids: [101, 102] });
    expect(packed.parcel_count).toBe(2);

    (api.post as any).mockResolvedValueOnce({
      data: { id: 11, status: 'SEALED', seal_number: 'SEAL-77' },
    });
    const sealed = await linehaulApi.sealBag(11, 'SEAL-77');
    expect(api.post).toHaveBeenCalledWith('/linehaul/bags/11/seal', { seal_number: 'SEAL-77' });
    expect(sealed.status).toBe('SEALED');

    (api.post as any).mockResolvedValueOnce({
      data: { id: 11, status: 'OPENED_AT_DEST' },
    });
    const debagged = await linehaulApi.debagBag(11, 'Opened at hub');
    expect(api.post).toHaveBeenCalledWith('/linehaul/bags/11/debag', { notes: 'Opened at hub' });
    expect(debagged.status).toBe('OPENED_AT_DEST');
  });

  it('creates, dispatches, arrives, and reconciles linehaul manifests', async () => {
    (api.post as any).mockResolvedValueOnce({
      data: { id: 21, manifest_number: 'LH-20261112-001', status: 'DRAFT', expected_parcel_count: 2 },
    });
    const manifest = await linehaulApi.createManifest({
      origin_branch_id: 1,
      dest_branch_id: 2,
      vehicle_id: 5,
      bag_ids: [11],
    });
    expect(api.post).toHaveBeenCalledWith('/linehaul/manifests', {
      origin_branch_id: 1,
      dest_branch_id: 2,
      vehicle_id: 5,
      bag_ids: [11],
    });
    expect(manifest.manifest_number).toBe('LH-20261112-001');

    (api.post as any).mockResolvedValueOnce({
      data: { id: 21, status: 'IN_TRANSIT', seal_number: 'LH-SEAL-1' },
    });
    const dispatched = await linehaulApi.dispatchManifest(21, { seal_number: 'LH-SEAL-1' });
    expect(api.post).toHaveBeenCalledWith('/linehaul/manifests/21/dispatch', { seal_number: 'LH-SEAL-1' });
    expect(dispatched.status).toBe('IN_TRANSIT');

    (api.post as any).mockResolvedValueOnce({
      data: { id: 21, status: 'ARRIVED' },
    });
    const arrived = await linehaulApi.arriveManifest(21, { seal_intact: true });
    expect(api.post).toHaveBeenCalledWith('/linehaul/manifests/21/arrive', { seal_intact: true });
    expect(arrived.status).toBe('ARRIVED');

    (api.post as any).mockResolvedValueOnce({
      data: {
        manifest: { id: 21, status: 'RECONCILED' },
        received_count: 1,
        damaged_count: 0,
        missing_count: 1,
        excess_count: 0,
        discrepancies_created: 1,
      },
    });
    const reconciled = await linehaulApi.reconcileManifest(21, {
      received_tracking_numbers: ['LF-2026-001'],
      finalize: true,
    });
    expect(api.post).toHaveBeenCalledWith('/linehaul/manifests/21/reconcile', {
      received_tracking_numbers: ['LF-2026-001'],
      finalize: true,
    });
    expect(reconciled.missing_count).toBe(1);
    expect(reconciled.manifest.status).toBe('RECONCILED');
  });

  it('logs and resolves transfer discrepancies cleanly', async () => {
    (api.post as any).mockResolvedValueOnce({
      data: { id: 31, discrepancy_type: 'DAMAGED', severity: 'HIGH', status: 'OPEN' },
    });
    const created = await linehaulApi.reportDiscrepancy({
      manifest_id: 21,
      tracking_number: 'LF-2026-002',
      discrepancy_type: 'DAMAGED',
      severity: 'HIGH',
      description: 'Water damage on outer carton',
    });
    expect(api.post).toHaveBeenCalledWith('/linehaul/discrepancies', {
      manifest_id: 21,
      tracking_number: 'LF-2026-002',
      discrepancy_type: 'DAMAGED',
      severity: 'HIGH',
      description: 'Water damage on outer carton',
    });
    expect(created.status).toBe('OPEN');

    (api.patch as any).mockResolvedValueOnce({
      data: { id: 31, status: 'RESOLVED', resolution_notes: 'Claim filed' },
    });
    const resolved = await linehaulApi.resolveDiscrepancy(31, {
      status: 'RESOLVED',
      resolution_notes: 'Claim filed',
      release_parcel_to_dest: true,
    });
    expect(api.patch).toHaveBeenCalledWith('/linehaul/discrepancies/31', {
      status: 'RESOLVED',
      resolution_notes: 'Claim filed',
      release_parcel_to_dest: true,
    });
    expect(resolved.status).toBe('RESOLVED');
  });
});

