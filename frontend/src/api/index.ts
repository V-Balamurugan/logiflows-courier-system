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
} from '../types';

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

