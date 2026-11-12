import { describe, it, expect, vi, beforeEach } from 'vitest';
import api from '../api/client';
import {
  organizationApi,
  branchApi,
  employeeApi,
  vehicleApi,
  customerApi,
  assignmentApi,
} from '../api';

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('Phase 12 Core Logistics APIs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Module 12.1: organizationApi', () => {
    it('calls POST /organizations/register with registration payload', async () => {
      const mockPayload = {
        name: 'Rapid Express Logistics',
        code: 'RAPID',
        admin_name: 'Rapid Admin',
        admin_email: 'admin@rapid.com',
        admin_password: 'Password123!',
      };
      const mockResponse = { data: { organization_id: 1, message: 'Created' } };
      (api.post as any).mockResolvedValueOnce(mockResponse);

      const res = await organizationApi.register(mockPayload);
      expect(api.post).toHaveBeenCalledWith('/organizations/register', mockPayload);
      expect(res).toEqual(mockResponse.data);
    });

    it('calls GET /organizations/my-org and PATCH /organizations/my-org', async () => {
      (api.get as any).mockResolvedValueOnce({ data: { id: 1, name: 'My Org' } });
      const getRes = await organizationApi.getMyOrg();
      expect(api.get).toHaveBeenCalledWith('/organizations/my-org');
      expect(getRes.name).toBe('My Org');

      (api.patch as any).mockResolvedValueOnce({ data: { id: 1, name: 'Updated Org' } });
      const patchRes = await organizationApi.updateMyOrg({ name: 'Updated Org' });
      expect(api.patch).toHaveBeenCalledWith('/organizations/my-org', { name: 'Updated Org' });
      expect(patchRes.name).toBe('Updated Org');
    });

    it('calls PATCH /organizations/{id}/status and GET /organizations/{id}/dashboard', async () => {
      (api.patch as any).mockResolvedValueOnce({ data: { id: 2, is_active: false } });
      const statusRes = await organizationApi.setStatus(2, false);
      expect(api.patch).toHaveBeenCalledWith('/organizations/2/status', { is_active: false });
      expect(statusRes.is_active).toBe(false);

      (api.get as any).mockResolvedValueOnce({
        data: { organization_id: 2, total_branches: 3, total_parcels: 42 },
      });
      const dashRes = await organizationApi.getDashboard(2);
      expect(api.get).toHaveBeenCalledWith('/organizations/2/dashboard');
      expect(dashRes.total_branches).toBe(3);
    });
  });

  describe('Module 12.2: branchApi Dashboard and Metrics', () => {
    it('calls GET /branches/{id}/dashboard', async () => {
      const mockMetrics = {
        branch_id: 5,
        branch_name: 'Central Hub',
        branch_code: 'HUB-001',
        is_active: true,
        total_active_parcels: 15,
        active_assignments: 4,
        assigned_employees: 6,
        assigned_vehicles: 3,
      };
      (api.get as any).mockResolvedValueOnce({ data: mockMetrics });

      const res = await branchApi.getDashboard(5);
      expect(api.get).toHaveBeenCalledWith('/branches/5/dashboard');
      expect(res.total_active_parcels).toBe(15);
      expect(res.assigned_vehicles).toBe(3);
    });
  });

  describe('Module 12.3: employeeApi Invites and Workflows', () => {
    it('calls POST /employees/{id}/invite and POST /employees/accept-invite', async () => {
      const mockInvite = {
        user_id: 10,
        email: 'agent@hub.com',
        invite_token: 'token-xyz',
        expires_in_hours: 48,
        invite_url: 'http://localhost/invite?token=token-xyz',
      };
      (api.post as any).mockResolvedValueOnce({ data: mockInvite });

      const inviteRes = await employeeApi.invite(10);
      expect(api.post).toHaveBeenCalledWith('/employees/10/invite');
      expect(inviteRes.invite_token).toBe('token-xyz');

      (api.post as any).mockResolvedValueOnce({ data: { message: 'Activated successfully' } });
      const acceptPayload = {
        invite_token: 'token-xyz',
        new_password: 'NewSecurePassword123!',
      };
      const acceptRes = await employeeApi.acceptInvite(acceptPayload);
      expect(api.post).toHaveBeenCalledWith('/employees/accept-invite', acceptPayload);
      expect(acceptRes.message).toBe('Activated successfully');
    });

    it('calls GET /employees/{id}/dashboard', async () => {
      const mockDash = {
        employee_id: 10,
        full_name: 'Agent John',
        email: 'john@logiflows.com',
        role: 'DELIVERY_AGENT',
        is_active: true,
        active_assignments: 2,
        completed_assignments: 18,
        total_assigned_parcels: 20,
      };
      (api.get as any).mockResolvedValueOnce({ data: mockDash });

      const res = await employeeApi.getDashboard(10);
      expect(api.get).toHaveBeenCalledWith('/employees/10/dashboard');
      expect(res.active_assignments).toBe(2);
      expect(res.completed_assignments).toBe(18);
    });
  });

  describe('Module 12.4: vehicleApi Maintenance', () => {
    it('calls PATCH /vehicles/{id}/maintenance with maintenance payload', async () => {
      const mockVehicle = {
        id: 7,
        vehicle_number: 'DL-01-AB-1234',
        status: 'MAINTENANCE',
        is_active: true,
      };
      (api.patch as any).mockResolvedValueOnce({ data: mockVehicle });

      const res = await vehicleApi.setMaintenance(7, true, 'Engine oil change');
      expect(api.patch).toHaveBeenCalledWith('/vehicles/7/maintenance', {
        in_maintenance: true,
        reason: 'Engine oil change',
      });
      expect(res.status).toBe('MAINTENANCE');
    });
  });

  describe('Module 12.5: customerApi Address Book and Profile', () => {
    it('calls GET /customers/me/profile and PUT /customers/me/profile', async () => {
      const mockProfile = {
        id: 15,
        email: 'customer@gmail.com',
        full_name: 'Customer One',
        role: 'CUSTOMER',
        customer_profile: {
          company_name: 'Apex Corp',
          gst_number: '27AAAAA0000A1Z5',
          default_pickup_address: 'Warehouse 4, Andheri East, Mumbai',
        },
      };
      (api.get as any).mockResolvedValueOnce({ data: mockProfile });

      const getRes = await customerApi.getMyProfile();
      expect(api.get).toHaveBeenCalledWith('/customers/me/profile');
      expect(getRes.customer_profile?.company_name).toBe('Apex Corp');

      const updatePayload = {
        company_name: 'Apex Global Logistics',
        default_pickup_address: 'Gate 2, Nhava Sheva Port, Navi Mumbai',
      };
      (api.put as any).mockResolvedValueOnce({
        data: {
          ...mockProfile,
          customer_profile: { ...mockProfile.customer_profile, ...updatePayload },
        },
      });

      const updateRes = await customerApi.updateMyProfile(updatePayload);
      expect(api.put).toHaveBeenCalledWith('/customers/me/profile', updatePayload);
      expect(updateRes.customer_profile?.company_name).toBe('Apex Global Logistics');
    });

    it('calls GET /customers/me/parcels', async () => {
      (api.get as any).mockResolvedValueOnce({ data: [{ id: 1, tracking_number: 'LGF-123' }] });
      const parcels = await customerApi.getMyParcels();
      expect(api.get).toHaveBeenCalledWith('/customers/me/parcels');
      expect(parcels).toHaveLength(1);
    });
  });

  describe('Module 12.7: assignmentApi Cancellation & Explainable Dispatch Suggestions', () => {
    it('calls POST /assignments/{id}/cancel with cancellation reason', async () => {
      const mockCancelled = {
        id: 3,
        parcel_id: 12,
        status: 'CANCELLED',
        notes: 'Delivery van flat tire',
      };
      (api.post as any).mockResolvedValueOnce({ data: mockCancelled });

      const res = await assignmentApi.cancel(3, 'Delivery van flat tire');
      expect(api.post).toHaveBeenCalledWith('/assignments/3/cancel', {
        cancellation_reason: 'Delivery van flat tire',
      });
      expect(res.status).toBe('CANCELLED');
    });

    it('calls GET /assignments/suggestions/{parcel_id} returning explainable recommendations', async () => {
      const mockSuggestions = {
        parcel_id: 12,
        tracking_number: 'LGF-99998888',
        parcel_weight_kg: 4.5,
        parcel_volume_cbm: 0.05,
        branch_id: 1,
        branch_name: 'Mumbai Central Hub',
        suggested_employees: [
          {
            employee_id: 2,
            full_name: 'Rajesh Kumar',
            active_assignments: 1,
            max_capacity: 10,
            workload_utilization_pct: 10,
            is_available: true,
            score: 95.0,
            explanation: 'Lowest active workload (1/10 active assignments).',
          },
        ],
        suggested_vehicles: [
          {
            vehicle_id: 4,
            vehicle_number: 'MH-02-CB-1234',
            vehicle_type: 'VAN',
            max_weight_kg: 500.0,
            max_volume_cbm: 6.0,
            parcel_weight_kg: 4.5,
            weight_utilization_pct: 0.9,
            fits_capacity: true,
            score: 99.1,
            explanation: 'Fits payload (0.9% weight utilized) with 495.5 kg spare capacity.',
          },
        ],
        summary_recommendation:
          'Assigned origin branch Mumbai Central Hub with 1 candidate agent(s) and 1 capacity-fit vehicle(s).',
      };
      (api.get as any).mockResolvedValueOnce({ data: mockSuggestions });

      const res = await assignmentApi.getSuggestions(12);
      expect(api.get).toHaveBeenCalledWith('/assignments/suggestions/12');
      expect(res.suggested_employees[0].score).toBe(95.0);
      expect(res.suggested_vehicles[0].fits_capacity).toBe(true);
      expect(res.summary_recommendation).toContain('Mumbai Central Hub');
    });
  });
});
