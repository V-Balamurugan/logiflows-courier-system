import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Package,
  ArrowLeft,
  Download,
  QrCode,
  MapPin,
  Clock,
  ShieldCheck,
  Calendar,
  Truck,
  CheckCircle2,
} from 'lucide-react';
import { parcelApi, custodyApi } from '../api';
import { Parcel } from '../types';
import { Badge } from '../components/Badge';

export const ParcelDetailPage: React.FC = () => {
  const { trackingNumber } = useParams<{ trackingNumber: string }>();
  const [parcel, setParcel] = useState<Parcel | null>(null);
  const [custodyLogs, setCustodyLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadParcel = async () => {
      if (!trackingNumber) return;
      setLoading(true);
      try {
        const [pData, cData] = await Promise.all([
          parcelApi.get(trackingNumber),
          custodyApi.getHistory(trackingNumber),
        ]);
        setParcel(pData);
        setCustodyLogs(cData);
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

        <button
          onClick={handleDownloadPdf}
          className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-sm flex items-center gap-2 transition-all"
        >
          <Download className="w-4 h-4" />
          <span>Download Shipping Label (PDF)</span>
        </button>
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
        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
          Chain of Custody & Milestone Timeline
        </h3>

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
    </div>
  );
};

