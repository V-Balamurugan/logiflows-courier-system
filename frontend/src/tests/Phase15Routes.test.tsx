import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import api from '../api/client';
import { branchApi, employeeApi, parcelApi, routeApi, vehicleApi } from '../api';
import { RoutesPage } from '../pages/RoutesPage';
import * as AuthContext from '../contexts/AuthContext';
import { DeliveryRoute, User } from '../types';

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

const bmUser: User = {
  id: 3,
  email: 'manager.mumbai@logiflows.com',
  full_name: 'Mumbai Branch Manager',
  role: 'BRANCH_MANAGER',
  is_active: true,
  organization_id: 1,
  branch_id: 1,
  created_at: '2026-11-01T00:00:00Z',
};

const sampleRoute: DeliveryRoute = {
  id: 101,
  route_code: 'RTE-BOM001-20261112-A1B2',
  organization_id: 1,
  branch_id: 1,
  branch_name: 'Mumbai Hub',
  vehicle_id: 11,
  vehicle_number: 'MH-02-CB-4091',
  vehicle_type: 'VAN',
  vehicle_max_weight_kg: 500,
  driver_id: 4,
  driver_name: 'Rahul Sharma',
  status: 'PLANNED',
  is_active_dispatch: false,
  optimization_objective: 'SHORTEST',
  provider_used: 'local_fallback',
  is_fallback: false,
  return_to_hub: true,
  start_latitude: 19.076,
  start_longitude: 72.8777,
  total_distance_km: 14.2,
  baseline_distance_km: 19.8,
  distance_saved_km: 5.6,
  distance_saved_pct: 28.3,
  estimated_duration_min: 32.5,
  total_weight_kg: 12.0,
  utilization_pct: 2.4,
  total_stops: 2,
  completed_stops: 0,
  geometry_points: [
    [19.076, 72.8777],
    [19.11, 72.89],
    [19.14, 72.91],
    [19.076, 72.8777],
  ],
  version_id: 1,
  created_at: '2026-11-12T06:00:00Z',
  stops: [
    {
      id: 201,
      route_id: 101,
      parcel_id: 501,
      tracking_number: 'LF-2026-BOM001',
      sequence_order: 1,
      stop_type: 'DELIVERY',
      status: 'PENDING',
      is_active: true,
      location_name: 'Andheri West Client',
      address: '101 Link Road, Mumbai 400053',
      latitude: 19.11,
      longitude: 72.89,
      coords_source: 'BRANCH_VICINITY_ESTIMATE',
      distance_from_prev_km: 4.5,
      eta_minutes_from_start: 12.0,
    },
    {
      id: 202,
      route_id: 101,
      sequence_order: 2,
      stop_type: 'DELIVERY',
      status: 'PENDING',
      is_active: false,
      location_name: 'Powai Tech Park',
      address: 'Powai Lake, Mumbai 400076',
      latitude: 19.14,
      longitude: 72.91,
      coords_source: 'EXPLICIT',
      distance_from_prev_km: 5.2,
      eta_minutes_from_start: 24.0,
    },
  ],
};

describe('Phase 15: routeApi Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls preview, create, reoptimize, dispatch, start, updateStop, and cancel endpoints', async () => {
    (api.post as any).mockResolvedValueOnce({ data: { total_distance_km: 12.5, stops: [] } });
    await routeApi.preview({ branch_id: 1, objective: 'FASTEST', parcel_ids: [10, 11] });
    expect(api.post).toHaveBeenCalledWith('/routes/preview', {
      branch_id: 1,
      objective: 'FASTEST',
      parcel_ids: [10, 11],
    });

    (api.post as any).mockResolvedValueOnce({ data: sampleRoute });
    await routeApi.create({ branch_id: 1, parcel_ids: [10] });
    expect(api.post).toHaveBeenCalledWith('/routes', { branch_id: 1, parcel_ids: [10] });

    (api.post as any).mockResolvedValueOnce({ data: { ...sampleRoute, version_id: 2 } });
    await routeApi.reoptimize(101, { objective: 'MANUAL', manual_stop_ids: [202, 201], expected_version_id: 1 });
    expect(api.post).toHaveBeenCalledWith('/routes/101/reoptimize', {
      objective: 'MANUAL',
      manual_stop_ids: [202, 201],
      expected_version_id: 1,
    });

    (api.post as any).mockResolvedValueOnce({ data: { ...sampleRoute, status: 'DISPATCHED' } });
    await routeApi.dispatch(101, { vehicle_id: 11, driver_id: 4 });
    expect(api.post).toHaveBeenCalledWith('/routes/101/dispatch', { vehicle_id: 11, driver_id: 4 });

    (api.post as any).mockResolvedValueOnce({ data: { ...sampleRoute, status: 'IN_PROGRESS' } });
    await routeApi.start(101);
    expect(api.post).toHaveBeenCalledWith('/routes/101/start');

    (api.post as any).mockResolvedValueOnce({ data: sampleRoute });
    await routeApi.updateStop(101, 201, { status: 'COMPLETED', latitude: 19.11, longitude: 72.89 });
    expect(api.post).toHaveBeenCalledWith('/routes/101/stops/201/update', {
      status: 'COMPLETED',
      latitude: 19.11,
      longitude: 72.89,
    });

    (api.post as any).mockResolvedValueOnce({ data: { ...sampleRoute, status: 'CANCELLED' } });
    await routeApi.cancel(101, 'Wave Consolidated');
    expect(api.post).toHaveBeenCalledWith('/routes/101/cancel', { cancellation_reason: 'Wave Consolidated' });
  });
});

