import React, { useState, useEffect } from 'react';
import { Truck, Plus, Search, CheckCircle2, Wrench, ShieldAlert } from 'lucide-react';
import { vehicleApi, branchApi } from '../api';
import { Vehicle, Branch } from '../types';
import { Modal } from '../components/Modal';
import { Badge } from '../components/Badge';

export const VehiclesPage: React.FC = () => {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    vehicle_number: '',
    vehicle_type: 'VAN' as const,
    model: '',
    max_weight_kg: '500',
    max_volume_cbm: '6',
    status: 'AVAILABLE' as const,
    branch_id: '',
  });

  const loadData = async () => {
    setLoading(true);
    try {
      const [vData, bData] = await Promise.all([
        vehicleApi.list(),
        branchApi.list(),
      ]);
      setVehicles(vData);
      setBranches(bData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateVehicle = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await vehicleApi.create({
        vehicle_number: formData.vehicle_number,
        vehicle_type: formData.vehicle_type,
        model: formData.model || undefined,
        max_weight_kg: parseFloat(formData.max_weight_kg),
        max_volume_cbm: formData.max_volume_cbm ? parseFloat(formData.max_volume_cbm) : undefined,
        status: formData.status,
        branch_id: formData.branch_id ? parseInt(formData.branch_id) : undefined,
      });
      setIsModalOpen(false);
      setFormData({
        vehicle_number: '',
        vehicle_type: 'VAN',
        model: '',
        max_weight_kg: '500',
        max_volume_cbm: '6',
        status: 'AVAILABLE',
        branch_id: '',
      });
      loadData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error adding vehicle. Check vehicle number uniqueness.');
    }
  };

  const handleToggleMaintenance = async (v: Vehicle) => {
    const nextStatus = v.status === 'MAINTENANCE' ? 'AVAILABLE' : 'MAINTENANCE';
    try {
      await vehicleApi.update(v.id, { status: nextStatus });
      loadData();
    } catch (err) {
      alert('Error updating status');
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Fleet & Vehicle Management</h1>
          <p className="text-xs text-slate-500 mt-1">
            Manage delivery vehicles, capacity limits, branch fleet allocation, and maintenance records.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-sm flex items-center gap-2 transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Register Vehicle</span>
        </button>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 uppercase font-semibold">
                <th className="py-3.5 px-6">Vehicle Registration</th>
                <th className="py-3.5 px-4">Type & Model</th>
                <th className="py-3.5 px-4">Max Weight Payload</th>
                <th className="py-3.5 px-4">Assigned Branch Hub</th>
                <th className="py-3.5 px-4">Fleet Status</th>
                <th className="py-3.5 px-6 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {vehicles.map((v) => {
                const branchObj = branches.find((b) => b.id === v.branch_id);
                return (
                  <tr key={v.id} className="hover:bg-slate-50/80">
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold">
                          <Truck className="w-4 h-4" />
                        </div>
                        <div>
                          <p className="font-bold text-slate-900 font-mono text-sm">{v.vehicle_number}</p>
                          <p className="text-[11px] text-slate-500">{v.model || 'Standard Edition'}</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-4 px-4 text-slate-700 font-semibold">{v.vehicle_type}</td>
                    <td className="py-4 px-4 text-slate-600 font-medium">
                      {v.max_weight_kg} kg / {v.max_volume_cbm || 0} cbm
                    </td>
                    <td className="py-4 px-4 text-slate-600">
                      {branchObj ? `${branchObj.branch_name} (${branchObj.city})` : 'Central Pool'}
                    </td>
                    <td className="py-4 px-4">
                      <Badge status={v.status} />
                    </td>
                    <td className="py-4 px-6 text-right">
                      <button
                        onClick={() => handleToggleMaintenance(v)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                          v.status === 'MAINTENANCE'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                            : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                        }`}
                      >
                        {v.status === 'MAINTENANCE' ? 'Set Available' : 'Send to Maintenance'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Register Vehicle Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Register Fleet Vehicle">
        <form onSubmit={handleCreateVehicle} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Registration # *</label>
            <input
              type="text"
              required
              placeholder="e.g. MH-02-CB-1234"
              value={formData.vehicle_number}
              onChange={(e) => setFormData({ ...formData, vehicle_number: e.target.value })}
              className="w-full px-3 py-2 border rounded-xl text-xs uppercase"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Vehicle Type *</label>
              <select
                value={formData.vehicle_type}
                onChange={(e) => setFormData({ ...formData, vehicle_type: e.target.value as any })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              >
                <option value="BIKE">Two-Wheeler (Bike)</option>
                <option value="VAN">Cargo Van</option>
                <option value="TRUCK">Heavy Truck</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Model Name</label>
              <input
                type="text"
                placeholder="e.g. Tata Winger / Eicher"
                value={formData.model}
                onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Max Weight (kg) *</label>
              <input
                type="number"
                required
                min="10"
                value={formData.max_weight_kg}
                onChange={(e) => setFormData({ ...formData, max_weight_kg: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Volume (CBM)</label>
              <input
                type="number"
                step="0.1"
                value={formData.max_volume_cbm}
                onChange={(e) => setFormData({ ...formData, max_volume_cbm: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Assign to Branch Hub</label>
            <select
              value={formData.branch_id}
              onChange={(e) => setFormData({ ...formData, branch_id: e.target.value })}
              className="w-full px-3 py-2 border rounded-xl text-xs"
            >
              <option value="">Central Headquarters Pool</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.branch_name} ({b.city})
                </option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-md mt-4"
          >
            Save Vehicle
          </button>
        </form>
      </Modal>
    </div>
  );
};

