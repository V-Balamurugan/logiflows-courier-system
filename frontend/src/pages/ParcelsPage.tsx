import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Package, Search, Filter, Download, Eye, XCircle, ArrowUpRight } from 'lucide-react';
import { parcelApi } from '../api';
import { Parcel } from '../types';
import { Badge } from '../components/Badge';
import { Modal } from '../components/Modal';

export const ParcelsPage: React.FC = () => {
  const [parcels, setParcels] = useState<Parcel[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);

  // Cancellation modal state
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [selectedParcel, setSelectedParcel] = useState<Parcel | null>(null);
  const [cancellationReason, setCancellationReason] = useState('');

  const loadParcels = async () => {
    setLoading(true);
    try {
      const data = await parcelApi.list({
        search,
        status: statusFilter || undefined,
      });
      setParcels(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadParcels();
  }, [search, statusFilter]);

  const handleDownloadLabel = async (trackingNo: string) => {
    try {
      await parcelApi.downloadLabel(trackingNo);
    } catch (err) {
      alert('Failed to download shipping label PDF.');
    }
  };

  const handleCancelSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedParcel) return;
    try {
      await parcelApi.cancel(selectedParcel.tracking_number, cancellationReason);
      setCancelModalOpen(false);
      setCancellationReason('');
      loadParcels();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to cancel parcel');
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Shipment Management</h1>
          <p className="text-xs text-slate-500 mt-1">
            Master registry of all booked, in-transit, and completed courier consignments.
          </p>
        </div>

        <Link
          to="/book-parcel"
          className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-sm flex items-center gap-2 transition-all self-start sm:self-auto"
        >
          <Package className="w-4 h-4" />
          <span>New Parcel Booking</span>
        </Link>
      </div>

      {/* Filter and Search Toolbar */}
      <div className="flex flex-col sm:flex-row gap-4 bg-white p-4 rounded-2xl border border-slate-200 shadow-2xs">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search tracking #, sender, recipient, destination city..."
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2 sm:w-64">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
          >
            <option value="">All Statuses</option>
            <option value="BOOKED">Booked</option>
            <option value="PICKUP_SCHEDULED">Pickup Scheduled</option>
            <option value="PICKED_UP">Picked Up</option>
            <option value="AT_ORIGIN_BRANCH">At Origin Branch</option>
            <option value="IN_TRANSIT">In Transit</option>
            <option value="AT_DESTINATION_BRANCH">At Destination Hub</option>
            <option value="OUT_FOR_DELIVERY">Out for Delivery</option>
            <option value="DELIVERED">Delivered</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>
      </div>

      {/* Parcels Table */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 uppercase font-semibold">
                <th className="py-3.5 px-6">Tracking # & Service</th>
                <th className="py-3.5 px-4">From (Origin)</th>
                <th className="py-3.5 px-4">To (Destination)</th>
                <th className="py-3.5 px-4">Weight / Dimensions</th>
                <th className="py-3.5 px-4">Delivery Status</th>
                <th className="py-3.5 px-4">Total Charge</th>
                <th className="py-3.5 px-6 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {parcels.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    No shipments match the selected criteria.
                  </td>
                </tr>
              ) : (
                parcels.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/80">
                    <td className="py-4 px-6">
                      <Link
                        to={`/parcels/${p.tracking_number}`}
                        className="font-bold text-slate-900 hover:text-indigo-600 flex items-center gap-1.5"
                      >
                        <span>{p.tracking_number}</span>
                        <ArrowUpRight className="w-3 h-3 text-slate-400" />
                      </Link>
                      <p className="text-[11px] text-slate-500 mt-0.5">{p.service_type}</p>
                    </td>
                    <td className="py-4 px-4 text-slate-600">
                      <p className="font-semibold text-slate-800">{p.sender_name}</p>
                      <p className="text-[11px] text-slate-400">{p.sender_city}</p>
                    </td>
                    <td className="py-4 px-4 text-slate-600">
                      <p className="font-semibold text-slate-800">{p.receiver_name}</p>
                      <p className="text-[11px] text-slate-400">{p.receiver_city}</p>
                    </td>
                    <td className="py-4 px-4 text-slate-600">
                      <p>{p.weight_kg} kg</p>
                      <p className="text-[11px] text-slate-400 font-mono">
                        {p.length_cm}x{p.width_cm}x{p.height_cm} cm
                      </p>
                    </td>
                    <td className="py-4 px-4">
                      <Badge status={p.delivery_status} />
                    </td>
                    <td className="py-4 px-4 font-bold text-slate-900">
                      ₹{p.total_charge}
                    </td>
                    <td className="py-4 px-6 text-right space-x-1">
                      <Link
                        to={`/parcels/${p.tracking_number}`}
                        className="p-1.5 inline-block text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                        title="View details & timeline"
                      >
                        <Eye className="w-4 h-4" />
                      </Link>

                      <button
                        onClick={() => handleDownloadLabel(p.tracking_number)}
                        className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                        title="Download PDF Shipping Label"
                      >
                        <Download className="w-4 h-4" />
                      </button>

                      {p.delivery_status === 'BOOKED' && (
                        <button
                          onClick={() => {
                            setSelectedParcel(p);
                            setCancelModalOpen(true);
                          }}
                          className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                          title="Cancel booking"
                        >
                          <XCircle className="w-4 h-4" />
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

      {/* Cancellation Modal */}
      <Modal
        isOpen={cancelModalOpen}
        onClose={() => setCancelModalOpen(false)}
        title={`Cancel Shipment ${selectedParcel?.tracking_number}`}
      >
        <form onSubmit={handleCancelSubmit} className="space-y-4">
          <p className="text-xs text-slate-600">
            Cancellation is only permitted while the package remains in <b>BOOKED</b> status. Cancelling will issue an immediate refund on shipping charges.
          </p>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Cancellation Reason *</label>
            <textarea
              required
              rows={3}
              value={cancellationReason}
              onChange={(e) => setCancellationReason(e.target.value)}
              placeholder="e.g. Recipient requested postponement or shipment details incorrect"
              className="w-full px-3 py-2 border rounded-xl text-xs"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setCancelModalOpen(false)}
              className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
            >
              Keep Booking
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-xl shadow-sm"
            >
              Confirm Cancellation
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

