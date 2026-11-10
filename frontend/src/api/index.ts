import api from './client';
import {
  User,
  AuthResponse,
  Branch,
  Vehicle,
  Parcel,
  DeliveryAssignment,
  PublicTrackingResponse,
  DashboardStats,
  Organization,
  OrganizationDashboard,
  BranchDashboard,
  EmployeeDashboard,
  EmployeeInviteResponse,
  CustomerProfileUpdate,
  DispatchSuggestionsResponse,
} from '../types';

export const organizationApi = {
  register: async (data: {
    name: string;
    code: string;
    admin_name: string;
    admin_email: string;
    admin_password: string;
    admin_phone?: string;
    contact_email?: string;
    contact_phone?: string;
    address?: string;
  }) => {
    const res = await api.post('/organizations/register', data);
    return res.data;
  },
  list: async (): Promise<Organization[]> => {
    const res = await api.get<Organization[]>('/organizations');
    return res.data;
  },
  getMyOrg: async (): Promise<Organization> => {
    const res = await api.get<Organization>('/organizations/my-org');
    return res.data;
  },
  updateMyOrg: async (data: Partial<Organization>): Promise<Organization> => {
    const res = await api.patch<Organization>('/organizations/my-org', data);
    return res.data;
  },
  get: async (id: number): Promise<Organization> => {
    const res = await api.get<Organization>(`/organizations/${id}`);
    return res.data;
  },
  update: async (id: number, data: Partial<Organization>): Promise<Organization> => {
    const res = await api.patch<Organization>(`/organizations/${id}`, data);
    return res.data;
  },
  setStatus: async (id: number, is_active: boolean): Promise<Organization> => {
    const res = await api.patch<Organization>(`/organizations/${id}/status`, { is_active });
    return res.data;
  },
  getDashboard: async (id: number): Promise<OrganizationDashboard> => {
    const res = await api.get<OrganizationDashboard>(`/organizations/${id}/dashboard`);
    return res.data;
  },
};

export const authApi = {
  login: async (credentials: { email: string; password: string }): Promise<AuthResponse> => {
    const res = await api.post<AuthResponse>('/auth/login', credentials);
    return res.data;
  },
  register: async (data: any): Promise<User> => {
    const res = await api.post<User>('/auth/register', data);
    return res.data;
  },
  getProfile: async (): Promise<User> => {
    const res = await api.get<User>('/auth/me');
    return res.data;
  },
  changePassword: async (data: { current_password: string; new_password: string }) => {
    const res = await api.put('/auth/change-password', data);
    return res.data;
  },
};

export const branchApi = {
  list: async (params?: { search?: string; city?: string; is_active?: boolean }): Promise<Branch[]> => {
    const res = await api.get<Branch[]>('/branches', { params });
    return res.data;
  },
  create: async (data: Partial<Branch>): Promise<Branch> => {
    const res = await api.post<Branch>('/branches', data);
    return res.data;
  },
  update: async (id: number, data: Partial<Branch>): Promise<Branch> => {
    const res = await api.put<Branch>(`/branches/${id}`, data);
    return res.data;
  },
  delete: async (id: number) => {
    const res = await api.delete(`/branches/${id}`);
    return res.data;
  },
  getDashboard: async (id: number): Promise<BranchDashboard> => {
    const res = await api.get<BranchDashboard>(`/branches/${id}/dashboard`);
    return res.data;
  },
};

export const employeeApi = {
  list: async (params?: { branch_id?: number; role?: string; is_active?: boolean }): Promise<User[]> => {
    const res = await api.get<User[]>('/employees', { params });
    return res.data;
  },
  create: async (data: any): Promise<User> => {
    const res = await api.post<User>('/employees', data);
    return res.data;
  },
  update: async (id: number, data: Partial<User>): Promise<User> => {
    const res = await api.put<User>(`/employees/${id}`, data);
    return res.data;
  },
  getWorkload: async (id: number) => {
    const res = await api.get(`/employees/${id}/workload`);
    return res.data;
  },
  invite: async (id: number): Promise<EmployeeInviteResponse> => {
    const res = await api.post<EmployeeInviteResponse>(`/employees/${id}/invite`);
    return res.data;
  },
  acceptInvite: async (data: {
    invite_token: string;
    new_password: string;
    full_name?: string;
    phone?: string;
  }) => {
    const res = await api.post('/employees/accept-invite', data);
    return res.data;
  },
  getDashboard: async (id: number): Promise<EmployeeDashboard> => {
    const res = await api.get<EmployeeDashboard>(`/employees/${id}/dashboard`);
    return res.data;
  },
};

export const customerApi = {
  list: async (search?: string): Promise<User[]> => {
    const res = await api.get<User[]>('/customers', { params: { search } });
    return res.data;
  },
  get: async (id: number): Promise<User> => {
    const res = await api.get<User>(`/customers/${id}`);
    return res.data;
  },
  getParcels: async (id: number): Promise<Parcel[]> => {
    const res = await api.get<Parcel[]>(`/customers/${id}/parcels`);
    return res.data;
  },
  getMyProfile: async (): Promise<User> => {
    const res = await api.get<User>('/customers/me/profile');
    return res.data;
  },
  updateMyProfile: async (data: CustomerProfileUpdate): Promise<User> => {
    const res = await api.put<User>('/customers/me/profile', data);
    return res.data;
  },
  getMyParcels: async (): Promise<Parcel[]> => {
    const res = await api.get<Parcel[]>('/customers/me/parcels');
    return res.data;
  },
};

