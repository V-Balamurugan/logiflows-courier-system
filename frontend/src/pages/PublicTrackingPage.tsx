import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search, Package, MapPin, Calendar, Clock, CheckCircle2, AlertTriangle, ArrowRight } from 'lucide-react';
import { trackingApi } from '../api';
import { PublicTrackingResponse } from '../types';
import { Badge } from '../components/Badge';
import { LeafletMap } from '../components/LeafletMap';

export const PublicTrackingPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [trackingNumber, setTrackingNumber] = useState(searchParams.get('number') || '');
  const [data, setData] = useState<PublicTrackingResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchTracking = async (num: string) => {
    if (!num.trim()) return;
    setLoading(true);
    setError('');
    try {
      const res = await trackingApi.getPublic(num.trim());
      setData(res);
      setSearchParams({ number: num.trim() });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Tracking number not found. Please verify the code.');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const num = searchParams.get('number');
    if (num) {
      setTrackingNumber(num);
      fetchTracking(num);
    }
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchTracking(trackingNumber);
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-12 space-y-8">
      {/* Search Header */}
      <div className="text-center space-y-4 max-w-2xl mx-auto">
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Shipment Live Tracker</h1>
        <p className="text-slate-600 text-sm">
          Track packages across origin hubs, transit corridors, and destination branches with real-time GPS coordinate milestones.
        </p>

        <form onSubmit={handleSearch} className="flex gap-2 max-w-lg mx-auto pt-2">
          <div className="relative flex-1">
            <Search className="w-5 h-5 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={trackingNumber}
              onChange={(e) => setTrackingNumber(e.target.value)}
              placeholder="e.g. LF-2026-948102"
              className="w-full pl-11 pr-4 py-3 bg-white border border-slate-200 rounded-xl text-sm font-semibold shadow-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-3 rounded-xl bg-indigo-600 text-white font-bold text-sm hover:bg-indigo-700 transition-all shadow-md shadow-indigo-600/30"
          >
            {loading ? 'Locating...' : 'Track'}
          </button>
        </form>
      </div>

      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 flex items-center gap-3 text-sm max-w-lg mx-auto">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {data && (
        <div className="bg-white rounded-3xl border border-slate-200 shadow-xl overflow-hidden space-y-8 p-8 animate-in fade-in duration-300">
          {/* Top Banner */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-100">
            <div>
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Tracking Number</span>
              <h2 className="text-2xl font-black text-slate-900 mt-0.5">{data.tracking_number}</h2>
            </div>
            <div className="flex items-center gap-3">
              <Badge status={data.status} variant="status" />
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100 space-y-1">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">Origin</span>
              <p className="text-base font-bold text-slate-800">{data.origin_city}</p>
            </div>
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100 space-y-1">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">Destination</span>
              <p className="text-base font-bold text-slate-800">{data.destination_city}</p>
            </div>
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100 space-y-1">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">Booked On</span>
              <p className="text-base font-bold text-slate-800">{data.booking_date.slice(0, 10)}</p>
            </div>
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100 space-y-1">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">Expected Delivery</span>
              <p className="text-base font-bold text-indigo-600">
                {data.expected_delivery_date ? data.expected_delivery_date.slice(0, 10) : 'In Schedule'}
              </p>
            </div>
          </div>

          {/* Interactive Route Map */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Transit Geo-Route Map</h3>
              <span className="text-xs text-slate-500">Live checkpoint coordinates</span>
            </div>
            <LeafletMap
              originLat={data.origin_lat}
              originLng={data.origin_lng}
              destLat={data.dest_lat}
              destLng={data.dest_lng}
              currentLat={data.current_lat}
              currentLng={data.current_lng}
              originName={data.origin_city}
              destName={data.destination_city}
              currentLocationName={data.current_location || 'Transit Hub'}
            />
          </div>

          {/* Milestone Timeline */}
          <div>
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-6">Milestone History</h3>
            <div className="space-y-6 relative before:absolute before:inset-0 before:left-3 before:w-0.5 before:bg-slate-200">
              {data.milestones.map((m, idx) => (
                <div key={idx} className="relative flex items-start gap-4 pl-8">
                  <div className="absolute left-1.5 -translate-x-1/2 w-4 h-4 rounded-full bg-white border-4 border-indigo-600 shrink-0"></div>
                  <div className="bg-slate-50/80 p-4 rounded-2xl border border-slate-200/80 flex-1 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge status={m.status} />
                        {m.location && <span className="text-xs font-semibold text-slate-700">@ {m.location}</span>}
                      </div>
                      {m.remarks && <p className="text-xs text-slate-600 mt-1">{m.remarks}</p>}
                    </div>
                    <div className="text-[11px] text-slate-400 font-medium shrink-0">
                      {new Date(m.timestamp).toLocaleString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

