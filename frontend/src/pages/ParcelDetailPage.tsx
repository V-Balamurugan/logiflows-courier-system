import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Download, ShieldCheck, CheckCircle2, AlertTriangle, X, Hash } from 'lucide-react';
import { parcelApi, custodyApi } from '../api';
import { Parcel, CustodyChainVerification } from '../types';
import { Badge } from '../components/Badge';

export const ParcelDetailPage: React.FC = () => {
  const { trackingNumber } = useParams<{ trackingNumber: string }>();
  const [parcel, setParcel] = useState<Parcel | null>(null);
  const [_custodyLogs, setCustodyLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Custody Chain Verification State
  const [chainData, setChainData] = useState<CustodyChainVerification | null>(null);
  const [showChainModal, setShowChainModal] = useState(false);
  const [verifyingChain, setVerifyingChain] = useState(false);
  const [chainError, setChainError] = useState<string | null>(null);

  useEffect(() => {
    const loadParcel = async () => {
      if (!trackingNumber) return;
      setLoading(true);
      try {
        const pData = await parcelApi.get(trackingNumber);
        setParcel(pData);
        try {
          const cData = await custodyApi.getHistory(trackingNumber);
          setCustodyLogs(cData);
        } catch {
          // Internal custody logs are staff-only; graceful fallback for customers
          setCustodyLogs([]);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    loadParcel();
  }, [trackingNumber]);

  const handleDownloadPdf = async () => {
    if (!trackingNumber) return;
    try {
      await parcelApi.downloadLabel(trackingNumber);
    } catch (err) {
      alert('Error downloading PDF label');
    }
  };

  const handleVerifyChain = async () => {
    if (!trackingNumber) return;
    setVerifyingChain(true);
    setChainError(null);
    try {
      const res = await custodyApi.verifyChain(trackingNumber);
      setChainData(res);
      setShowChainModal(true);
    } catch (err: any) {
      setChainError(err.response?.data?.detail || 'Failed to verify cryptographic custody chain.');
      setShowChainModal(true);
    } finally {
      setVerifyingChain(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!parcel) {
    return (
      <div className="text-center py-12 space-y-4">
        <h2 className="text-xl font-bold text-slate-800">Shipment Not Found</h2>
        <Link to="/parcels" className="text-indigo-600 font-semibold text-xs">
          ← Back to shipments
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-in fade-in duration-200">
      {/* Top Navigation */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-200">
        <Link
          to="/parcels"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Parcels</span>
        </Link>

        <div className="flex items-center gap-3">
          <button
            onClick={handleVerifyChain}
            disabled={verifyingChain}
            className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 font-semibold text-xs shadow-xs flex items-center gap-2 transition-all border border-slate-200"
          >
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>{verifyingChain ? 'Verifying...' : 'Verify Custody Chain'}</span>
          </button>

          <button
            onClick={handleDownloadPdf}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-sm flex items-center gap-2 transition-all"
          >
            <Download className="w-4 h-4" />
            <span>Download Shipping Label (PDF)</span>
          </button>
        </div>
      </div>

      {/* Hero Tracking Banner */}
      <div className="bg-white p-8 rounded-3xl border border-slate-200/80 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-6">
        <div>
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Consignment Tracking ID
          </span>
          <h1 className="text-3xl font-black text-slate-900 mt-1">{parcel.tracking_number}</h1>
          <p className="text-xs text-slate-500 mt-1">
            Booked on {new Date(parcel.booking_date).toLocaleDateString()} • {parcel.service_type} Service
          </p>
        </div>

        <div className="flex items-center gap-4">
          {parcel.qr_code_data && (
            <div className="p-2 bg-slate-50 border border-slate-200 rounded-2xl shrink-0">
              <img
                src={parcel.qr_code_data}
                alt={`QR Code ${parcel.tracking_number}`}
                className="w-20 h-20 rounded-lg"
              />
            </div>
          )}
          <div className="space-y-2">
            <Badge status={parcel.delivery_status} />
            <p className="text-xs text-slate-500">
              Status: <span className="font-semibold text-slate-800">{parcel.delivery_status}</span>
            </p>
          </div>
        </div>
      </div>

      {/* Sender, Receiver & Specifications Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Sender */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-3">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Origin (Sender)</span>
          <h4 className="font-bold text-slate-900 text-sm">{parcel.sender_name}</h4>
          <p className="text-xs text-slate-600 leading-relaxed">{parcel.sender_address}</p>
          <p className="text-xs font-semibold text-slate-800">
            {parcel.sender_city}, {parcel.sender_state} - {parcel.sender_pincode}
          </p>
          <p className="text-xs text-slate-500 pt-1 border-t border-slate-100">Phone: {parcel.sender_phone}</p>
        </div>

        {/* Receiver */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-3">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Destination (Receiver)</span>
          <h4 className="font-bold text-slate-900 text-sm">{parcel.receiver_name}</h4>
          <p className="text-xs text-slate-600 leading-relaxed">{parcel.receiver_address}</p>
          <p className="text-xs font-semibold text-slate-800">
            {parcel.receiver_city}, {parcel.receiver_state} - {parcel.receiver_pincode}
          </p>
          <p className="text-xs text-slate-500 pt-1 border-t border-slate-100">Phone: {parcel.receiver_phone}</p>
        </div>

        {/* Specifications */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-3">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Consignment Specs</span>
          <div className="space-y-1.5 text-xs text-slate-600">
            <div className="flex justify-between">
              <span>Actual Weight:</span>
              <span className="font-bold text-slate-900">{parcel.weight_kg} kg</span>
            </div>
            <div className="flex justify-between">
              <span>Volumetric Weight:</span>
              <span className="font-bold text-slate-900">{parcel.volumetric_weight_kg} kg</span>
            </div>
            <div className="flex justify-between">
              <span>Dimensions:</span>
              <span className="font-mono text-slate-900">{parcel.length_cm}x{parcel.width_cm}x{parcel.height_cm} cm</span>
            </div>
            <div className="flex justify-between">
              <span>Total Charge:</span>
              <span className="font-bold text-indigo-600 text-sm">₹{parcel.total_charge}</span>
            </div>
            <div className="flex justify-between pt-1 border-t border-slate-100">
              <span>Payment Status:</span>
              <span className="font-semibold text-emerald-600">{parcel.payment_status}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tracking History Timeline */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-6">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
            Chain of Custody & Milestone Timeline
          </h3>
          <button
            onClick={handleVerifyChain}
            disabled={verifyingChain}
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1.5 transition-colors"
          >
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Audit Hash Chain</span>
          </button>
        </div>

        <div className="space-y-6 relative before:absolute before:inset-0 before:left-3 before:w-0.5 before:bg-slate-200">
          {parcel.tracking_history?.map((h) => (
            <div key={h.id} className="relative flex items-start gap-4 pl-8">
              <div className="absolute left-1.5 -translate-x-1/2 w-4 h-4 rounded-full bg-white border-4 border-indigo-600 shrink-0"></div>
              <div className="bg-slate-50/70 p-4 rounded-2xl border border-slate-200/70 flex-1 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <Badge status={h.status} />
                    {h.location_name && (
                      <span className="text-xs font-semibold text-slate-700">@ {h.location_name}</span>
                    )}
                  </div>
                  {h.remarks && <p className="text-xs text-slate-600 mt-1">{h.remarks}</p>}
                </div>
                <span className="text-[11px] text-slate-400 font-medium shrink-0">
                  {new Date(h.created_at).toLocaleString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Custody Chain Cryptographic Verification Modal */}
      {showChainModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-2xl w-full shadow-2xl flex flex-col max-h-[85vh] overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 pb-4 border-b border-slate-100 shrink-0 gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-10 h-10 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                  <ShieldCheck className="w-6 h-6" />
                </div>
                <div className="min-w-0">
                  <h3 className="font-bold text-slate-900 text-sm sm:text-base truncate">Cryptographic Chain of Custody</h3>
                  <p className="text-xs text-slate-500 truncate">Immutable SHA-256 Ledger Audit for {parcel.tracking_number}</p>
                </div>
              </div>
              <button
                onClick={() => setShowChainModal(false)}
                aria-label="Close modal"
                className="p-2 rounded-xl text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors shrink-0"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Scrollable Body */}
            <div className="p-6 space-y-4 overflow-y-auto flex-1">
              {chainError && (
                <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 flex items-center gap-3 text-xs">
                  <AlertTriangle className="w-5 h-5 shrink-0" />
                  <span>{chainError}</span>
                </div>
              )}

              {chainData && (
                <div className="space-y-4">
                  {/* Status banner */}
                  <div
                    className={`p-4 rounded-2xl border flex items-center justify-between ${
                      chainData.is_valid && !chainData.tamper_detected
                        ? 'bg-emerald-50/80 border-emerald-200 text-emerald-900'
                        : 'bg-rose-50 border-rose-200 text-rose-900'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      {chainData.is_valid && !chainData.tamper_detected ? (
                        <CheckCircle2 className="w-6 h-6 text-emerald-600 shrink-0" />
                      ) : (
                        <AlertTriangle className="w-6 h-6 text-rose-600 shrink-0" />
                      )}
                      <div>
                        <p className="font-bold text-sm">
                          {chainData.is_valid && !chainData.tamper_detected
                            ? '100% Cryptographically Verified & Tamper-Evident'
                            : 'Tampering or Broken Hash Sequence Detected!'}
                        </p>
                        <p className="text-xs opacity-80">
                          {chainData.total_scans} physical custody scan record(s) audited against SHA-256 hash chains.
                        </p>
                      </div>
                    </div>
                    <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-full bg-white/80 border">
                      {chainData.total_scans} Scans
                    </span>
                  </div>

                  {/* Scans Hash List */}
                  <div className="space-y-3">
                    {chainData.chain.length === 0 ? (
                      <div className="text-center py-8 text-slate-500 text-xs">
                        No physical custody scans recorded yet for this consignment.
                      </div>
                    ) : (
                      chainData.chain.map((record, index) => (
                        <div
                          key={record.id}
                          className={`p-4 rounded-2xl border text-xs space-y-2 ${
                            record.verified ? 'bg-slate-50 border-slate-200' : 'bg-rose-50/50 border-rose-300'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="w-5 h-5 rounded-full bg-indigo-600 text-white font-bold text-[10px] flex items-center justify-center">
                                {index + 1}
                              </span>
                              <span className="font-bold text-slate-900">{record.scan_type}</span>
                              {record.is_successful ? (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                                  Successful
                                </span>
                              ) : (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-800">
                                  Rejected
                                </span>
                              )}
                            </div>
                            <span className="text-[10px] text-slate-400">
                              {new Date(record.created_at).toLocaleString()}
                            </span>
                          </div>

                          {record.scanned_by_name && (
                            <p className="text-slate-600 text-[11px]">
                              Handler: <span className="font-medium text-slate-800">{record.scanned_by_name}</span>
                              {record.branch_id && ` • Branch #${record.branch_id}`}
                            </p>
                          )}

                          {record.record_hash && (
                            <div className="space-y-1 font-mono text-[10px] bg-white p-2.5 rounded-xl border border-slate-200">
                              <div className="flex items-center justify-between text-slate-500">
                                <span>Prev: {record.previous_hash ? `${record.previous_hash.slice(0, 16)}...` : 'None'}</span>
                                <span>Curr: {record.record_hash.slice(0, 16)}...</span>
                              </div>
                              <div className="text-[9px] text-emerald-700 flex items-center gap-1 font-sans">
                                <Hash className="w-3 h-3" />
                                <span>SHA-256 Hash Match Confirmed</span>
                              </div>
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Sticky Footer */}
            <div className="p-4 px-6 border-t border-slate-100 bg-slate-50/70 flex justify-end shrink-0">
              <button
                onClick={() => setShowChainModal(false)}
                className="px-5 py-2.5 rounded-xl bg-slate-900 text-white font-bold text-xs hover:bg-slate-800 transition-colors shadow-xs"
              >
                Close Audit
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

