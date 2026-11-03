import React from 'react';
import { ParcelStatus, UserRole, VehicleStatus, AssignmentStatus } from '../types';

interface BadgeProps {
  status: string;
  variant?: 'status' | 'role' | 'vehicle' | 'assignment';
}

export const Badge: React.FC<BadgeProps> = ({ status, variant = 'status' }) => {
  const getStyle = () => {
    switch (status) {
      // Parcel Statuses
      case 'BOOKED':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'PICKUP_SCHEDULED':
      case 'PICKED_UP':
        return 'bg-indigo-50 text-indigo-700 border-indigo-200';
      case 'AT_ORIGIN_BRANCH':
      case 'AT_DESTINATION_BRANCH':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'IN_TRANSIT':
      case 'OUT_FOR_DELIVERY':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'DELIVERED':
      case 'COMPLETED':
      case 'PAID':
      case 'AVAILABLE':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'DELIVERY_FAILED':
      case 'CANCELLED':
      case 'RETIRED':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'RETURN_TO_ORIGIN':
      case 'ON_HOLD':
      case 'MAINTENANCE':
        return 'bg-orange-50 text-orange-700 border-orange-200';
      
      // Roles
      case 'SUPER_ADMIN':
        return 'bg-red-50 text-red-700 border-red-200';
      case 'ORG_ADMIN':
        return 'bg-indigo-50 text-indigo-700 border-indigo-200';
      case 'BRANCH_MANAGER':
        return 'bg-cyan-50 text-cyan-700 border-cyan-200';
      case 'DELIVERY_AGENT':
        return 'bg-teal-50 text-teal-700 border-teal-200';
      case 'CUSTOMER':
        return 'bg-slate-100 text-slate-700 border-slate-300';

      default:
        return 'bg-slate-50 text-slate-700 border-slate-200';
    }
  };

  const formatText = (text: string) => {
    return text.replace(/_/g, ' ');
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStyle()}`}
    >
      <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-current opacity-70"></span>
      {formatText(status)}
    </span>
  );
};