describe('Phase 15: RoutesPage UI Workbench', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
      user: bmUser,
      token: 'valid-token',
      loading: false,
      login: vi.fn(),
      logout: vi.fn(),
    });
    vi.spyOn(branchApi, 'list').mockResolvedValue([
      {
        id: 1,
        organization_id: 1,
        branch_code: 'BOM-001',
        branch_name: 'Mumbai Hub',
        address: 'Andheri East',
        pincode: '400069',
        city: 'Mumbai',
        state: 'Maharashtra',
        country: 'India',
        contact_email: 'bom@logiflows.com',
        contact_phone: '9876543210',
        latitude: 19.076,
        longitude: 72.8777,
        operating_status: 'ACTIVE',
        is_active: true,
        created_at: '2026-11-01T00:00:00Z',
      },
    ]);
    vi.spyOn(vehicleApi, 'list').mockResolvedValue([]);
    vi.spyOn(employeeApi, 'list').mockResolvedValue([]);
    vi.spyOn(parcelApi, 'list').mockResolvedValue([]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows loading state and empty state cleanly when no routes exist', async () => {
    vi.spyOn(routeApi, 'list').mockResolvedValueOnce([]);
    render(<RoutesPage />);

    expect(screen.getByText(/Loading route plans/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/No route plans found/i)).toBeInTheDocument();
    });
  });

  it('renders error alert when route fetching fails', async () => {
    vi.spyOn(routeApi, 'list').mockRejectedValueOnce({
      response: { data: { detail: 'Routing service unreachable' } },
    });
    render(<RoutesPage />);

    await waitFor(() => {
      expect(screen.getByText(/Routing service unreachable/i)).toBeInTheDocument();
    });
  });

  it('displays route itinerary, honest vicinity badge, and executes preview planner flow', async () => {
    vi.spyOn(routeApi, 'list').mockResolvedValue([sampleRoute]);
    const previewSpy = vi.spyOn(routeApi, 'preview').mockResolvedValueOnce({
      branch_id: 1,
      branch_name: 'Mumbai Hub',
      start_latitude: 19.076,
      start_longitude: 72.8777,
      total_weight_kg: 5.0,
      capacity_exceeded: false,
      objective: 'FASTEST',
      return_to_hub: true,
      provider_used: 'local_fallback',
      is_fallback: true,
      fallback_reason: 'OpenRouteService unavailable; degraded cleanly to local 2-opt optimizer',
      baseline_distance_km: 20.0,
      total_distance_km: 14.0,
      distance_saved_km: 6.0,
      distance_saved_pct: 30.0,
      estimated_duration_min: 31.0,
      geometry_points: [
        [19.076, 72.8777],
        [19.12, 72.9],
      ],
      stops: [
        {
          sequence_order: 1,
          stop_type: 'DELIVERY',
          location_name: 'Powai Client',
          latitude: 19.12,
          longitude: 72.9,
          coords_source: 'EXPLICIT',
          parcel_weight_kg: 0,
          distance_from_prev_km: 6.5,
          eta_minutes_from_start: 18.0,
        },
      ],
    });

    render(<RoutesPage />);

    await waitFor(() => {
      expect(screen.getByText('Andheri West Client')).toBeInTheDocument();
      expect(screen.getByText(/Vicinity Est\./i)).toBeInTheDocument();
    });

    // Switch to Plan New Route
    fireEvent.click(screen.getByRole('button', { name: /Plan New Route/i }));
    fireEvent.change(screen.getByPlaceholderText(/Stop location name/i), {
      target: { value: 'Powai Client' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Latitude/i), {
      target: { value: '19.12' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Longitude/i), {
      target: { value: '72.90' },
    });
    fireEvent.click(screen.getByRole('button', { name: /\+ Add Stop/i }));
    fireEvent.click(screen.getByRole('button', { name: /Preview Optimized Route/i }));

    await waitFor(() => {
      expect(previewSpy).toHaveBeenCalledTimes(1);
      expect(screen.getByText(/degraded cleanly to local 2-opt optimizer/i)).toBeInTheDocument();
      expect(screen.getByText(/6 km \(30%\)/i)).toBeInTheDocument();
    });
  });
});
