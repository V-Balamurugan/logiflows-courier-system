import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Package,
  Truck,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Users,
  TrendingUp,
  PackagePlus,
  QrCode,
  ArrowRight,
  GitBranch,
} from 'lucide-react';
import { analyticsApi, parcelApi } from '../api';
import { useAuth } from '../contexts/AuthContext';
import { DashboardStats, Parcel } from '../types';
import { StatCard } from '../components/StatCard';
import { Badge } from '../components/Badge';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentParcels, setRecentParcels] = useState<Parcel[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [statsData, parcelsData] = await Promise.all([
          analyticsApi.getDashboard(),
          parcelApi.list({ search: '' }),
        ]);
        setStats(statsData);
        setRecentParcels(parcelsData.slice(0, 5));
      } catch (err) {
        console.error('Failed to load dashboard metrics', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  const role = user?.role;

  return (
    <div className="space-y-8 animate-in fade-in duration-200">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Operations Dashboard</h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time logistical telemetry & delivery performance across active branches.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {role !== 'DELIVERY_AGENT' && (
            <Link
              to="/book-parcel"
              className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-sm flex items-center gap-2 transition-all"
            >
              <PackagePlus className="w-4 h-4" />
              <span>Book Parcel</span>
            </Link>
          )}

          {role !== 'CUSTOMER' && (
            <Link
              to="/qr-scanner"
              className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs shadow-sm flex items-center gap-2 transition-all"
            >
              <QrCode className="w-4 h-4" />
              <span>Scan QR Code</span>
            </Link>
          )}
        </div>
      </div>

      {/* Primary KPI Grid */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard
            title="Total Shipments"
            value={stats.total_parcels}
            subtitle="Volume processed"
            icon={Package}
            color="indigo"
          />
          <StatCard
            title="Delivered Successfully"
            value={stats.delivered_parcels}
            subtitle={`${stats.delivery_success_rate}% success rate`}
            icon={CheckCircle2}
            color="emerald"
            trend={`${stats.delivery_success_rate}%`}
            trendPositive={true}
          />
          <StatCard
            title="In Transit / Pending"
            value={stats.pending_deliveries}
            subtitle="Active delivery runs"
            icon={Clock}
            color="amber"
          />
          {role === 'CUSTOMER' ? (
            <StatCard
              title="Failed / Cancelled"
              value={stats.failed_deliveries}
              subtitle="Requires review"
              icon={AlertTriangle}
              color="rose"
            />
          ) : (
            <StatCard
              title="Active Fleet Vehicles"
              value={stats.available_vehicles}
              subtitle="Ready for dispatch"
              icon={Truck}
              color="blue"
            />
          )}
        </div>
      )}

      {/* Secondary Section: Status Breakdown & Branch Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Status Breakdown Bar chart */}
        <div className="lg:col-span-5 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Shipment Status Mix</h3>
            <span className="text-xs text-slate-500 font-medium">By Lifecycle Stage</span>
          </div>

          <div className="space-y-3 pt-2">
            {stats?.status_breakdown && stats.status_breakdown.length > 0 ? (
              stats.status_breakdown.map((item) => {
                const total = stats.total_parcels || 1;
                const pct = Math.round((item.count / total) * 100);
                return (
                  <div key={item.status} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-semibold text-slate-700">{item.status.replace(/_/g, ' ')}</span>
                      <span className="text-slate-500 font-medium">{item.count} ({pct}%)</span>
                    </div>
                    <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-indigo-600 rounded-full transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      ></div>
                    </div>
                  </div>
                );
              })
            ) : (
              <p className="text-xs text-slate-400 py-6 text-center">No parcels recorded yet.</p>
            )}
          </div>
        </div>

        {/* Branch Performance (or Recent Shipments for Customer/Agent) */}
        <div className="lg:col-span-7 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
              {role === 'CUSTOMER' || role === 'DELIVERY_AGENT' ? 'Recent Activity' : 'Branch Hub Throughput'}
            </h3>
            <Link
              to="/parcels"
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
            >
              <span>View All</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {role === 'CUSTOMER' || role === 'DELIVERY_AGENT' ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-slate-400 uppercase font-semibold">
                    <th className="pb-3">Tracking #</th>
                    <th className="pb-3">Destination</th>
                    <th className="pb-3">Status</th>
                    <th className="pb-3 text-right">Charge</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {recentParcels.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50/80">
                      <td className="py-3 font-bold text-slate-900">
                        <Link to={`/parcels/${p.tracking_number}`} className="hover:text-indigo-600">
                          {p.tracking_number}
                        </Link>
                      </td>
                      <td className="py-3 text-slate-600">{p.receiver_city}</td>
                      <td className="py-3"><Badge status={p.delivery_status} /></td>
                      <td className="py-3 text-right font-bold text-slate-900">₹{p.total_charge}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-slate-400 uppercase font-semibold">
                    <th className="pb-3">Branch Hub</th>
                    <th className="pb-3">Code</th>
                    <th className="pb-3">Parcels Handled</th>
                    <th className="pb-3">Delivered</th>
                    <th className="pb-3 text-right">Completion</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {stats?.branch_performance?.map((b) => {
                    const compRate = b.parcels_handled > 0 ? Math.round((b.deliveries_completed / b.parcels_handled) * 100) : 100;
                    return (
                      <tr key={b.branch_id} className="hover:bg-slate-50/80">
                        <td className="py-3 font-bold text-slate-900 flex items-center gap-2">
                          <GitBranch className="w-3.5 h-3.5 text-slate-400" />
                          <span>{b.branch_name}</span>
                        </td>
                        <td className="py-3 text-slate-500 font-mono">{b.branch_code}</td>
                        <td className="py-3 text-slate-800">{b.parcels_handled}</td>
                        <td className="py-3 text-emerald-600 font-bold">{b.deliveries_completed}</td>
                        <td className="py-3 text-right font-bold text-slate-900">{compRate}%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

