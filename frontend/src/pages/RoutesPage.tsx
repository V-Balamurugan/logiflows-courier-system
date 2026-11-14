import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Clock,
  Compass,
  MapPin,
  Navigation,
  Play,
  Plus,
  RefreshCw,
  Route as RouteIcon,
  Send,
  Sparkles,
  Truck,
  XCircle,
} from 'lucide-react';
import { branchApi, employeeApi, parcelApi, routeApi, vehicleApi } from '../api';
import { Badge } from '../components/Badge';
import { LeafletMap, MapStopMarker } from '../components/LeafletMap';
import { Modal } from '../components/Modal';
import { useAuth } from '../contexts/AuthContext';
import {
  Branch,
  DeliveryRoute,
  Parcel,
  RouteObjective,
  RoutePreviewResponse,
  RouteStatus,
  RouteStop,
  RouteStopInput,
  RouteStopStatus,
  RouteStopType,
  User,
  Vehicle,
} from '../types';

const DELIVERY_ELIGIBLE = new Set([
  'PICKED_UP',
  'AT_ORIGIN_BRANCH',
  'AT_DESTINATION_BRANCH',
  'DELIVERY_FAILED',
]);
const PICKUP_ELIGIBLE = new Set(['BOOKED', 'PICKUP_SCHEDULED']);

const extractError = (err: unknown, fallback: string): string => {
  const axiosErr = err as { response?: { data?: { detail?: unknown } }; message?: string };
  const detail = axiosErr?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string };
    if (first?.msg) return first.msg;
  }
  return axiosErr?.message || fallback;
};

