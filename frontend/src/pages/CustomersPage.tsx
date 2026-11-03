import React, { useState, useEffect } from 'react';
import { UserCheck, Search, Mail, Phone, Building2, Package, MapPin } from 'lucide-react';
import { customerApi } from '../api';
import { User, Parcel } from '../types';
import { Modal } from '../components/Modal';
import { Badge } from '../components/Badge';

export const CustomersPage: React.FC = () => {
  const [customers, setCustomers] = useState<User[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedCustomer, setSelectedCustomer] = useState<User | null>(null);
  const [customerParcels, setCustomerParcels] = useState<Parcel[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const loadCustomers = async () => {
    setLoading(true);
    try {
      const data = await customerApi.list(search);
      setCustomers(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCustomers();
  }, [search]);

  const handleViewParcels = async (cust: User) => {
    setSelectedCustomer(cust);
    try {
      const parcels = await customerApi.getParcels(cust.id);
      setCustomerParcels(parcels);
      setIsModalOpen(true);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="pb-2 border-b border-slate-200">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Customer Directory</h1>
        <p className="text-xs text-slate-500 mt-1">
          Registered corporate clients, eCommerce shippers, and retail customers.
        </p>
      </div>

      <div className="flex items-center gap-4 bg-white p-4 rounded-2xl border border-slate-200 shadow-2xs">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search customer by name, email, phone..."
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
          />
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 uppercase font-semibold">
                <th className="py-3.5 px-6">Customer</th>
                <th className="py-3.5 px-4">Contact</th>
                <th className="py-3.5 px-4">Company & GST</th>
                <th className="py-3.5 px-4">Default Address</th>
                <th className="py-3.5 px-6 text-right">Shipment History</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {customers.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50/80">
                  <td className="py-4 px-6">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-indigo-50 text-indigo-700 flex items-center justify-center font-bold">
                        {c.full_name.charAt(0)}
                      </div>
                      <div>
                        <p className="font-bold text-slate-900">{c.full_name}</p>
                        <p className="text-[11px] text-slate-400">Registered {c.created_at.slice(0, 10)}</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-4 px-4 text-slate-600 space-y-0.5">
                    <p className="flex items-center gap-1.5 text-[11px]">
                      <Mail className="w-3 h-3 text-slate-400" /> {c.email}
                    </p>
                    <p className="flex items-center gap-1.5 text-[11px]">
                      <Phone className="w-3 h-3 text-slate-400" /> {c.phone || 'N/A'}
                    </p>
                  </td>
                  <td className="py-4 px-4 text-slate-600">
                    <p className="font-semibold text-slate-800">{c.customer_profile?.company_name || 'Individual'}</p>
                    {c.customer_profile?.gst_number && (
                      <p className="text-[10px] text-slate-400 font-mono">GST: {c.customer_profile.gst_number}</p>
                    )}
                  </td>
                  <td className="py-4 px-4 text-slate-500 max-w-xs truncate text-[11px]">
                    {c.customer_profile?.default_pickup_address || 'No default specified'}
                  </td>
                  <td className="py-4 px-6 text-right">
                    <button
                      onClick={() => handleViewParcels(c)}
                      className="px-3 py-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold text-xs flex items-center gap-1.5 ml-auto transition-colors"
                    >
                      <Package className="w-3.5 h-3.5" />
                      <span>View Parcels</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Customer Parcels Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={`Shipments for ${selectedCustomer?.full_name}`}
        maxWidth="xl"
      >
        <div className="space-y-4">
          {customerParcels.length === 0 ? (
            <p className="text-xs text-slate-500 text-center py-6">No shipments booked by this customer yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-slate-500 uppercase font-semibold">
                    <th className="pb-2">Tracking #</th>
                    <th className="pb-2">Destination</th>
                    <th className="pb-2">Date</th>
                    <th className="pb-2">Status</th>
                    <th className="pb-2 text-right">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {customerParcels.map((p) => (
                    <tr key={p.id}>
                      <td className="py-2.5 font-bold text-indigo-600">{p.tracking_number}</td>
                      <td className="py-2.5 text-slate-600">{p.receiver_city}</td>
                      <td className="py-2.5 text-slate-500">{p.booking_date.slice(0, 10)}</td>
                      <td className="py-2.5"><Badge status={p.delivery_status} /></td>
                      <td className="py-2.5 text-right font-bold text-slate-900">₹{p.total_charge}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};

