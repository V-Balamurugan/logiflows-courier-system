export type UserRole = 
  | 'SUPER_ADMIN' 
  | 'ORG_ADMIN' 
  | 'BRANCH_MANAGER' 
  | 'DELIVERY_AGENT' 
  | 'CUSTOMER';

export type ParcelStatus = 
  | 'BOOKED'
  | 'PICKUP_SCHEDULED'
  | 'PICKED_UP'
  | 'AT_ORIGIN_BRANCH'
  | 'IN_TRANSIT'
  | 'AT_DESTINATION_BRANCH'
  | 'OUT_FOR_DELIVERY'
  | 'DELIVERED'
  | 'DELIVERY_FAILED'
  | 'RETURN_TO_ORIGIN'
  | 'CANCELLED'
  | 'ON_HOLD';

export type ServiceType = 'STANDARD' | 'EXPRESS' | 'SAME_DAY' | 'OVERNIGHT';
export type PaymentStatus = 'PENDING' | 'PAID' | 'REFUNDED';
export type VehicleType = 'BIKE' | 'VAN' | 'TRUCK';
export type VehicleStatus = 'AVAILABLE' | 'ASSIGNED' | 'IN_TRANSIT' | 'MAINTENANCE' | 'RETIRED';
export type AssignmentType = 'PICKUP' | 'TRANSFER' | 'LAST_MILE';
export type AssignmentStatus = 'ASSIGNED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';
export type ScanType = 
  | 'PICKUP_VERIFICATION' 
  | 'ORIGIN_INWARD' 
  | 'HUB_OUTWARD' 
  | 'DEST_INWARD' 
  | 'OUT_FOR_DELIVERY' 
  | 'DELIVERY_CONFIRMATION';

export interface User {
  id: number;
  email: string;
  full_name: string;
  phone?: string;
  role: UserRole;
  is_active: boolean;
  organization_id?: number;
  branch_id?: number;
  customer_profile?: {
    company_name?: string;
    gst_number?: string;
    default_pickup_address?: string;
    default_delivery_address?: string;
  };
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user_id: number;
  email: string;
  full_name: string;
  role: UserRole;
  organization_id?: number;
  branch_id?: number;
}

export interface Branch {
  id: number;
  organization_id: number;
  branch_code: string;
  branch_name: string;
  address: string;
  pincode: string;
  city: string;
  state: string;
  country: string;
  contact_email: string;
  contact_phone: string;
  latitude?: number;
  longitude?: number;
  operating_status: 'ACTIVE' | 'INACTIVE' | 'UNDER_MAINTENANCE';
  is_active: boolean;
  created_at: string;
}

export interface Vehicle {
  id: number;
  organization_id: number;
  branch_id?: number;
  vehicle_number: string;
  vehicle_type: VehicleType;
  model?: string;
  max_weight_kg: number;
  max_volume_cbm?: number;
  status: VehicleStatus;
  assigned_employee_id?: number;
  is_active: boolean;
  created_at: string;
}

export interface TrackingEvent {
  id: number;
  status: ParcelStatus;
  location_name?: string;
  remarks?: string;
  created_at: string;
}

export interface Parcel {
  id: number;
  tracking_number: string;
  customer_id?: number;
  origin_branch_id: number;
  dest_branch_id: number;
  sender_name: string;
  sender_phone: string;
  sender_email?: string;
  sender_address: string;
  sender_city: string;
  sender_state: string;
  sender_pincode: string;
  receiver_name: string;
  receiver_phone: string;
  receiver_email?: string;
  receiver_address: string;
  receiver_city: string;
  receiver_state: string;
  receiver_pincode: string;
  weight_kg: number;
  length_cm: number;
  width_cm: number;
  height_cm: number;
  volumetric_weight_kg: number;
  service_type: ServiceType;
  base_charge: number;
  weight_charge: number;
  service_charge: number;
  tax_amount: number;
  total_charge: number;
  payment_status: PaymentStatus;
  delivery_status: ParcelStatus;
  current_location?: string;
  qr_code_data?: string;
  notes?: string;
  booking_date: string;
  expected_delivery_date?: string;
  actual_delivery_date?: string;
  cancellation_reason?: string;
  tracking_history?: TrackingEvent[];
}

export interface DeliveryAssignment {
  id: number;
  parcel_id: number;
  employee_id: number;
  vehicle_id?: number;
  assignment_type: AssignmentType;
  status: AssignmentStatus;
  notes?: string;
  assigned_at: string;
  completed_at?: string;
  employee_name?: string;
  tracking_number?: string;
  vehicle_number?: string;
}

export interface PublicTrackingResponse {
  tracking_number: string;
  status: ParcelStatus;
  origin_city: string;
  destination_city: string;
  booking_date: string;
  expected_delivery_date?: string;
  actual_delivery_date?: string;
  origin_lat?: number;
  origin_lng?: number;
  dest_lat?: number;
  dest_lng?: number;
  current_lat?: number;
  current_lng?: number;
  current_location?: string;
  milestones: {
    status: ParcelStatus;
    location?: string;
    remarks?: string;
    timestamp: string;
  }[];
}

export interface DashboardStats {
  role: string;
  total_parcels: number;
  pending_deliveries: number;
  delivered_parcels: number;
  failed_deliveries: number;
  active_employees: number;
  available_vehicles: number;
  delivery_success_rate: number;
  status_breakdown: { status: string; count: number }[];
  branch_performance: {
    branch_id: number;
    branch_name: string;
    branch_code: string;
    parcels_handled: number;
    deliveries_completed: number;
  }[];
}

