import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Truck, Search, ShieldCheck, Clock, MapPin, Calculator, ArrowRight, CheckCircle2 } from 'lucide-react';
import { parcelApi } from '../api';

export const LandingPage: React.FC = () => {
  const [trackingNumber, setTrackingNumber] = useState('');
  const [quoteWeight, setQuoteWeight] = useState('2.0');
  const [quoteLength, setQuoteLength] = useState('20');
  const [quoteWidth, setQuoteWidth] = useState('15');
  const [quoteHeight, setQuoteHeight] = useState('10');
  const [quoteService, setQuoteService] = useState('STANDARD');
  const [quoteResult, setQuoteResult] = useState<any>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);

  const navigate = useNavigate();

  const handleTrackSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (trackingNumber.trim()) {
      navigate(`/tracking?number=${encodeURIComponent(trackingNumber.trim())}`);
    }
  };

  const handleCalculateQuote = async (e: React.FormEvent) => {
    e.preventDefault();
    setQuoteLoading(true);
    try {
      const data = await parcelApi.quote({
        weight_kg: parseFloat(quoteWeight) || 1.0,
        length_cm: parseFloat(quoteLength) || 10.0,
        width_cm: parseFloat(quoteWidth) || 10.0,
        height_cm: parseFloat(quoteHeight) || 10.0,
        service_type: quoteService,
      });
      setQuoteResult(data);
    } catch (err) {
      console.error(err);
    } finally {
      setQuoteLoading(false);
    }
  };

  return (
    <div className="space-y-24 pb-20">
      {/* Hero Section */}
      <section className="relative overflow-hidden pt-12 pb-20 lg:pt-20 bg-gradient-to-b from-indigo-50/70 via-white to-slate-50">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-3xl mx-auto space-y-6">
            <span className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-indigo-100/80 text-indigo-700 border border-indigo-200/50">
              <span className="w-2 h-2 rounded-full bg-indigo-600 animate-pulse"></span>
              Next-Generation Logistics & Courier Automation Platform
            </span>

            <h1 className="text-4xl sm:text-6xl font-black text-slate-900 tracking-tight leading-tight">
              Smarter Logistics, <br />
              <span className="bg-gradient-to-r from-indigo-600 via-blue-600 to-indigo-800 bg-clip-text text-transparent">
                Faster Deliveries.
              </span>
            </h1>

            <p className="text-lg text-slate-600 leading-relaxed">
              LogiFlows empowers courier companies, regional branch hubs, and delivery agents with end-to-end parcel tracking, automated fleet routing, and QR-verified custody transfers.
            </p>

            {/* Quick Track Input Bar */}
            <div className="pt-4 max-w-2xl mx-auto">
              <form
                onSubmit={handleTrackSubmit}
                className="flex items-center p-2 rounded-2xl bg-white border border-slate-200/90 shadow-xl shadow-slate-200/50 focus-within:ring-2 focus-within:ring-indigo-500/20 focus-within:border-indigo-500 transition-all"
              >
                <div className="pl-3 text-slate-400">
                  <Search className="w-5 h-5" />
                </div>
                <input
                  type="text"
                  value={trackingNumber}
                  onChange={(e) => setTrackingNumber(e.target.value)}
                  placeholder="Enter Tracking Number (e.g. LF-2026-948102)"
                  className="w-full px-3 py-3 text-sm sm:text-base bg-transparent border-none focus:outline-hidden text-slate-800 font-medium placeholder-slate-400"
                />
                <button
                  type="submit"
                  className="px-6 py-3.5 rounded-xl bg-indigo-600 text-white font-bold text-sm hover:bg-indigo-700 transition-all shadow-md shadow-indigo-600/30 shrink-0"
                >
                  Track Shipment
                </button>
              </form>
            </div>
          </div>
        </div>
      </section>

      {/* Instant Shipping Rate Calculator & Feature Grid */}
      <section className="max-w-7xl mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-start">
          {/* Rate Calculator */}
          <div className="lg:col-span-5 bg-white p-8 rounded-3xl border border-slate-200 shadow-xl">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-3 rounded-xl bg-indigo-50 text-indigo-600">
                <Calculator className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-slate-900">Live Rate Calculator</h3>
                <p className="text-xs text-slate-500">Calculate charges by weight and volumetric metrics</p>
              </div>
            </div>

            <form onSubmit={handleCalculateQuote} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Weight (kg)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0.1"
                  value={quoteWeight}
                  onChange={(e) => setQuoteWeight(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1">Length (cm)</label>
                  <input
                    type="number"
                    value={quoteLength}
                    onChange={(e) => setQuoteLength(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1">Width (cm)</label>
                  <input
                    type="number"
                    value={quoteWidth}
                    onChange={(e) => setQuoteWidth(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1">Height (cm)</label>
                  <input
                    type="number"
                    value={quoteHeight}
                    onChange={(e) => setQuoteHeight(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Service Tier</label>
                <select
                  value={quoteService}
                  onChange={(e) => setQuoteService(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm"
                >
                  <option value="STANDARD">Standard Delivery (3-5 Days)</option>
                  <option value="EXPRESS">Express Priority (2 Days)</option>
                  <option value="OVERNIGHT">Overnight Cargo (1 Day)</option>
                  <option value="SAME_DAY">Same Day Courier (Immediate)</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={quoteLoading}
                className="w-full py-3 rounded-xl bg-slate-900 text-white font-bold text-sm hover:bg-slate-800 transition-all flex items-center justify-center gap-2 mt-4"
              >
                {quoteLoading ? 'Calculating...' : 'Calculate Estimate'}
              </button>
            </form>

            {quoteResult && (
              <div className="mt-6 p-4 rounded-2xl bg-indigo-50/70 border border-indigo-100 space-y-2 text-sm">
                <div className="flex justify-between text-slate-600">
                  <span>Chargeable Weight:</span>
                  <span className="font-semibold text-slate-900">{quoteResult.chargeable_weight_kg} kg</span>
                </div>
                <div className="flex justify-between text-slate-600">
                  <span>Base & Distance Rate:</span>
                  <span>₹{quoteResult.base_charge + quoteResult.weight_charge}</span>
                </div>
                <div className="flex justify-between text-slate-600">
                  <span>GST (18%):</span>
                  <span>₹{quoteResult.tax_amount}</span>
                </div>
                <div className="pt-2 border-t border-indigo-200/60 flex justify-between items-center text-indigo-900 font-extrabold text-base">
                  <span>Total Estimated Charge:</span>
                  <span className="text-xl text-indigo-700">₹{quoteResult.total_charge}</span>
                </div>
                <p className="text-[11px] text-slate-500 text-center pt-1">
                  Estimated transit window: {quoteResult.estimated_delivery_days} business days
                </p>
              </div>
            )}
          </div>

          {/* Platform Capabilities */}
          <div className="lg:col-span-7 space-y-8">
            <div>
              <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">
                Enterprise Logistics Engine Built for Complete Visibility
              </h2>
              <p className="text-slate-600 mt-2">
                Designed to handle complex multi-branch routing, last-mile deliveries, and physical chain-of-custody validation.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs space-y-3">
                <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                  <MapPin className="w-5 h-5" />
                </div>
                <h4 className="font-bold text-slate-900">Branch Geolocation Hubs</h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Map-integrated physical hubs tracking inward/outward freight flow with coordinate-accurate spatial visualization.
                </p>
              </div>

              <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs space-y-3">
                <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <h4 className="font-bold text-slate-900">QR Chain-of-Custody</h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Every handoff is verified with secure QR scans, recording agent timestamp, branch coordinates, and state validation.
                </p>
              </div>

              <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs space-y-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
                  <Truck className="w-5 h-5" />
                </div>
                <h4 className="font-bold text-slate-900">Fleet & Vehicle Dispatch</h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Manage trucks, vans, and bikes with payload capacity checks, driver assignments, and maintenance logs.
                </p>
              </div>

              <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs space-y-3">
                <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
                  <Clock className="w-5 h-5" />
                </div>
                <h4 className="font-bold text-slate-900">Real-Time Milestone SLA</h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Full 12-stage shipment lifecycle from booking to delivery proof with automated customer notifications.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Role Demonstration Quick Access Card */}
      <section className="max-w-7xl mx-auto px-6">
        <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-10 text-white shadow-2xl space-y-6">
          <div className="max-w-2xl">
            <h3 className="text-2xl font-bold">Try LogiFlows Across Any Role</h3>
            <p className="text-sm text-slate-300 mt-2">
              LogiFlows comes pre-seeded with realistic operational data. Use our 1-click login buttons on the Sign In page to explore the system from any persona:
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 pt-2">
            <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-1">
              <span className="text-[10px] uppercase font-bold text-red-400">System Admin</span>
              <p className="text-sm font-semibold">Super Admin</p>
              <p className="text-xs text-slate-400">Global control & orgs</p>
            </div>
            <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-1">
              <span className="text-[10px] uppercase font-bold text-indigo-400">HQ Operations</span>
              <p className="text-sm font-semibold">Org Admin</p>
              <p className="text-xs text-slate-400">Branches & employees</p>
            </div>
            <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-1">
              <span className="text-[10px] uppercase font-bold text-cyan-400">Hub Operations</span>
              <p className="text-sm font-semibold">Branch Manager</p>
              <p className="text-xs text-slate-400">Dispatches & local hub</p>
            </div>
            <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-1">
              <span className="text-[10px] uppercase font-bold text-teal-400">Field Operations</span>
              <p className="text-sm font-semibold">Delivery Agent</p>
              <p className="text-xs text-slate-400">QR scans & deliveries</p>
            </div>
            <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-300">Customer</span>
              <p className="text-sm font-semibold">Retail User</p>
              <p className="text-xs text-slate-400">Bookings & tracking</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

