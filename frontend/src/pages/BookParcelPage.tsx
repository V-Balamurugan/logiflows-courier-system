import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { PackagePlus, ArrowRight, Calculator, CheckCircle2, MapPin, Truck, AlertCircle } from 'lucide-react';
import { branchApi, parcelApi } from '../api';
import { Branch } from '../types';

export const BookParcelPage: React.FC = () => {
  const navigate = useNavigate();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(false);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quote, setQuote] = useState<any>(null);
  const [error, setError] = useState('');

  const [formData, setFormData] = useState({
    origin_branch_id: '',
    dest_branch_id: '',
    sender_name: '',
    sender_phone: '',
    sender_email: '',
    sender_address: '',
    sender_city: '',
    sender_state: '',
    sender_pincode: '',
    receiver_name: '',
    receiver_phone: '',
    receiver_email: '',
    receiver_address: '',
    receiver_city: '',
    receiver_state: '',
    receiver_pincode: '',
    weight_kg: '1.5',
    length_cm: '20',
    width_cm: '15',
    height_cm: '10',
    service_type: 'STANDARD',
    notes: '',
  });

  useEffect(() => {
    const loadBranches = async () => {
      try {
        const data = await branchApi.list();
        setBranches(data);
        if (data.length >= 2) {
          setFormData((prev) => ({
            ...prev,
            origin_branch_id: data[0].id.toString(),
            dest_branch_id: data[1].id.toString(),
            sender_city: data[0].city,
            sender_state: data[0].state,
            sender_pincode: data[0].pincode,
            receiver_city: data[1].city,
            receiver_state: data[1].state,
            receiver_pincode: data[1].pincode,
          }));
        }
      } catch (err) {
        console.error(err);
      }
    };
    loadBranches();
  }, []);

  // Auto calculate quote on metric changes
  useEffect(() => {
    const fetchQuote = async () => {
      const w = parseFloat(formData.weight_kg);
      const l = parseFloat(formData.length_cm);
      const wi = parseFloat(formData.width_cm);
      const h = parseFloat(formData.height_cm);
      if (w > 0 && l > 0 && wi > 0 && h > 0) {
        setQuoteLoading(true);
        try {
          const res = await parcelApi.quote({
            weight_kg: w,
            length_cm: l,
            width_cm: wi,
            height_cm: h,
            service_type: formData.service_type,
          });
          setQuote(res);
        } catch (e) {
          console.error(e);
        } finally {
          setQuoteLoading(false);
        }
      }
    };
    const timer = setTimeout(fetchQuote, 400);
    return () => clearTimeout(timer);
  }, [formData.weight_kg, formData.length_cm, formData.width_cm, formData.height_cm, formData.service_type]);

  const handleOriginChange = (branchIdStr: string) => {
    const b = branches.find((item) => item.id.toString() === branchIdStr);
    setFormData((prev) => ({
      ...prev,
      origin_branch_id: branchIdStr,
      sender_city: b ? b.city : prev.sender_city,
      sender_state: b ? b.state : prev.sender_state,
      sender_pincode: b ? b.pincode : prev.sender_pincode,
    }));
  };

  const handleDestChange = (branchIdStr: string) => {
    const b = branches.find((item) => item.id.toString() === branchIdStr);
    setFormData((prev) => ({
      ...prev,
      dest_branch_id: branchIdStr,
      receiver_city: b ? b.city : prev.receiver_city,
      receiver_state: b ? b.state : prev.receiver_state,
      receiver_pincode: b ? b.pincode : prev.receiver_pincode,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const created = await parcelApi.book({
        origin_branch_id: parseInt(formData.origin_branch_id),
        dest_branch_id: parseInt(formData.dest_branch_id),
        sender_name: formData.sender_name,
        sender_phone: formData.sender_phone,
        sender_email: formData.sender_email || undefined,
        sender_address: formData.sender_address,
        sender_city: formData.sender_city,
        sender_state: formData.sender_state,
        sender_pincode: formData.sender_pincode,
        receiver_name: formData.receiver_name,
        receiver_phone: formData.receiver_phone,
        receiver_email: formData.receiver_email || undefined,
        receiver_address: formData.receiver_address,
        receiver_city: formData.receiver_city,
        receiver_state: formData.receiver_state,
        receiver_pincode: formData.receiver_pincode,
        weight_kg: parseFloat(formData.weight_kg),
        length_cm: parseFloat(formData.length_cm),
        width_cm: parseFloat(formData.width_cm),
        height_cm: parseFloat(formData.height_cm),
        service_type: formData.service_type,
        notes: formData.notes || undefined,
      });
      navigate(`/parcels/${created.tracking_number}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to book parcel. Please verify inputs.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-in fade-in duration-200">
      <div className="pb-2 border-b border-slate-200">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Create Consignment Booking</h1>
        <p className="text-xs text-slate-500 mt-1">
          Generate a tracking code, generate shipping label with QR custody barcode, and dispatch.
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 flex items-center gap-3 text-xs text-rose-700">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Form: Details */}
        <div className="lg:col-span-8 space-y-6">
          {/* Routing Branches */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <Truck className="w-4 h-4 text-indigo-600" />
              <span>1. Hub Routing Selection</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Origin Branch Hub *</label>
                <select
                  required
                  value={formData.origin_branch_id}
                  onChange={(e) => handleOriginChange(e.target.value)}
                  className="w-full px-3 py-2 border rounded-xl text-xs bg-slate-50 focus:bg-white"
                >
                  {branches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.branch_name} ({b.city})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Destination Branch Hub *</label>
                <select
                  required
                  value={formData.dest_branch_id}
                  onChange={(e) => handleDestChange(e.target.value)}
                  className="w-full px-3 py-2 border rounded-xl text-xs bg-slate-50 focus:bg-white"
                >
                  {branches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.branch_name} ({b.city})
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Sender & Receiver Address Details */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {/* Sender */}
            <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-3">
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider text-indigo-700">
                2. Sender Information
              </h3>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1">Sender Name *</label>
                <input
                  type="text"
                  required
                  value={formData.sender_name}
                  onChange={(e) => setFormData({ ...formData, sender_name: e.target.value })}
                  placeholder="e.g. Acme Corp"
                  className="w-full px-3 py-2 border rounded-xl text-xs"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1">Phone *</label>
                <input
                  type="text"
                  required
                  value={formData.sender_phone}
                  onChange={(e) => setFormData({ ...formData, sender_phone: e.target.value })}
                  placeholder="+91 98765 00000"
                  className="w-full px-3 py-2 border rounded-xl text-xs"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1">Pickup Address *</label>
                <textarea
                  rows={2}
                  required
                  value={formData.sender_address}
                  onChange={(e) => setFormData({ ...formData, sender_address: e.target.value })}
                  placeholder="Warehouse, Floor, Street"
                  className="w-full px-3 py-2 border rounded-xl text-xs"
                />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase mb-1">Pincode</label>
                  <input
                    type="text"
                    required
                    value={formData.sender_pincode}
                    onChange={(e) => setFormData({ ...formData, sender_pincode: e.target.value })}
                    className="w-full px-2 py-1.5 border rounded-lg text-xs"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase mb-1">City</label>
                  <input
                    type="text"
                    required
                    value={formData.sender_city}
                    onChange={(e) => setFormData({ ...formData, sender_city: e.target.value })}
                    className="w-full px-2 py-1.5 border rounded-lg text-xs"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase mb-1">State</label>
                  <input
                    type="text"
                    required
                    value={formData.sender_state}
                    onChange={(e) => setFormData({ ...formData, sender_state: e.target.value })}
                    className="w-full px-2 py-1.5 border rounded-lg text-xs"
                  />
                </div>
              </div>
            </div>

            {/* Receiver */}
            <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-3">
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider text-emerald-700">
                3. Receiver (Delivery)
              </h3>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1">Receiver Name *</label>
                <input
                  type="text"
                  required
                  value={formData.receiver_name}
                  onChange={(e) => setFormData({ ...formData, receiver_name: e.target.value })}
                  placeholder="e.g. Sunil Kumar"
                  className="w-full px-3 py-2 border rounded-xl text-xs"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1">Phone *</label>
                <input
                  type="text"
                  required
                  value={formData.receiver_phone}
                  onChange={(e) => setFormData({ ...formData, receiver_phone: e.target.value })}
                  placeholder="+91 91234 56789"
                  className="w-full px-3 py-2 border rounded-xl text-xs"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1">Delivery Address *</label>
                <textarea
                  rows={2}
                  required
                  value={formData.receiver_address}
                  onChange={(e) => setFormData({ ...formData, receiver_address: e.target.value })}
                  placeholder="Door No, Street, Landmark"
                  className="w-full px-3 py-2 border rounded-xl text-xs"
                />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase mb-1">Pincode</label>
                  <input
                    type="text"
                    required
                    value={formData.receiver_pincode}
                    onChange={(e) => setFormData({ ...formData, receiver_pincode: e.target.value })}
                    className="w-full px-2 py-1.5 border rounded-lg text-xs"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase mb-1">City</label>
                  <input
                    type="text"
                    required
                    value={formData.receiver_city}
                    onChange={(e) => setFormData({ ...formData, receiver_city: e.target.value })}
                    className="w-full px-2 py-1.5 border rounded-lg text-xs"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase mb-1">State</label>
                  <input
                    type="text"
                    required
                    value={formData.receiver_state}
                    onChange={(e) => setFormData({ ...formData, receiver_state: e.target.value })}
                    className="w-full px-2 py-1.5 border rounded-lg text-xs"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Physical Specifications */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
              4. Parcel Metrics & Service Speed
            </h3>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Weight (kg) *</label>
                <input
                  type="number"
                  step="0.1"
                  min="0.1"
                  required
                  value={formData.weight_kg}
                  onChange={(e) => setFormData({ ...formData, weight_kg: e.target.value })}
                  className="w-full px-3 py-2 border rounded-xl text-xs"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Length (cm) *</label>
                <input
                  type="number"
                  min="1"
                  required
                  value={formData.length_cm}
                  onChange={(e) => setFormData({ ...formData, length_cm: e.target.value })}
                  className="w-full px-3 py-2 border rounded-xl text-xs"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Width (cm) *</label>
                <input
                  type="number"
                  min="1"
                  required
                  value={formData.width_cm}
                  onChange={(e) => setFormData({ ...formData, width_cm: e.target.value })}
                  className="w-full px-3 py-2 border rounded-xl text-xs"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Height (cm) *</label>
                <input
                  type="number"
                  min="1"
                  required
                  value={formData.height_cm}
                  onChange={(e) => setFormData({ ...formData, height_cm: e.target.value })}
                  className="w-full px-3 py-2 border rounded-xl text-xs"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Service Tier *</label>
              <select
                value={formData.service_type}
                onChange={(e) => setFormData({ ...formData, service_type: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs bg-slate-50"
              >
                <option value="STANDARD">Standard Ground Delivery (3-5 Days)</option>
                <option value="EXPRESS">Express Air Cargo (2 Days)</option>
                <option value="OVERNIGHT">Overnight Priority (Next Morning)</option>
                <option value="SAME_DAY">Same Day Direct Courier (Immediate)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Right Panel: Invoice & Summary */}
        <div className="lg:col-span-4 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xl space-y-6 sticky top-24">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
            <Calculator className="w-5 h-5 text-indigo-600" />
            <h3 className="font-bold text-slate-900 text-sm">Pricing Calculation</h3>
          </div>

          {quote ? (
            <div className="space-y-3 text-xs">
              <div className="flex justify-between text-slate-600">
                <span>Actual Weight:</span>
                <span className="font-semibold text-slate-900">{quote.weight_kg} kg</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Volumetric Weight:</span>
                <span className="font-semibold text-slate-900">{quote.volumetric_weight_kg} kg</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Chargeable Weight:</span>
                <span className="font-bold text-indigo-600">{quote.chargeable_weight_kg} kg</span>
              </div>
              <div className="h-px bg-slate-100 my-2"></div>
              <div className="flex justify-between text-slate-600">
                <span>Base Charge:</span>
                <span>₹{quote.base_charge}</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Weight Charge:</span>
                <span>₹{quote.weight_charge}</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Service Fee ({formData.service_type}):</span>
                <span>₹{quote.service_charge}</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>GST (18%):</span>
                <span>₹{quote.tax_amount}</span>
              </div>
              <div className="pt-3 border-t border-slate-200 flex justify-between items-center text-sm">
                <span className="font-bold text-slate-900">Total Payable:</span>
                <span className="text-2xl font-black text-indigo-600">₹{quote.total_charge}</span>
              </div>
              <p className="text-[11px] text-slate-400 text-center">
                Estimated Transit SLA: {quote.estimated_delivery_days} days
              </p>
            </div>
          ) : (
            <p className="text-xs text-slate-400 py-6 text-center">Enter parcel metrics to compute price.</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-md shadow-indigo-600/30 transition-all flex items-center justify-center gap-2"
          >
            {loading ? 'Processing Consignment...' : 'Confirm & Book Shipment'}
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
};

