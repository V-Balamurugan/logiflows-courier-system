import React, { useState, useEffect } from 'react';
import { GitBranch, Plus, Search, MapPin, Phone, Mail, Edit2, Trash2 } from 'lucide-react';
import { branchApi } from '../api';
import { Branch } from '../types';
import { Modal } from '../components/Modal';
import { Badge } from '../components/Badge';

export const BranchesPage: React.FC = () => {
  const [branches, setBranches] = useState<Branch[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    branch_code: '',
    branch_name: '',
    address: '',
    pincode: '',
    city: '',
    state: '',
    country: 'India',
    contact_email: '',
    contact_phone: '',
    latitude: '',
    longitude: '',
    operating_status: 'ACTIVE' as const,
  });

  const loadBranches = async () => {
    setLoading(true);
    try {
      const data = await branchApi.list({ search });
      setBranches(data);
    } catch (err) {
      console.error('Failed to load branches', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBranches();
  }, [search]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await branchApi.create({
        ...formData,
        latitude: formData.latitude ? parseFloat(formData.latitude) : undefined,
        longitude: formData.longitude ? parseFloat(formData.longitude) : undefined,
      });
      setIsModalOpen(false);
      setFormData({
        branch_code: '',
        branch_name: '',
        address: '',
        pincode: '',
        city: '',
        state: '',
        country: 'India',
        contact_email: '',
        contact_phone: '',
        latitude: '',
        longitude: '',
        operating_status: 'ACTIVE',
      });
      loadBranches();
    } catch (err) {
      alert('Error creating branch. Ensure branch code is unique.');
    }
  };

  const handleDeactivate = async (id: number) => {
    if (confirm('Are you sure you want to deactivate this branch?')) {
      await branchApi.delete(id);
      loadBranches();
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Branch Management</h1>
          <p className="text-xs text-slate-500 mt-1">
            Configure regional physical sorting hubs, GPS dispatch locations, and branch staff.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-sm flex items-center gap-2 transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Add New Branch</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex items-center gap-4 bg-white p-4 rounded-2xl border border-slate-200 shadow-2xs">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search branches by code, name, city..."
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
          />
        </div>
      </div>

      {/* Branches Table */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 uppercase font-semibold">
                <th className="py-3.5 px-6">Branch Code & Name</th>
                <th className="py-3.5 px-4">Location</th>
                <th className="py-3.5 px-4">Contact Details</th>
                <th className="py-3.5 px-4">Coordinates (Lat / Lng)</th>
                <th className="py-3.5 px-4">Operating Status</th>
                <th className="py-3.5 px-6 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {branches.map((b) => (
                <tr key={b.id} className="hover:bg-slate-50/80">
                  <td className="py-4 px-6">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold">
                        <GitBranch className="w-4 h-4" />
                      </div>
                      <div>
                        <p className="font-bold text-slate-900">{b.branch_name}</p>
                        <p className="text-[11px] font-mono text-slate-500">{b.branch_code}</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-4 px-4 text-slate-600">
                    <p>{b.city}, {b.state}</p>
                    <p className="text-[11px] text-slate-400">{b.pincode}</p>
                  </td>
                  <td className="py-4 px-4 text-slate-600 space-y-0.5">
                    <p className="flex items-center gap-1.5 text-[11px]">
                      <Mail className="w-3 h-3 text-slate-400" /> {b.contact_email}
                    </p>
                    <p className="flex items-center gap-1.5 text-[11px]">
                      <Phone className="w-3 h-3 text-slate-400" /> {b.contact_phone}
                    </p>
                  </td>
                  <td className="py-4 px-4 text-slate-500 font-mono text-[11px]">
                    {b.latitude && b.longitude ? `${b.latitude.toFixed(4)}, ${b.longitude.toFixed(4)}` : 'Not set'}
                  </td>
                  <td className="py-4 px-4">
                    <Badge status={b.operating_status} />
                  </td>
                  <td className="py-4 px-6 text-right">
                    <button
                      onClick={() => handleDeactivate(b.id)}
                      className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                      title="Deactivate branch"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Branch Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Add Physical Hub / Branch">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Branch Code *</label>
              <input
                type="text"
                required
                placeholder="e.g. BOM-002"
                value={formData.branch_code}
                onChange={(e) => setFormData({ ...formData, branch_code: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Branch Name *</label>
              <input
                type="text"
                required
                placeholder="e.g. Mumbai South Hub"
                value={formData.branch_name}
                onChange={(e) => setFormData({ ...formData, branch_name: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Street Address *</label>
            <textarea
              rows={2}
              required
              placeholder="Plot No, Industrial Estate, Landmark"
              value={formData.address}
              onChange={(e) => setFormData({ ...formData, address: e.target.value })}
              className="w-full px-3 py-2 border rounded-xl text-xs"
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-[11px] font-semibold uppercase text-slate-700 mb-1">Pincode *</label>
              <input
                type="text"
                required
                placeholder="400001"
                value={formData.pincode}
                onChange={(e) => setFormData({ ...formData, pincode: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold uppercase text-slate-700 mb-1">City *</label>
              <input
                type="text"
                required
                placeholder="Mumbai"
                value={formData.city}
                onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold uppercase text-slate-700 mb-1">State *</label>
              <input
                type="text"
                required
                placeholder="Maharashtra"
                value={formData.state}
                onChange={(e) => setFormData({ ...formData, state: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Email *</label>
              <input
                type="email"
                required
                placeholder="hub@logiflows.com"
                value={formData.contact_email}
                onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Phone *</label>
              <input
                type="text"
                required
                placeholder="+91 98765 00000"
                value={formData.contact_phone}
                onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Latitude</label>
              <input
                type="number"
                step="0.0001"
                placeholder="e.g. 19.0760"
                value={formData.latitude}
                onChange={(e) => setFormData({ ...formData, latitude: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Longitude</label>
              <input
                type="number"
                step="0.0001"
                placeholder="e.g. 72.8777"
                value={formData.longitude}
                onChange={(e) => setFormData({ ...formData, longitude: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              />
            </div>
          </div>

          <button
            type="submit"
            className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-md mt-4"
          >
            Create Branch
          </button>
        </form>
      </Modal>
    </div>
  );
};

