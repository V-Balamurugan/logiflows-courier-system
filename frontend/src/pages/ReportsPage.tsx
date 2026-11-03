import React, { useState, useEffect } from 'react';
import { FileSpreadsheet, Download, Filter, Search, Calendar } from 'lucide-react';
import { analyticsApi, parcelApi, branchApi } from '../api';
import { Parcel, Branch } from '../types';
import { Badge } from '../components/Badge';

export const ReportsPage: React.FC = () => {
  const [parcels, setParcels] = useState<Parcel[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [branchFilter, setBranchFilter] = useState('');
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [pData, bData] = await Promise.all([
        parcelApi.list({
          status: statusFilter || undefined,
          branch_id: branchFilter ? parseInt(branchFilter) : undefined,
        }),
        branchApi.list(),
      ]);
      setParcels(pData);
      setBranches(bData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [statusFilter, branchFilter]);

  const handleExportCsv = async () => {
    try {
      await analyticsApi.exportCsv({
        status: statusFilter || undefined,
        branch_id: branchFilter ? parseInt(branchFilter) : undefined,
      });
    } catch (err) {
      alert('Error exporting CSV');
    }
  };

  const totalRevenue = parcels.reduce((sum, p) => sum + p.total_charge, 0);
  const totalWeight = parcels.reduce((sum, p) => sum + p.weight_kg, 0);

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Reports & Operational Analytics</h1>
          <p className="text-xs text-slate-500 mt-1">
            Generate audit logs, review branch billing metrics, and download CSV spreadsheets.
          </p>
        </div>

        <button
          onClick={handleExportCsv}
          className="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs shadow-sm flex items-center gap-2 transition-all self-start sm:self-auto"
        >
          <Download className="w-4 h-4" />
          <span>Export Filtered CSV</span>
        </button>
      </div>

      {/* Summary KPI Pills */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-2xs">
          <p className="text-[11px] font-semibold text-slate-500 uppercase">Filtered Volume</p>
          <p className="text-xl font-bold text-slate-900 mt-0.5">{parcels.length} Consignments</p>
        </div>
        <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-2xs">
          <p className="text-[11px] font-semibold text-slate-500 uppercase">Total Revenue Generated</p>
          <p className="text-xl font-bold text-indigo-600 mt-0.5">₹{totalRevenue.toFixed(2)}</p>
        </div>
        <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-2xs">
          <p className="text-[11px] font-semibold text-slate-500 uppercase">Total Freight Tonnage</p>
          <p className="text-xl font-bold text-slate-900 mt-0.5">{totalWeight.toFixed(1)} kg</p>
        </div>
      </div>

      {/* Filter toolbar */}
      <div className="flex flex-col sm:flex-row gap-4 bg-white p-4 rounded-2xl border border-slate-200 shadow-2xs">
        <div className="flex items-center gap-2 sm:w-64">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs"
          >
            <option value="">All Delivery Statuses</option>
            <option value="BOOKED">Booked</option>
            <option value="PICKED_UP">Picked Up</option>
            <option value="AT_ORIGIN_BRANCH">At Origin Branch</option>
            <option value="IN_TRANSIT">In Transit</option>
            <option value="AT_DESTINATION_BRANCH">At Destination Hub</option>
            <option value="OUT_FOR_DELIVERY">Out for Delivery</option>
            <option value="DELIVERED">Delivered</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>

        <div className="flex items-center gap-2 sm:w-64">
          <select
            value={branchFilter}
            onChange={(e) => setBranchFilter(e.target.value)}
            className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs"
          >
            <option value="">All Branch Hubs</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.branch_name} ({b.branch_code})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 uppercase font-semibold">
                <th className="py-3.5 px-6">Tracking #</th>
                <th className="py-3.5 px-4">Booking Date</th>
                <th className="py-3.5 px-4">Sender City</th>
                <th className="py-3.5 px-4">Destination City</th>
                <th className="py-3.5 px-4">Service</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-6 text-right">Revenue (INR)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {parcels.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50/80">
                  <td className="py-3.5 px-6 font-bold text-slate-900">{p.tracking_number}</td>
                  <td className="py-3.5 px-4 text-slate-500">{p.booking_date.slice(0, 10)}</td>
                  <td className="py-3.5 px-4 text-slate-700">{p.sender_city}</td>
                  <td className="py-3.5 px-4 text-slate-700">{p.receiver_city}</td>
                  <td className="py-3.5 px-4 text-slate-600">{p.service_type}</td>
                  <td className="py-3.5 px-4">
                    <Badge status={p.delivery_status} />
                  </td>
                  <td className="py-3.5 px-6 text-right font-bold text-slate-900">₹{p.total_charge}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

