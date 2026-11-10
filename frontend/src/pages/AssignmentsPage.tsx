import React, { useState, useEffect } from 'react';
import { Plus, User, Sparkles, XCircle, AlertTriangle, Truck } from 'lucide-react';
import { assignmentApi, parcelApi, employeeApi, vehicleApi } from '../api';
import { DeliveryAssignment, Parcel, User as UserType, Vehicle, DispatchSuggestionsResponse } from '../types';
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
  const [suggestions, setSuggestions] = useState<DispatchSuggestionsResponse | null>(null);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);

  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [assignmentToCancel, setAssignmentToCancel] = useState<number | null>(null);
  const [cancelReason, setCancelReason] = useState('');
  const [cancelling, setCancelling] = useState(false);

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

  const handleParcelSelect = async (parcelIdStr: string) => {
    setFormData((prev) => ({ ...prev, parcel_id: parcelIdStr }));
    if (!parcelIdStr) {
      setSuggestions(null);
      return;
    }
    const pid = parseInt(parcelIdStr);
    setSuggestionsLoading(true);
    try {
      const res = await assignmentApi.getSuggestions(pid);
      setSuggestions(res);
      // Auto-prefill best scored available agent and vehicle if unselected
      if (res.suggested_employees.length > 0 && res.suggested_employees[0].is_available) {
        setFormData((prev) => ({
          ...prev,
          employee_id: res.suggested_employees[0].employee_id.toString(),
        }));
      }
      if (res.suggested_vehicles.length > 0 && res.suggested_vehicles[0].fits_capacity) {
        setFormData((prev) => ({
          ...prev,
          vehicle_id: res.suggested_vehicles[0].vehicle_id.toString(),
        }));
      }
    } catch (err) {
      console.error('Failed to load dispatch suggestions', err);
      setSuggestions(null);
    } finally {
      setSuggestionsLoading(false);
    }
  };

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
      setSuggestions(null);
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

  const handleOpenCancelModal = (id: number) => {
    setAssignmentToCancel(id);
    setCancelReason('');
    setCancelModalOpen(true);
  };

  const handleConfirmCancel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignmentToCancel || !cancelReason.trim()) return;
    setCancelling(true);
    try {
      await assignmentApi.cancel(assignmentToCancel, cancelReason);
      setCancelModalOpen(false);
      setAssignmentToCancel(null);
      setCancelReason('');
      loadData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to cancel assignment');
    } finally {
      setCancelling(false);
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
                    <td className="py-4 px-6 text-right space-x-2 whitespace-nowrap">
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
                      {(a.status === 'ASSIGNED' || a.status === 'IN_PROGRESS') && isStaff && (
                        <button
                          onClick={() => handleOpenCancelModal(a.id)}
                          className="px-2.5 py-1 rounded-lg bg-rose-50 text-rose-700 hover:bg-rose-100 font-semibold text-[11px] transition-colors inline-flex items-center gap-1"
                        >
                          <XCircle className="w-3 h-3" />
                          <span>Cancel Run</span>
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
      <Modal isOpen={isModalOpen} onClose={() => { setIsModalOpen(false); setSuggestions(null); }} title="Assign Parcel to Delivery Agent">
        <form onSubmit={handleCreateAssignment} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Select Consignment *</label>
            <select
              required
              value={formData.parcel_id}
              onChange={(e) => handleParcelSelect(e.target.value)}
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

          {suggestionsLoading && (
            <div className="p-3 bg-indigo-50/50 rounded-xl text-xs text-indigo-600 flex items-center gap-2 animate-pulse">
              <Sparkles className="w-4 h-4 animate-spin" />
              <span>Analyzing dispatch workload and capacity recommendations...</span>
            </div>
          )}

          {suggestions && (
            <div className="bg-indigo-50/70 border border-indigo-200/80 rounded-xl p-3.5 space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-bold text-indigo-950 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                  Dispatch Intelligence: {suggestions.branch_name}
                </span>
                <span className="text-[11px] font-semibold text-indigo-700">
                  Parcel: {suggestions.parcel_weight_kg} kg
                </span>
              </div>
              <p className="text-[11px] text-slate-600 font-medium">
                {suggestions.summary_recommendation}
              </p>

              {suggestions.suggested_employees.length > 0 && (
                <div className="space-y-1 pt-1">
                  <p className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Recommended Delivery Agents</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                    {suggestions.suggested_employees.slice(0, 2).map((emp) => (
                      <button
                        type="button"
                        key={emp.employee_id}
                        onClick={() => setFormData((prev) => ({ ...prev, employee_id: emp.employee_id.toString() }))}
                        className={`p-2 rounded-lg text-left border transition-all ${
                          formData.employee_id === emp.employee_id.toString()
                            ? 'bg-indigo-100 border-indigo-400 font-bold text-indigo-900 shadow-2xs'
                            : 'bg-white/80 border-slate-200 text-slate-700 hover:bg-white'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-xs">{emp.full_name}</span>
                          <span className="text-[10px] text-indigo-600 font-mono">Score {emp.score}</span>
                        </div>
                        <p className="text-[10px] text-slate-500 mt-0.5">{emp.explanation}</p>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {suggestions.suggested_vehicles.length > 0 && (
                <div className="space-y-1 pt-1">
                  <p className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Fleet Payload Capacity Fit</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                    {suggestions.suggested_vehicles.slice(0, 2).map((v) => (
                      <button
                        type="button"
                        key={v.vehicle_id}
                        onClick={() => setFormData((prev) => ({ ...prev, vehicle_id: v.vehicle_id.toString() }))}
                        className={`p-2 rounded-lg text-left border transition-all ${
                          formData.vehicle_id === v.vehicle_id.toString()
                            ? 'bg-indigo-100 border-indigo-400 font-bold text-indigo-900 shadow-2xs'
                            : 'bg-white/80 border-slate-200 text-slate-700 hover:bg-white'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-xs font-mono">{v.vehicle_number}</span>
                          <span className="text-[10px] text-emerald-600 font-semibold">{v.weight_utilization_pct}% load</span>
                        </div>
                        <p className="text-[10px] text-slate-500 mt-0.5">{v.explanation}</p>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

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

      {/* Cancel Assignment Modal */}
      <Modal
        isOpen={cancelModalOpen}
        onClose={() => { setCancelModalOpen(false); setAssignmentToCancel(null); }}
        title="Cancel Delivery Assignment"
      >
        <form onSubmit={handleConfirmCancel} className="space-y-4">
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Cancelling will release assigned fleet resources</p>
              <p className="text-[11px] text-amber-700 mt-0.5">
                The parcel will revert to the sorting hub inventory, and the fleet vehicle status will be restored to Available.
              </p>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
              Cancellation Reason *
            </label>
            <textarea
              required
              rows={3}
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="Provide a clear operational reason (e.g., Delivery vehicle breakdown, Route rescheduling requested)..."
              className="w-full px-3 py-2 border rounded-xl text-xs"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => { setCancelModalOpen(false); setAssignmentToCancel(null); }}
              className="px-4 py-2 border border-slate-200 rounded-xl text-xs font-medium text-slate-700 hover:bg-slate-50"
            >
              Dismiss
            </button>
            <button
              type="submit"
              disabled={cancelling || !cancelReason.trim()}
              className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs shadow-sm disabled:opacity-50"
            >
              {cancelling ? 'Cancelling...' : 'Confirm Cancellation'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

