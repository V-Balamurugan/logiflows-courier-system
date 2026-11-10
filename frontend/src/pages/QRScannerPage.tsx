import React, { useState } from 'react';
import { QrCode, CheckCircle2, AlertCircle, ArrowRight, ShieldCheck, Hash } from 'lucide-react';
import { custodyApi } from '../api';
import { Badge } from '../components/Badge';

export const QRScannerPage: React.FC = () => {
  const [trackingNumber, setTrackingNumber] = useState('');
  const [scanType, setScanType] = useState('PICKUP_VERIFICATION');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  const handleScanSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!trackingNumber.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const res = await custodyApi.scan({
        tracking_number: trackingNumber.trim(),
        scan_type: scanType,
        notes: notes || undefined,
      });
      setResult(res);
      setTrackingNumber('');
      setNotes('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Scan processing failed. Please verify tracking code.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-8 animate-in fade-in duration-200">
      <div className="text-center space-y-2">
        <div className="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-2">
          <QrCode className="w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">QR Custody Scanner Portal</h1>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          Scan or enter barcode tracking number to verify physical custody transitions and update consignment status.
        </p>
      </div>

      <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-xl space-y-6">
        {error && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-center gap-3 text-xs text-rose-700">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {result && (
          <div className="p-5 rounded-2xl bg-emerald-50 border border-emerald-200 space-y-3 text-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-emerald-800 font-bold text-sm">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                <span>Custody Verified & Recorded Successfully!</span>
              </div>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
                <ShieldCheck className="w-3 h-3 text-emerald-600" />
                Hash Chained
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-slate-700">
              <p>
                Parcel: <span className="font-bold text-slate-900">{result.tracking_number}</span>
              </p>
              <p>
                New Status: <Badge status={result.new_parcel_status} />
              </p>
            </div>
            <p className="text-slate-500 text-[11px]">
              Scanned by: {result.scanned_by_name} at {new Date(result.created_at).toLocaleTimeString()}
            </p>
            {result.record_hash && (
              <div className="pt-2 border-t border-emerald-200/60 font-mono text-[10px] text-emerald-900 space-y-0.5">
                <div className="flex items-center gap-1 text-[11px] font-semibold text-emerald-800 font-sans">
                  <Hash className="w-3 h-3" />
                  <span>Immutable Ledger Record</span>
                </div>
                <p className="truncate text-slate-600">
                  Record SHA-256: <span className="font-bold text-slate-800">{result.record_hash}</span>
                </p>
              </div>
            )}
          </div>
        )}

        <form onSubmit={handleScanSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
              Tracking Number / Scanned Barcode *
            </label>
            <div className="relative">
              <QrCode className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                required
                value={trackingNumber}
                onChange={(e) => setTrackingNumber(e.target.value)}
                placeholder="Scan or enter LF-2026-..."
                className="w-full pl-10 pr-4 py-3 rounded-xl border border-slate-200 text-sm font-mono focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Custody Scan Event *</label>
            <select
              value={scanType}
              onChange={(e) => setScanType(e.target.value)}
              className="w-full px-3 py-2.5 rounded-xl border border-slate-200 text-xs bg-slate-50 font-medium"
            >
              <option value="PICKUP_VERIFICATION">📦 Doorstep Pickup Verification (Status -&gt; PICKED_UP)</option>
              <option value="ORIGIN_INWARD">🏢 Origin Hub Inward Receiving (Status -&gt; AT_ORIGIN_BRANCH)</option>
              <option value="HUB_OUTWARD">🚛 Linehaul Hub Outward Dispatch (Status -&gt; IN_TRANSIT)</option>
              <option value="DEST_INWARD">📍 Destination Hub Arrival Inward (Status -&gt; AT_DESTINATION_BRANCH)</option>
              <option value="OUT_FOR_DELIVERY">🛵 Dispatch for Last-Mile Delivery (Status -&gt; OUT_FOR_DELIVERY)</option>
              <option value="DELIVERY_CONFIRMATION">✅ Proof of Delivery Confirmation (Status -&gt; DELIVERED)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Audit Notes / Signature OTP</label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Scanned at Bay 4 / Received by receiver personally"
              className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-md shadow-indigo-600/30 transition-all flex items-center justify-center gap-2 mt-4"
          >
            {loading ? 'Validating Barcode Scan...' : 'Confirm Custody Scan'}
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
};

