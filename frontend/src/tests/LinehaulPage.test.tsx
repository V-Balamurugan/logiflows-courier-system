import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { LinehaulPage } from '../pages/LinehaulPage';
import { branchApi, employeeApi, linehaulApi, parcelApi, vehicleApi } from '../api';

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 1,
      email: 'bm@logiflows.com',
      full_name: 'Origin Branch Manager',
      role: 'BRANCH_MANAGER',
      is_active: true,
      organization_id: 1,
      branch_id: 1,
      created_at: '2026-11-01T00:00:00Z',
    },
  }),
}));

vi.mock('../api', () => ({
  linehaulApi: {
    listManifests: vi.fn(),
    listBags: vi.fn(),
    listDiscrepancies: vi.fn(),
    createManifest: vi.fn(),
    dispatchManifest: vi.fn(),
    arriveManifest: vi.fn(),
    reconcileManifest: vi.fn(),
    createBag: vi.fn(),
    attachParcelsToBag: vi.fn(),
    sealBag: vi.fn(),
    debagBag: vi.fn(),
    reportDiscrepancy: vi.fn(),
    resolveDiscrepancy: vi.fn(),
  },
  branchApi: { list: vi.fn() },
  vehicleApi: { list: vi.fn() },
  employeeApi: { list: vi.fn() },
  parcelApi: { list: vi.fn() },
}));

describe('LinehaulPage UI Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (branchApi.list as any).mockResolvedValue([]);
    (vehicleApi.list as any).mockResolvedValue([]);
    (employeeApi.list as any).mockResolvedValue([]);
    (parcelApi.list as any).mockResolvedValue([]);
  });

  it('renders empty states cleanly when no manifests exist', async () => {
    (linehaulApi.listManifests as any).mockResolvedValueOnce([]);
    (linehaulApi.listBags as any).mockResolvedValueOnce([]);
    (linehaulApi.listDiscrepancies as any).mockResolvedValueOnce([]);

    render(<LinehaulPage />);

    expect(screen.getByText(/Loading linehaul operations/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/No linehaul manifests found/i)).toBeInTheDocument();
    });
  });

  it('renders error banner when backend API fails', async () => {
    (linehaulApi.listManifests as any).mockRejectedValueOnce({
      response: { data: { detail: 'Linehaul service temporarily unavailable' } },
    });

    render(<LinehaulPage />);

    await waitFor(() => {
      expect(screen.getByText(/Linehaul service temporarily unavailable/i)).toBeInTheDocument();
    });
  });

  it('renders manifest, bag, and discrepancy rows across tabs', async () => {
    (linehaulApi.listManifests as any).mockResolvedValueOnce([
      {
        id: 1,
        organization_id: 1,
        manifest_number: 'LH-20261112-XYZ999',
        origin_branch_id: 1,
        dest_branch_id: 2,
        origin_branch_name: 'Mumbai Hub',
        dest_branch_name: 'Delhi Hub',
        vehicle_id: 4,
        vehicle_number: 'MH01TR1000',
        driver_id: 7,
        driver_name: 'Driver A',
        seal_number: 'SEAL-55',
        status: 'IN_TRANSIT',
        expected_parcel_count: 5,
        received_parcel_count: 0,
        total_weight_kg: 42.5,
        created_at: '2026-11-12T05:00:00Z',
        items: [],
        bags: [],
        discrepancies: [],
      },
    ]);
    (linehaulApi.listBags as any).mockResolvedValueOnce([
      {
        id: 10,
        organization_id: 1,
        bag_code: 'BAG-20261112-BAG001',
        origin_branch_id: 1,
        dest_branch_id: 2,
        origin_branch_name: 'Mumbai Hub',
        dest_branch_name: 'Delhi Hub',
        status: 'SEALED',
        total_weight_kg: 12.0,
        parcel_count: 3,
        created_at: '2026-11-12T04:00:00Z',
        parcels: [],
      },
    ]);
    (linehaulApi.listDiscrepancies as any).mockResolvedValueOnce([
      {
        id: 77,
        organization_id: 1,
        manifest_id: 1,
        manifest_number: 'LH-20261112-XYZ999',
        tracking_number: 'LF-2026-999',
        discrepancy_type: 'MISSING',
        severity: 'HIGH',
        status: 'OPEN',
        description: 'Carton missing at Delhi dock',
        reported_at: '2026-11-12T06:00:00Z',
      },
    ]);

    render(<LinehaulPage />);

    await waitFor(() => {
      expect(screen.getByText('LH-20261112-XYZ999')).toBeInTheDocument();
      expect(screen.getByText('MH01TR1000')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Consolidation Bags/i }));
    expect(screen.getByText('BAG-20261112-BAG001')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Discrepancies/i }));
    expect(screen.getByText(/Carton missing at Delhi dock/i)).toBeInTheDocument();
  });
});