export const parcelApi = {
  quote: async (data: {
    weight_kg: number;
    length_cm: number;
    width_cm: number;
    height_cm: number;
    service_type: string;
  }) => {
    const res = await api.post('/parcels/quote', data);
    return res.data;
  },
  book: async (data: any): Promise<Parcel> => {
    const res = await api.post<Parcel>('/parcels', data);
    return res.data;
  },
  list: async (params?: { status?: string; branch_id?: number; search?: string }): Promise<Parcel[]> => {
    const res = await api.get<Parcel[]>('/parcels', { params });
    return res.data;
  },
  get: async (trackingNumber: string): Promise<Parcel> => {
    const res = await api.get<Parcel>(`/parcels/${trackingNumber}`);
    return res.data;
  },
  cancel: async (trackingNumber: string, cancellation_reason: string): Promise<Parcel> => {
    const res = await api.post<Parcel>(`/parcels/${trackingNumber}/cancel`, { cancellation_reason });
    return res.data;
  },
  downloadLabel: async (trackingNumber: string) => {
    const res = await api.get(`/parcels/${trackingNumber}/label`, {
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `shipping_label_${trackingNumber}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  },
};

export const assignmentApi = {
  list: async (params?: { employee_id?: number; status?: string }): Promise<DeliveryAssignment[]> => {
    const res = await api.get<DeliveryAssignment[]>('/assignments', { params });
    return res.data;
  },
  get: async (id: number): Promise<DeliveryAssignment> => {
    const res = await api.get<DeliveryAssignment>(`/assignments/${id}`);
    return res.data;
  },
  create: async (data: {
    parcel_id: number;
    employee_id: number;
    vehicle_id?: number;
    assignment_type: string;
    notes?: string;
  }): Promise<DeliveryAssignment> => {
    const res = await api.post<DeliveryAssignment>('/assignments', data);
    return res.data;
  },
  updateStatus: async (id: number, status: string, notes?: string): Promise<DeliveryAssignment> => {
    const res = await api.put<DeliveryAssignment>(`/assignments/${id}/status`, { status, notes });
    return res.data;
  },
  cancel: async (id: number, cancellation_reason: string): Promise<DeliveryAssignment> => {
    const res = await api.post<DeliveryAssignment>(`/assignments/${id}/cancel`, { cancellation_reason });
    return res.data;
  },
  getSuggestions: async (parcelId: number): Promise<DispatchSuggestionsResponse> => {
    const res = await api.get<DispatchSuggestionsResponse>(`/assignments/suggestions/${parcelId}`);
    return res.data;
  },
};

export const vehicleApi = {
  list: async (params?: { branch_id?: number; status?: string }): Promise<Vehicle[]> => {
    const res = await api.get<Vehicle[]>('/vehicles', { params });
    return res.data;
  },
  create: async (data: Partial<Vehicle>): Promise<Vehicle> => {
    const res = await api.post<Vehicle>('/vehicles', data);
    return res.data;
  },
  update: async (id: number, data: Partial<Vehicle>): Promise<Vehicle> => {
    const res = await api.put<Vehicle>(`/vehicles/${id}`, data);
    return res.data;
  },
  setMaintenance: async (id: number, in_maintenance: boolean, reason?: string): Promise<Vehicle> => {
    const res = await api.patch<Vehicle>(`/vehicles/${id}/maintenance`, { in_maintenance, reason });
    return res.data;
  },
};

export const trackingApi = {
  getPublic: async (trackingNumber: string): Promise<PublicTrackingResponse> => {
    const res = await api.get<PublicTrackingResponse>(`/tracking/public/${trackingNumber}`);
    return res.data;
  },
  updateMilestone: async (trackingNumber: string, data: any) => {
    const res = await api.post(`/tracking/${trackingNumber}/update`, data);
    return res.data;
  },
};

export const custodyApi = {
  scan: async (data: {
    tracking_number: string;
    scan_type: string;
    branch_id?: number;
    latitude?: number;
    longitude?: number;
    notes?: string;
  }) => {
    const res = await api.post('/custody/scan', data);
    return res.data;
  },
  getHistory: async (trackingNumber: string) => {
    const res = await api.get(`/custody/${trackingNumber}/history`);
    return res.data;
  },
};

export const analyticsApi = {
  getDashboard: async (): Promise<DashboardStats> => {
    const res = await api.get<DashboardStats>('/analytics/dashboard');
    return res.data;
  },
  exportCsv: async (params?: { status?: string; branch_id?: number }) => {
    const res = await api.get('/analytics/export/csv', {
      params,
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'logiflows_parcels.csv');
    document.body.appendChild(link);
    link.click();
    link.remove();
  },
};