export const RoutesPage: React.FC = () => {
  const { user } = useAuth();
  const isManager =
    user?.role === 'SUPER_ADMIN' || user?.role === 'ORG_ADMIN' || user?.role === 'BRANCH_MANAGER';

  const [routes, setRoutes] = useState<DeliveryRoute[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<DeliveryRoute | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [bannerMsg, setBannerMsg] = useState<string | null>(null);

  // Reference data for managers
  const [branches, setBranches] = useState<Branch[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<User[]>([]);
  const [parcels, setParcels] = useState<Parcel[]>([]);

  // Planner Mode
  const [plannerOpen, setPlannerOpen] = useState(false);
  const [planBranchId, setPlanBranchId] = useState<string>('');
  const [planVehicleId, setPlanVehicleId] = useState<string>('');
  const [planDriverId, setPlanDriverId] = useState<string>('');
  const [planObjective, setPlanObjective] = useState<RouteObjective>('FASTEST');
  const [planReturnToHub, setPlanReturnToHub] = useState(true);
  const [planNotes, setPlanNotes] = useState('');
  const [selectedParcelStops, setSelectedParcelStops] = useState<Record<number, RouteStopType>>({});
  const [adhocStops, setAdhocStops] = useState<RouteStopInput[]>([]);
  const [adhocForm, setAdhocForm] = useState({
    location_name: '',
    latitude: '',
    longitude: '',
    stop_type: 'DELIVERY' as RouteStopType,
  });
  const [previewResult, setPreviewResult] = useState<RoutePreviewResponse | null>(null);

  // Dispatch Modal
  const [dispatchModalOpen, setDispatchModalOpen] = useState(false);
  const [dispatchForm, setDispatchForm] = useState({ vehicle_id: '', driver_id: '', notes: '' });

  // Cancel Modal
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState('');

  // Stop Execution Modal
  const [stopTarget, setStopTarget] = useState<RouteStop | null>(null);
  const [stopForm, setStopForm] = useState({
    status: 'COMPLETED' as RouteStopStatus,
    latitude: '',
    longitude: '',
    failure_reason: '',
    notes: '',
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const routeData = await routeApi.list(
        statusFilter !== 'ALL' ? { status: statusFilter as RouteStatus } : undefined
      );
      setRoutes(routeData);
      setSelectedRoute((prev) => {
        if (routeData.length === 0) return null;
        if (prev) {
          const match = routeData.find((r) => r.id === prev.id);
          if (match) return match;
        }
        return routeData[0];
      });

      if (isManager) {
        const [brData, vehData, empData, pclData] = await Promise.all([
          branchApi.list({ is_active: true }),
          vehicleApi.list(),
          employeeApi.list({ is_active: true }),
          parcelApi.list(),
        ]);
        setBranches(brData);
        setVehicles(vehData.filter((v) => v.is_active && v.status !== 'RETIRED'));
        setDrivers(
          empData.filter(
            (e) => e.is_active && (e.role === 'DELIVERY_AGENT' || e.role === 'BRANCH_MANAGER')
          )
        );
        setParcels(pclData);

        if (!planBranchId) {
          const preferredBranch =
            (user?.branch_id && brData.find((b) => b.id === user.branch_id)) ||
            brData.find((b) => b.latitude != null && b.longitude != null) ||
            brData[0];
          if (preferredBranch) {
            setPlanBranchId(String(preferredBranch.id));
          }
        }
      }
    } catch (err) {
      setErrorMsg(extractError(err, 'Failed to load route optimization data.'));
    } finally {
      setLoading(false);
    }
  }, [isManager, planBranchId, statusFilter, user?.branch_id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const activeBranchId = planBranchId ? Number(planBranchId) : undefined;

  const branchParcels = useMemo(() => {
    if (!activeBranchId) return [];
    return parcels.filter((p) => {
      const touchesBranch = p.origin_branch_id === activeBranchId || p.dest_branch_id === activeBranchId;
      if (!touchesBranch) return false;
      return DELIVERY_ELIGIBLE.has(p.delivery_status) || PICKUP_ELIGIBLE.has(p.delivery_status);
    });
  }, [activeBranchId, parcels]);

  const branchVehicles = useMemo(() => {
    if (!activeBranchId) return vehicles;
    return vehicles.filter((v) => !v.branch_id || v.branch_id === activeBranchId);
  }, [activeBranchId, vehicles]);

  const branchDrivers = useMemo(() => {
    if (!activeBranchId) return drivers;
    return drivers.filter((d) => !d.branch_id || d.branch_id === activeBranchId);
  }, [activeBranchId, drivers]);

  const buildPlannerStops = (): RouteStopInput[] => {
    const parcelStops: RouteStopInput[] = Object.entries(selectedParcelStops).map(
      ([parcelIdStr, stopType]) => ({
        parcel_id: Number(parcelIdStr),
        stop_type: stopType,
      })
    );
    return [...parcelStops, ...adhocStops];
  };

  const toggleParcelSelection = (parcel: Parcel) => {
    setPreviewResult(null);
    setSelectedParcelStops((prev) => {
      const next = { ...prev };
      if (next[parcel.id]) {
        delete next[parcel.id];
      } else {
        next[parcel.id] = PICKUP_ELIGIBLE.has(parcel.delivery_status) ? 'PICKUP' : 'DELIVERY';
      }
      return next;
    });
  };

  const handleAddAdhocStop = () => {
    const lat = Number(adhocForm.latitude);
    const lng = Number(adhocForm.longitude);
    if (!adhocForm.location_name.trim() || !Number.isFinite(lat) || !Number.isFinite(lng)) {
      setErrorMsg('Provide a stop label along with valid latitude and longitude.');
      return;
    }
    setPreviewResult(null);
    setErrorMsg(null);
    setAdhocStops((prev) => [
      ...prev,
      {
        stop_type: adhocForm.stop_type,
        location_name: adhocForm.location_name.trim(),
        latitude: lat,
        longitude: lng,
      },
    ]);
    setAdhocForm({ location_name: '', latitude: '', longitude: '', stop_type: 'DELIVERY' });
  };

  const handlePreviewRoute = async () => {
    if (!activeBranchId) {
      setErrorMsg('Select a branch hub with coordinates configured.');
      return;
    }
    const stops = buildPlannerStops();
    if (stops.length === 0) {
      setErrorMsg('Select at least one parcel or add an ad-hoc stop to preview.');
      return;
    }
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const res = await routeApi.preview({
        branch_id: activeBranchId,
        vehicle_id: planVehicleId ? Number(planVehicleId) : undefined,
        objective: planObjective,
        return_to_hub: planReturnToHub,
        stops,
      });
      setPreviewResult(res);
    } catch (err) {
      setErrorMsg(extractError(err, 'Failed to compute route preview.'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateRoute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeBranchId) {
      setErrorMsg('Select a branch hub first.');
      return;
    }
    const stops = buildPlannerStops();
    if (stops.length === 0) {
      setErrorMsg('Select at least one parcel or add an ad-hoc stop.');
      return;
    }
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const created = await routeApi.create({
        branch_id: activeBranchId,
        vehicle_id: planVehicleId ? Number(planVehicleId) : undefined,
        driver_id: planDriverId ? Number(planDriverId) : undefined,
        objective: planObjective,
        return_to_hub: planReturnToHub,
        stops,
        notes: planNotes.trim() || undefined,
      });
      setSelectedRoute(created);
      setPlannerOpen(false);
      setPreviewResult(null);
      setSelectedParcelStops({});
      setAdhocStops([]);
      setPlanNotes('');
      setBannerMsg(
        `Route ${created.route_code} saved (${created.total_distance_km.toFixed(1)} km, saved ${created.distance_saved_km.toFixed(1)} km).`
      );
      await loadData();
    } catch (err) {
      setErrorMsg(extractError(err, 'Failed to create optimized route plan.'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleReoptimizeSelected = async (objective: RouteObjective) => {
    if (!selectedRoute) return;
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const updated = await routeApi.reoptimize(selectedRoute.id, {
        objective,
        expected_version_id: selectedRoute.version_id,
      });
      setSelectedRoute(updated);
      setBannerMsg(`Route ${updated.route_code} re-optimized (${updated.optimization_objective}).`);
      await loadData();
    } catch (err) {
      setErrorMsg(extractError(err, 'Failed to re-optimize route.'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleMoveStop = async (stopId: number, direction: -1 | 1) => {
    if (!selectedRoute) return;
    const mutableStops = selectedRoute.stops.filter(
      (s) => s.status === 'PENDING' || s.status === 'EN_ROUTE'
    );
    const idx = mutableStops.findIndex((s) => s.id === stopId);
    const swapIdx = idx + direction;
    if (idx < 0 || swapIdx < 0 || swapIdx >= mutableStops.length) return;

    const reorderedIds = mutableStops.map((s) => s.id);
    [reorderedIds[idx], reorderedIds[swapIdx]] = [reorderedIds[swapIdx], reorderedIds[idx]];

    setSubmitting(true);
    setErrorMsg(null);
    try {
      const updated = await routeApi.reoptimize(selectedRoute.id, {
        objective: 'MANUAL',
        manual_stop_ids: reorderedIds,
        expected_version_id: selectedRoute.version_id,
      });
      setSelectedRoute(updated);
      setBannerMsg(`Updated manual stop sequence on ${updated.route_code}.`);
      await loadData();
    } catch (err) {
      setErrorMsg(extractError(err, 'Failed to reorder route stops.'));
    } finally {
      setSubmitting(false);
    }
  };

  const openDispatchModal = () => {
    if (!selectedRoute) return;
    setDispatchForm({
      vehicle_id: selectedRoute.vehicle_id ? String(selectedRoute.vehicle_id) : '',
      driver_id: selectedRoute.driver_id ? String(selectedRoute.driver_id) : '',
      notes: '',
    });
    setDispatchModalOpen(true);
  };

  const handleDispatchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRoute) return;
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const updated = await routeApi.dispatch(selectedRoute.id, {
        vehicle_id: dispatchForm.vehicle_id ? Number(dispatchForm.vehicle_id) : undefined,
        driver_id: dispatchForm.driver_id ? Number(dispatchForm.driver_id) : undefined,
        expected_version_id: selectedRoute.version_id,
        notes: dispatchForm.notes.trim() || undefined,
      });
      setSelectedRoute(updated);
      setDispatchModalOpen(false);
      setBannerMsg(`Dispatched ${updated.route_code} to ${updated.driver_name || 'driver'} (${updated.vehicle_number || 'vehicle'}).`);
      await loadData();
    } catch (err) {
      setErrorMsg(extractError(err, 'Failed to dispatch route.'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleStartRoute = async () => {
    if (!selectedRoute) return;
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const updated = await routeApi.start(selectedRoute.id);
      setSelectedRoute(updated);
      setBannerMsg(`Route ${updated.route_code} is now IN PROGRESS.`);
      await loadData();
    } catch (err) {
      setErrorMsg(extractError(err, 'Failed to start route.'));
    } finally {
      setSubmitting(false);
    }
  };

  const openStopActionModal = (stop: RouteStop, status: RouteStopStatus) => {
    setStopTarget(stop);
    setStopForm({
      status,
      latitude: String(stop.latitude),
      longitude: String(stop.longitude),
      failure_reason: '',
      notes: '',
    });
  };

  const handleStopUpdateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRoute || !stopTarget) return;
    const hasLat = stopForm.latitude.trim() !== '';
    const hasLng = stopForm.longitude.trim() !== '';
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const updated = await routeApi.updateStop(selectedRoute.id, stopTarget.id, {
        status: stopForm.status,
        latitude: hasLat && hasLng ? Number(stopForm.latitude) : undefined,
        longitude: hasLat && hasLng ? Number(stopForm.longitude) : undefined,
        failure_reason:
          stopForm.status === 'FAILED' ? stopForm.failure_reason.trim() : undefined,
        notes: stopForm.notes.trim() || undefined,
      });
      setSelectedRoute(updated);
      setStopTarget(null);
      setBannerMsg(`Stop #${stopTarget.sequence_order} marked ${stopForm.status}.`);
      await loadData();
    } catch (err) {
      setErrorMsg(extractError(err, 'Failed to update route stop status.'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelRouteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRoute) return;
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const updated = await routeApi.cancel(selectedRoute.id, cancelReason.trim());
      setSelectedRoute(updated);
      setCancelModalOpen(false);
      setCancelReason('');
      setBannerMsg(`Route ${updated.route_code} cancelled and fleet/parcels restored.`);
      await loadData();
    } catch (err) {
      setErrorMsg(extractError(err, 'Failed to cancel route.'));
    } finally {
      setSubmitting(false);
    }
  };

  const kpis = useMemo(() => {
    const active = routes.filter((r) => r.status === 'DISPATCHED' || r.status === 'IN_PROGRESS').length;
    const planned = routes.filter((r) => r.status === 'PLANNED').length;
    const totalDist = routes.reduce((acc, r) => acc + (r.total_distance_km || 0), 0);
    const totalSaved = routes.reduce((acc, r) => acc + (r.distance_saved_km || 0), 0);
    return { active, planned, totalDist, totalSaved };
  }, [routes]);

  const activeMapStops: MapStopMarker[] = useMemo(() => {
    if (plannerOpen && previewResult) {
      return previewResult.stops.map((s) => ({
        sequenceOrder: s.sequence_order,
        label: s.location_name,
        address: s.address,
        latitude: s.latitude,
        longitude: s.longitude,
        stopType: s.stop_type,
        coordsSource: s.coords_source,
      }));
    }
    if (!selectedRoute) return [];
    return selectedRoute.stops.map((s) => ({
      sequenceOrder: s.sequence_order,
      label: s.location_name,
      address: s.address,
      latitude: s.latitude,
      longitude: s.longitude,
      status: s.status,
      stopType: s.stop_type,
      coordsSource: s.coords_source,
    }));
  }, [plannerOpen, previewResult, selectedRoute]);

  const activePolyline = useMemo<[number, number][]>(() => {
    if (plannerOpen && previewResult) return previewResult.geometry_points;
    if (selectedRoute) return selectedRoute.geometry_points;
    return [];
  }, [plannerOpen, previewResult, selectedRoute]);

  return (
    <div className="space-y-6 min-w-0 max-w-full overflow-x-hidden animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Navigation className="w-6 h-6 text-indigo-600 shrink-0" />
            <span>Dynamic Route Optimization & Map</span>
          </h1>
          <p className="text-slate-500 text-xs mt-1">
            Multi-stop 2-opt TSP sequence planning, ETA calculation, atomic vehicle dispatch, and live itinerary tracking.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => loadData()}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-200 bg-white text-slate-700 text-xs font-semibold hover:bg-slate-50"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          {isManager && (
            <button
              type="button"
              onClick={() => {
                setPlannerOpen((prev) => !prev);
                setErrorMsg(null);
              }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700 shadow-sm"
            >
              <Plus className="w-4 h-4" />
              {plannerOpen ? 'View Active Routes' : 'Plan New Route'}
            </button>
          )}
        </div>
      </div>

      {/* Feedback Banners */}
      {bannerMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
            <span>{bannerMsg}</span>
          </div>
          <button type="button" onClick={() => setBannerMsg(null)} className="text-emerald-700 hover:underline">
            Dismiss
          </button>
        </div>
      )}

      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
            <span>{errorMsg}</span>
          </div>
          <button type="button" onClick={() => setErrorMsg(null)} className="text-rose-700 hover:underline">
            Dismiss
          </button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-4">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Active Dispatched</div>
          <div className="text-2xl font-black text-slate-900 mt-1">{kpis.active}</div>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-4">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Planned Waves</div>
          <div className="text-2xl font-black text-indigo-600 mt-1">{kpis.planned}</div>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-4">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Total Route Distance</div>
          <div className="text-2xl font-black text-slate-900 mt-1">{kpis.totalDist.toFixed(1)} km</div>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-4">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Distance Saved</div>
          <div className="text-2xl font-black text-emerald-600 mt-1">{kpis.totalSaved.toFixed(1)} km</div>
        </div>
      </div>

      {/* Main Split Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start min-w-0">
        {/* Left: Route List */}
        <div className="lg:col-span-4 space-y-3 min-w-0">
          <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-3 min-w-0">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-bold text-slate-900">Route Plans</h2>
              <select
                aria-label="Filter routes by status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="max-w-full min-w-0 text-xs font-semibold border border-slate-200 rounded-lg px-2.5 py-1.5 bg-slate-50 text-slate-700"
              >
                <option value="ALL">All Statuses</option>
                <option value="PLANNED">Planned</option>
                <option value="DISPATCHED">Dispatched</option>
                <option value="IN_PROGRESS">In Progress</option>
                <option value="COMPLETED">Completed</option>
                <option value="CANCELLED">Cancelled</option>
              </select>
            </div>

            {loading ? (
              <div className="p-4 sm:p-12 flex flex-col items-center justify-center text-slate-400 gap-2">
                <div className="w-7 h-7 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
                <span className="text-xs font-medium">Loading route plans...</span>
              </div>
            ) : routes.length === 0 ? (
              <div className="p-4 sm:p-12 text-center space-y-2 border border-dashed border-slate-200 rounded-xl bg-slate-50">
                <RouteIcon className="w-8 h-8 text-slate-300 mx-auto" />
                <p className="text-xs font-semibold text-slate-600">No route plans found</p>
                <p className="text-[11px] text-slate-400">
                  {isManager
                    ? 'Click "Plan New Route" to optimize stops for a branch hub.'
                    : 'Assigned routes will appear here once dispatched.'}
                </p>
              </div>
            ) : (
              <div className="space-y-2.5 max-h-[540px] overflow-y-auto pr-1">
                {routes.map((route) => {
                  const isSelected = selectedRoute?.id === route.id && !plannerOpen;
                  return (
                    <button
                      key={route.id}
                      type="button"
                      onClick={() => {
                        setPlannerOpen(false);
                        setSelectedRoute(route);
                      }}
                      className={`w-full text-left p-3.5 rounded-xl border transition-all ${
                        isSelected
                          ? 'bg-indigo-50/70 border-indigo-400 shadow-xs'
                          : 'bg-white border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-extrabold text-slate-900 truncate">
                          {route.route_code}
                        </span>
                        <Badge status={route.status} />
                      </div>
                      <div className="mt-1.5 text-[11px] text-slate-500 flex flex-wrap gap-x-3 gap-y-1">
                        <span>{route.branch_name || `Branch #${route.branch_id}`}</span>
                        <span>
                          {route.completed_stops}/{route.total_stops} stops
                        </span>
                        <span>{route.total_distance_km.toFixed(1)} km</span>
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px]">
                        {route.distance_saved_km > 0 && (
                          <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200">
                            Saved {route.distance_saved_km.toFixed(1)} km ({route.distance_saved_pct}%)
                          </span>
                        )}
                        {route.is_fallback && (
                          <span className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 font-semibold border border-amber-200">
                            Local 2-opt fallback
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right: Planner OR Selected Route Detail + Interactive Map */}
        <div className="lg:col-span-8 space-y-4 min-w-0">
          {plannerOpen && isManager ? (
            <form onSubmit={handleCreateRoute} className="bg-white rounded-2xl border border-slate-200 p-4 sm:p-6 space-y-5 min-w-0 max-w-full overflow-hidden">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-100">
                <div className="min-w-0">
                  <h2 className="text-base font-extrabold text-slate-900 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-indigo-600 shrink-0" />
                    <span>Optimize New Multi-Stop Route</span>
                  </h2>
                  <p className="text-xs text-slate-500">
                    Select eligible parcels or custom waypoints, preview distance & ETA, then save or dispatch.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setPlannerOpen(false)}
                  className="text-xs font-semibold text-slate-500 hover:text-slate-800 self-start"
                >
                  Close Planner
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 min-w-0">
                <div className="min-w-0">
                  <label htmlFor="route-branch-select" className="block text-[11px] font-bold text-slate-600 uppercase mb-1">
                    Anchor Branch
                  </label>
                  <select
                    id="route-branch-select"
                    value={planBranchId}
                    onChange={(e) => {
                      setPlanBranchId(e.target.value);
                      setSelectedParcelStops({});
                      setPreviewResult(null);
                    }}
                    className="w-full min-w-0 max-w-full px-3 py-2 text-xs rounded-xl border border-slate-200 bg-white font-semibold"
                  >
                    <option value="">Select Branch</option>
                    {branches.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.branch_name} ({b.branch_code})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="min-w-0">
                  <label htmlFor="route-objective-select" className="block text-[11px] font-bold text-slate-600 uppercase mb-1">
                    Objective
                  </label>
                  <select
                    id="route-objective-select"
                    value={planObjective}
                    onChange={(e) => {
                      setPlanObjective(e.target.value as RouteObjective);
                      setPreviewResult(null);
                    }}
                    className="w-full min-w-0 max-w-full px-3 py-2 text-xs rounded-xl border border-slate-200 bg-white font-semibold"
                  >
                    <option value="FASTEST">Fastest Time</option>
                    <option value="SHORTEST">Shortest Distance</option>
                    <option value="BALANCED">Balanced (Express Priority)</option>
                  </select>
                </div>

                <div className="min-w-0">
                  <label htmlFor="route-vehicle-select" className="block text-[11px] font-bold text-slate-600 uppercase mb-1">
                    Vehicle (Optional)
                  </label>
                  <select
                    id="route-vehicle-select"
                    value={planVehicleId}
                    onChange={(e) => {
                      setPlanVehicleId(e.target.value);
                      setPreviewResult(null);
                    }}
                    className="w-full min-w-0 max-w-full px-3 py-2 text-xs rounded-xl border border-slate-200 bg-white font-semibold"
                  >
                    <option value="">Unassigned</option>
                    {branchVehicles.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.vehicle_number} ({v.vehicle_type}, {v.max_weight_kg}kg, {v.status})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="min-w-0">
                  <label htmlFor="route-driver-select" className="block text-[11px] font-bold text-slate-600 uppercase mb-1">
                    Driver (Optional)
                  </label>
                  <select
                    id="route-driver-select"
                    value={planDriverId}
                    onChange={(e) => setPlanDriverId(e.target.value)}
                    className="w-full min-w-0 max-w-full px-3 py-2 text-xs rounded-xl border border-slate-200 bg-white font-semibold"
                  >
                    <option value="">Unassigned</option>
                    {branchDrivers.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.full_name} ({d.role})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Eligible Parcels Selection */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-700">
                    Eligible Branch Parcels ({branchParcels.length})
                  </span>
                  <label className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={planReturnToHub}
                      onChange={(e) => {
                        setPlanReturnToHub(e.target.checked);
                        setPreviewResult(null);
                      }}
                      className="rounded border-slate-300 text-indigo-600"
                    />
                    Return to Hub Depot
                  </label>
                </div>

                {branchParcels.length === 0 ? (
                  <div className="p-4 rounded-xl border border-dashed border-slate-200 bg-slate-50 text-xs text-slate-500">
                    No parcels awaiting pickup or delivery at this branch yet. You can add custom GPS waypoints below.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-48 overflow-y-auto pr-1">
                    {branchParcels.map((p) => {
                      const stopType = selectedParcelStops[p.id];
                      const checked = Boolean(stopType);
                      return (
                        <div
                          key={p.id}
                          className={`p-2.5 rounded-xl border text-xs flex items-center justify-between gap-2 ${
                            checked ? 'bg-indigo-50/70 border-indigo-300' : 'bg-slate-50 border-slate-200'
                          }`}
                        >
                          <label className="flex items-start gap-2 cursor-pointer flex-1 min-w-0">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleParcelSelection(p)}
                              className="mt-0.5 rounded border-slate-300 text-indigo-600"
                            />
                            <div className="min-w-0">
                              <div className="font-bold text-slate-900 truncate">{p.tracking_number}</div>
                              <div className="text-[11px] text-slate-500 truncate">
                                {p.receiver_name} ({p.weight_kg}kg · {p.delivery_status})
                              </div>
                            </div>
                          </label>
                          {checked && (
                            <select
                              aria-label={`Stop type for ${p.tracking_number}`}
                              value={stopType}
                              onChange={(e) =>
                                setSelectedParcelStops((prev) => ({
                                  ...prev,
                                  [p.id]: e.target.value as RouteStopType,
                                }))
                              }
                              className="text-[11px] font-bold border border-indigo-200 rounded-lg px-2 py-1 bg-white"
                            >
                              <option value="DELIVERY">DELIVERY</option>
                              <option value="PICKUP">PICKUP</option>
                            </select>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Ad-Hoc Waypoint Adder */}
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5 min-w-0">
                <div className="text-xs font-bold text-slate-700">Add Custom GPS Waypoint (Optional)</div>
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 min-w-0">
                  <input
                    type="text"
                    placeholder="Stop location name"
                    value={adhocForm.location_name}
                    onChange={(e) => setAdhocForm({ ...adhocForm, location_name: e.target.value })}
                    className="w-full min-w-0 px-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white"
                  />
                  <input
                    type="number"
                    step="0.0001"
                    placeholder="Latitude (e.g. 19.11)"
                    value={adhocForm.latitude}
                    onChange={(e) => setAdhocForm({ ...adhocForm, latitude: e.target.value })}
                    className="w-full min-w-0 px-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white"
                  />
                  <input
                    type="number"
                    step="0.0001"
                    placeholder="Longitude (e.g. 72.89)"
                    value={adhocForm.longitude}
                    onChange={(e) => setAdhocForm({ ...adhocForm, longitude: e.target.value })}
                    className="w-full min-w-0 px-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white"
                  />
                  <button
                    type="button"
                    onClick={handleAddAdhocStop}
                    className="w-full min-w-0 px-3 py-1.5 text-xs font-bold rounded-lg bg-slate-800 text-white hover:bg-slate-900"
                  >
                    + Add Stop
                  </button>
                </div>
                {adhocStops.length > 0 && (
                  <div className="flex flex-wrap gap-2 pt-1 min-w-0">
                    {adhocStops.map((s, idx) => (
                      <span
                        key={`${s.location_name}-${idx}`}
                        className="inline-flex max-w-full items-center gap-1.5 px-2.5 py-1 rounded-full bg-white border border-slate-200 text-[11px] font-semibold text-slate-700 break-all"
                      >
                        {s.location_name} ({s.latitude}, {s.longitude})
                        <button
                          type="button"
                          onClick={() => {
                            setAdhocStops((prev) => prev.filter((_, i) => i !== idx));
                            setPreviewResult(null);
                          }}
                          className="text-rose-600 font-bold"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <input
                  type="text"
                  placeholder="Dispatch / route planner notes (optional)"
                  value={planNotes}
                  onChange={(e) => setPlanNotes(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200"
                />
              </div>

              <div className="flex flex-wrap items-center gap-3 min-w-0">
                <button
                  type="button"
                  disabled={submitting}
                  onClick={handlePreviewRoute}
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-3 sm:px-4 py-2 rounded-xl bg-slate-900 text-white text-xs font-bold hover:bg-slate-800 disabled:opacity-50 whitespace-normal text-center"
                >
                  <Compass className="w-4 h-4 shrink-0" />
                  Preview Optimized Route
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-3 sm:px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700 disabled:opacity-50 whitespace-normal text-center"
                >
                  <Plus className="w-4 h-4 shrink-0" />
                  Save Route Plan
                </button>
              </div>

              {/* Preview Comparison Result & Map */}
              {previewResult && (
                <div className="pt-4 border-t border-slate-100 space-y-4">
                  {previewResult.capacity_exceeded && (
                    <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      <span>
                        Cargo weight ({previewResult.total_weight_kg} kg) exceeds vehicle capacity ({previewResult.vehicle_max_weight_kg} kg · {previewResult.utilization_pct}%).
                      </span>
                    </div>
                  )}
                  {previewResult.is_fallback && previewResult.fallback_reason && (
                    <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs font-semibold flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      <span>{previewResult.fallback_reason}</span>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                      <div className="text-slate-400 font-semibold">Optimized Dist</div>
                      <div className="font-black text-slate-900 text-sm">{previewResult.total_distance_km} km</div>
                    </div>
                    <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200">
                      <div className="text-emerald-700 font-semibold">Savings vs Baseline</div>
                      <div className="font-black text-emerald-700 text-sm">
                        {previewResult.distance_saved_km} km ({previewResult.distance_saved_pct}%)
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                      <div className="text-slate-400 font-semibold">Est. Duration</div>
                      <div className="font-black text-slate-900 text-sm">{previewResult.estimated_duration_min} min</div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                      <div className="text-slate-400 font-semibold">Provider</div>
                      <div className="font-black text-indigo-700 text-sm">{previewResult.provider_used}</div>
                    </div>
                  </div>

                  <LeafletMap
                    depotLat={previewResult.start_latitude}
                    depotLng={previewResult.start_longitude}
                    depotName={previewResult.branch_name}
                    stops={activeMapStops}
                    routePolyline={activePolyline}
                  />
                </div>
              )}
            </form>
          ) : selectedRoute ? (
            <div className="bg-white rounded-2xl border border-slate-200 p-4 sm:p-6 space-y-5 min-w-0 max-w-full overflow-hidden">
              {/* Route Header & Actions */}
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 pb-4 border-b border-slate-100">
                <div>
                  <div className="flex flex-wrap items-center gap-2.5">
                    <h2 className="text-lg font-black text-slate-900">{selectedRoute.route_code}</h2>
                    <Badge status={selectedRoute.status} />
                    <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                      {selectedRoute.optimization_objective} · v{selectedRoute.version_id}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
                    <span className="inline-flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5" />
                      {selectedRoute.branch_name || `Branch #${selectedRoute.branch_id}`}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Truck className="w-3.5 h-3.5" />
                      {selectedRoute.vehicle_number || 'Unassigned Vehicle'}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      {selectedRoute.estimated_duration_min.toFixed(0)} min · {selectedRoute.total_distance_km.toFixed(1)} km
                    </span>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {isManager && selectedRoute.status === 'PLANNED' && (
                    <>
                      <button
                        type="button"
                        disabled={submitting}
                        onClick={() => handleReoptimizeSelected('SHORTEST')}
                        className="px-3 py-1.5 rounded-xl border border-slate-200 text-xs font-bold text-slate-700 hover:bg-slate-50"
                      >
                        Re-optimize
                      </button>
                      <button
                        type="button"
                        disabled={submitting}
                        onClick={openDispatchModal}
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700"
                      >
                        <Send className="w-3.5 h-3.5" />
                        Dispatch Route
                      </button>
                    </>
                  )}
                  {selectedRoute.status === 'DISPATCHED' && (
                    <button
                      type="button"
                      disabled={submitting}
                      onClick={handleStartRoute}
                      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700"
                    >
                      <Play className="w-3.5 h-3.5" />
                      Start Route
                    </button>
                  )}
                  {isManager &&
                    selectedRoute.status !== 'COMPLETED' &&
                    selectedRoute.status !== 'CANCELLED' && (
                      <button
                        type="button"
                        disabled={submitting}
                        onClick={() => setCancelModalOpen(true)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-rose-200 bg-rose-50 text-rose-700 text-xs font-bold hover:bg-rose-100"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        Cancel Route
                      </button>
                    )}
                </div>
              </div>

              {selectedRoute.is_fallback && (
                <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs font-semibold flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>
                    {selectedRoute.fallback_reason || `Using ${selectedRoute.provider_used} fallback routing engine.`}
                  </span>
                </div>
              )}

              {/* Metrics Strip */}
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                  <div className="text-slate-400 font-semibold">Progress</div>
                  <div className="font-black text-slate-900 text-sm">
                    {selectedRoute.completed_stops} / {selectedRoute.total_stops} Stops
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200">
                  <div className="text-emerald-700 font-semibold">Distance Saved</div>
                  <div className="font-black text-emerald-700 text-sm">
                    {selectedRoute.distance_saved_km.toFixed(1)} km ({selectedRoute.distance_saved_pct}%)
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                  <div className="text-slate-400 font-semibold">Cargo Load</div>
                  <div className="font-black text-slate-900 text-sm">
                    {selectedRoute.total_weight_kg.toFixed(1)} kg
                    {selectedRoute.utilization_pct != null ? ` (${selectedRoute.utilization_pct}%)` : ''}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                  <div className="text-slate-400 font-semibold">Driver / Engine</div>
                  <div className="font-bold text-slate-900 text-sm truncate">
                    {selectedRoute.driver_name || 'Unassigned'} · {selectedRoute.provider_used}
                  </div>
                </div>
              </div>

              {/* Interactive Route Map */}
              <LeafletMap
                depotLat={selectedRoute.start_latitude}
                depotLng={selectedRoute.start_longitude}
                depotName={selectedRoute.branch_name || 'Branch Depot'}
                stops={activeMapStops}
                routePolyline={activePolyline}
              />

              {/* Ordered Stop Itinerary */}
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-900">Ordered Stop Itinerary</h3>
                  <span className="text-[11px] text-slate-500">
                    {selectedRoute.return_to_hub ? 'Round-trip to depot' : 'One-way final stop'}
                  </span>
                </div>

                {selectedRoute.stops.map((stop) => {
                  const isMutable = stop.status === 'PENDING' || stop.status === 'EN_ROUTE';
                  const isTerminal =
                    stop.status === 'COMPLETED' || stop.status === 'FAILED' || stop.status === 'SKIPPED';
                  const canExecute =
                    !isTerminal &&
                    (selectedRoute.status === 'DISPATCHED' || selectedRoute.status === 'IN_PROGRESS');

                  return (
                    <div
                      key={stop.id}
                      className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                    >
                      <div className="flex items-start gap-3 min-w-0">
                        <div className="w-7 h-7 rounded-full bg-indigo-600 text-white text-xs font-black flex items-center justify-center shrink-0 mt-0.5">
                          {stop.sequence_order}
                        </div>
                        <div className="min-w-0 space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-xs font-extrabold text-slate-900">{stop.location_name}</span>
                            <Badge status={stop.status} />
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-200 text-slate-700">
                              {stop.stop_type}
                            </span>
                            {stop.tracking_number && (
                              <span className="text-[11px] font-mono font-bold text-indigo-700">
                                {stop.tracking_number}
                              </span>
                            )}
                          </div>
                          {stop.address && <p className="text-[11px] text-slate-500">{stop.address}</p>}
                          <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
                            <span>Leg: {stop.distance_from_prev_km.toFixed(2)} km</span>
                            <span>ETA: +{stop.eta_minutes_from_start.toFixed(0)} min</span>
                            <span
                              className={`font-semibold ${
                                stop.coords_source === 'BRANCH_VICINITY_ESTIMATE'
                                  ? 'text-amber-700'
                                  : 'text-emerald-700'
                              }`}
                            >
                              Coords: {stop.coords_source === 'BRANCH_VICINITY_ESTIMATE' ? 'Vicinity Est.' : stop.coords_source}
                            </span>
                          </div>
                          {stop.failure_reason && (
                            <p className="text-[11px] font-semibold text-rose-600">
                              Failure: {stop.failure_reason}
                            </p>
                          )}
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                        {isManager &&
                          isMutable &&
                          selectedRoute.status !== 'COMPLETED' &&
                          selectedRoute.status !== 'CANCELLED' && (
                            <>
                              <button
                                type="button"
                                aria-label={`Move stop ${stop.sequence_order} up`}
                                disabled={submitting}
                                onClick={() => handleMoveStop(stop.id, -1)}
                                className="p-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-100"
                              >
                                <ArrowUp className="w-3.5 h-3.5" />
                              </button>
                              <button
                                type="button"
                                aria-label={`Move stop ${stop.sequence_order} down`}
                                disabled={submitting}
                                onClick={() => handleMoveStop(stop.id, 1)}
                                className="p-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-100"
                              >
                                <ArrowDown className="w-3.5 h-3.5" />
                              </button>
                            </>
                          )}
                        {canExecute && (
                          <>
                            {stop.status !== 'ARRIVED' && (
                              <button
                                type="button"
                                onClick={() => openStopActionModal(stop, 'ARRIVED')}
                                className="px-2.5 py-1 rounded-lg border border-cyan-200 bg-cyan-50 text-cyan-800 text-[11px] font-bold hover:bg-cyan-100"
                              >
                                Arrive
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => openStopActionModal(stop, 'COMPLETED')}
                              className="px-2.5 py-1 rounded-lg bg-emerald-600 text-white text-[11px] font-bold hover:bg-emerald-700"
                            >
                              Complete
                            </button>
                            <button
                              type="button"
                              onClick={() => openStopActionModal(stop, 'FAILED')}
                              className="px-2.5 py-1 rounded-lg bg-rose-600 text-white text-[11px] font-bold hover:bg-rose-700"
                            >
                              Fail
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-slate-200 p-4 sm:p-12 text-center space-y-3">
              <Navigation className="w-10 h-10 text-slate-300 mx-auto" />
              <h3 className="text-sm font-bold text-slate-800">Select or Plan a Route</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                Choose a route plan on the left to inspect its interactive Leaflet map, stop sequence, and live execution actions.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Dispatch Route Modal */}
      <Modal
        isOpen={dispatchModalOpen}
        onClose={() => setDispatchModalOpen(false)}
        title={`Dispatch ${selectedRoute?.route_code || 'Route'}`}
        maxWidth="md"
      >
        <form onSubmit={handleDispatchSubmit} className="space-y-4">
          <div>
            <label htmlFor="dispatch-vehicle" className="block text-xs font-bold text-slate-700 mb-1">
              Assign Available Vehicle
            </label>
            <select
              id="dispatch-vehicle"
              required
              value={dispatchForm.vehicle_id}
              onChange={(e) => setDispatchForm({ ...dispatchForm, vehicle_id: e.target.value })}
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200"
            >
              <option value="">Select Vehicle</option>
              {vehicles
                .filter((v) => v.status === 'AVAILABLE' || String(v.id) === dispatchForm.vehicle_id)
                .map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.vehicle_number} ({v.vehicle_type} · {v.max_weight_kg}kg · {v.status})
                  </option>
                ))}
            </select>
          </div>
          <div>
            <label htmlFor="dispatch-driver" className="block text-xs font-bold text-slate-700 mb-1">
              Assign Driver / Delivery Agent
            </label>
            <select
              id="dispatch-driver"
              required
              value={dispatchForm.driver_id}
              onChange={(e) => setDispatchForm({ ...dispatchForm, driver_id: e.target.value })}
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200"
            >
              <option value="">Select Driver</option>
              {drivers.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.full_name} ({d.role})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="dispatch-notes" className="block text-xs font-bold text-slate-700 mb-1">
              Dispatch Instructions (Optional)
            </label>
            <input
              id="dispatch-notes"
              type="text"
              value={dispatchForm.notes}
              onChange={(e) => setDispatchForm({ ...dispatchForm, notes: e.target.value })}
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200"
              placeholder="Priority handling or gate pass notes"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setDispatchModalOpen(false)}
              className="px-4 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-600"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700"
            >
              Confirm Atomic Dispatch
            </button>
          </div>
        </form>
      </Modal>

      {/* Stop Update Modal */}
      <Modal
        isOpen={Boolean(stopTarget)}
        onClose={() => setStopTarget(null)}
        title={`Update Stop #${stopTarget?.sequence_order ?? ''} (${stopForm.status})`}
        maxWidth="md"
      >
        <form onSubmit={handleStopUpdateSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="stop-lat" className="block text-xs font-bold text-slate-700 mb-1">
                GPS Latitude
              </label>
              <input
                id="stop-lat"
                type="number"
                step="0.0001"
                value={stopForm.latitude}
                onChange={(e) => setStopForm({ ...stopForm, latitude: e.target.value })}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200"
              />
            </div>
            <div>
              <label htmlFor="stop-lng" className="block text-xs font-bold text-slate-700 mb-1">
                GPS Longitude
              </label>
              <input
                id="stop-lng"
                type="number"
                step="0.0001"
                value={stopForm.longitude}
                onChange={(e) => setStopForm({ ...stopForm, longitude: e.target.value })}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200"
              />
            </div>
          </div>
          {stopForm.status === 'FAILED' && (
            <div>
              <label htmlFor="stop-fail-reason" className="block text-xs font-bold text-slate-700 mb-1">
                Failure Reason
              </label>
              <input
                id="stop-fail-reason"
                type="text"
                required
                minLength={3}
                value={stopForm.failure_reason}
                onChange={(e) => setStopForm({ ...stopForm, failure_reason: e.target.value })}
                placeholder="Customer unavailable / premises closed"
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200"
              />
            </div>
          )}
          <div>
            <label htmlFor="stop-notes" className="block text-xs font-bold text-slate-700 mb-1">
              POD / Checkpoint Notes
            </label>
            <input
              id="stop-notes"
              type="text"
              value={stopForm.notes}
              onChange={(e) => setStopForm({ ...stopForm, notes: e.target.value })}
              placeholder="Optional delivery remarks"
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setStopTarget(null)}
              className="px-4 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-600"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700"
            >
              Submit Update
            </button>
          </div>
        </form>
      </Modal>

      {/* Cancel Route Modal */}
      <Modal
        isOpen={cancelModalOpen}
        onClose={() => setCancelModalOpen(false)}
        title={`Cancel ${selectedRoute?.route_code || 'Route'}`}
        maxWidth="md"
      >
        <form onSubmit={handleCancelRouteSubmit} className="space-y-4">
          <div>
            <label htmlFor="cancel-route-reason" className="block text-xs font-bold text-slate-700 mb-1">
              Cancellation Reason
            </label>
            <input
              id="cancel-route-reason"
              type="text"
              required
              minLength={3}
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="e.g. Vehicle reassigned or wave consolidated"
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setCancelModalOpen(false)}
              className="px-4 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-600"
            >
              Keep Route
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 rounded-xl bg-rose-600 text-white text-xs font-bold hover:bg-rose-700"
            >
              Confirm Cancel
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
