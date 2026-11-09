import React, { useState, useEffect } from 'react';
import { Plus, User } from 'lucide-react';
import { assignmentApi, parcelApi, employeeApi, vehicleApi } from '../api';
import { DeliveryAssignment, Parcel, User as UserType, Vehicle } from '../types';
import { useAuth } from '../contexts/AuthContext';
import { Modal } from '../components/Modal';
import { Badge } from '../components/Badge';

export const AssignmentsPage: React.FC = () => {
  const { user } = useAuth();
  const [assignments, setAssignments] = useState<DeliveryAssignment[]>([]);
  const [parcels, setParcels] = useState<Parcel[]>([]);
  const [employees, setEmployees] = useState<UserType[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [loading, setLoading] = useState(true);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    parcel_id: '',
    employee_id: '',
    vehicle_id: '',
    assignment_type: 'LAST_MILE',
    notes: '',
  });

  const loadData = async () => {
    setLoading(true);
    try {
      const [assignData, parcelData, empData, vehData] = await Promise.all([
        assignmentApi.list(),
        parcelApi.list({ status: '' }),
        employeeApi.list(),
        vehicleApi.list(),
      ]);
      setAssignments(assignData);
      setParcels(parcelData);
      setEmployees(empData.filter((e) => e.role === 'DELIVERY_AGENT' || e.role === 'BRANCH_MANAGER'));
      setVehicles(vehData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateAssignment = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await assignmentApi.create({
        parcel_id: parseInt(formData.parcel_id),
        employee_id: parseInt(formData.employee_id),
        vehicle_id: formData.vehicle_id ? parseInt(formData.vehicle_id) : undefined,
        assignment_type: formData.assignment_type,
        notes: formData.notes || undefined,
      });
      setIsModalOpen(false);
      setFormData({
        parcel_id: '',
        employee_id: '',
        vehicle_id: '',
        assignment_type: 'LAST_MILE',
        notes: '',
      });
      loadData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create assignment');
    }
  };

  const handleUpdateStatus = async (id: number, status: string) => {
    try {
      await assignmentApi.updateStatus(id, status);
      loadData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update assignment status');
    }
  };

  const isStaff = user?.role !== 'DELIVERY_AGENT' && user?.role !== 'CUSTOMER';

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Delivery Assignments</h1>
          <p className="text-xs text-slate-500 mt-1">
            Dispatch consignments to delivery agents, pair with fleet vehicles, and monitor route runs.
          </p>
        </div>

        {isStaff && (
          <button
            onClick={() => setIsModalOpen(true)}
            className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-sm flex items-center gap-2 transition-all self-start sm:self-auto"
          >
            <Plus className="w-4 h-4" />
            <span>Create Assignment</span>
          </button>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 uppercase font-semibold">
                <th className="py-3.5 px-6">Assignment #</th>
                <th className="py-3.5 px-4">Tracking Number</th>
                <th className="py-3.5 px-4">Assigned Agent</th>
                <th className="py-3.5 px-4">Vehicle Used</th>
                <th className="py-3.5 px-4">Type</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-6 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    Loading assignments...
                  </td>
                </tr>
              ) : assignments.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    No active assignments found.
                  </td>
                </tr>
              ) : (
                assignments.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50/80">
                    <td className="py-4 px-6 font-bold text-slate-900">
                      ASN-{a.id.toString().padStart(4, '0')}
                    </td>
                    <td className="py-4 px-4 font-bold text-indigo-600">
                      {a.tracking_number || `Parcel #${a.parcel_id}`}
                    </td>
                    <td className="py-4 px-4 text-slate-800 font-semibold flex items-center gap-1.5">
                      <User className="w-3.5 h-3.5 text-slate-400" />
                      <span>{a.employee_name || `Agent #${a.employee_id}`}</span>
                    </td>
                    <td className="py-4 px-4 text-slate-600">
                      {a.vehicle_number ? (
                        <span className="font-mono bg-slate-100 px-2 py-0.5 rounded text-[11px]">
                          {a.vehicle_number}
                        </span>
                      ) : (
                        <span className="text-slate-400">Self / Standard</span>
                      )}
                    </td>
                    <td className="py-4 px-4 text-slate-600">{a.assignment_type}</td>
                    <td className="py-4 px-4">
                      <Badge status={a.status} />
                    </td>
                    <td className="py-4 px-6 text-right space-x-2">
                      {a.status === 'ASSIGNED' && (
                        <button
                          onClick={() => handleUpdateStatus(a.id, 'IN_PROGRESS')}
                          className="px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 font-semibold text-[11px] transition-colors"
                        >
                          Start Run
                        </button>
                      )}
                      {a.status === 'IN_PROGRESS' && (
                        <button
                          onClick={() => handleUpdateStatus(a.id, 'COMPLETED')}
                          className="px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 font-semibold text-[11px] transition-colors"
                        >
                          Mark Delivered
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Assignment Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Assign Parcel to Delivery Agent">
        <form onSubmit={handleCreateAssignment} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Select Consignment *</label>
            <select
              required
              value={formData.parcel_id}
              onChange={(e) => setFormData({ ...formData, parcel_id: e.target.value })}
              className="w-full px-3 py-2 border rounded-xl text-xs"
            >
              <option value="">Select parcel tracking number...</option>
              {parcels
                .filter((p) => p.delivery_status !== 'DELIVERED' && p.delivery_status !== 'CANCELLED')
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.tracking_number} ({p.receiver_name} - {p.receiver_city})
                  </option>
                ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Select Delivery Agent *</label>
            <select
              required
              value={formData.employee_id}
              onChange={(e) => setFormData({ ...formData, employee_id: e.target.value })}
              className="w-full px-3 py-2 border rounded-xl text-xs"
            >
              <option value="">Select delivery agent...</option>
              {employees.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.full_name} ({e.email})
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Fleet Vehicle (Optional)</label>
              <select
                value={formData.vehicle_id}
                onChange={(e) => setFormData({ ...formData, vehicle_id: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              >
                <option value="">No vehicle / Two-wheeler</option>
                {vehicles
                  .filter((v) => v.status === 'AVAILABLE')
                  .map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.vehicle_number} ({v.model || v.vehicle_type})
                    </option>
                  ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Assignment Type *</label>
              <select
                value={formData.assignment_type}
                onChange={(e) => setFormData({ ...formData, assignment_type: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              >
                <option value="LAST_MILE">Last Mile Delivery</option>
                <option value="PICKUP">Doorstep Pickup</option>
                <option value="TRANSFER">Inter-Branch Trunk Transfer</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Dispatcher Instructions</label>
            <textarea
              rows={2}
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              placeholder="e.g. Call customer 10 mins prior to delivery"
              className="w-full px-3 py-2 border rounded-xl text-xs"
            />
          </div>

          <button
            type="submit"
            className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-md mt-4"
          >
            Confirm Assignment & Dispatch
          </button>
        </form>
      </Modal>
    </div>
  );
};

