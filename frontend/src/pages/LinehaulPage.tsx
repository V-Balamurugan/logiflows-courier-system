import React, { useCallback, useEffect, useState } from 'react';
import {
  Boxes,
  Plus,
  Truck,
  ShieldCheck,
  AlertTriangle,
  PackageCheck,
  ArrowRightLeft,
  Lock,
  Unlock,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { branchApi, employeeApi, linehaulApi, parcelApi, vehicleApi } from '../api';
import {
  Branch,
  ConsolidationBag,
  LinehaulManifest,
  Parcel,
  TransferDiscrepancy,
  User,
  Vehicle,
} from '../types';
import { useAuth } from '../contexts/AuthContext';
import { Badge } from '../components/Badge';
import { Modal } from '../components/Modal';

type TabType = 'manifests' | 'bags' | 'discrepancies';

export const LinehaulPage: React.FC = () => {
  const { user } = useAuth();
  const isManager =
    user?.role === 'SUPER_ADMIN' || user?.role === 'ORG_ADMIN' || user?.role === 'BRANCH_MANAGER';

  const [activeTab, setActiveTab] = useState<TabType>('manifests');
  const [manifests, setManifests] = useState<LinehaulManifest[]>([]);
  const [bags, setBags] = useState<ConsolidationBag[]>([]);
  const [discrepancies, setDiscrepancies] = useState<TransferDiscrepancy[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<User[]>([]);
  const [eligibleParcels, setEligibleParcels] = useState<Parcel[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [bannerMsg, setBannerMsg] = useState<string | null>(null);

  // Create Manifest Modal
  const [manifestModalOpen, setManifestModalOpen] = useState(false);
  const [manifestForm, setManifestForm] = useState({
    origin_branch_id: '',
    dest_branch_id: '',
    vehicle_id: '',
    driver_id: '',
    seal_number: '',
    bag_ids: [] as number[],
    parcel_ids: [] as number[],
    notes: '',
  });

  // Create Bag Modal
  const [bagModalOpen, setBagModalOpen] = useState(false);
  const [bagForm, setBagForm] = useState({
    origin_branch_id: '',
    dest_branch_id: '',
    notes: '',
  });

  // Attach Parcels to Bag Modal
  const [attachBagTarget, setAttachBagTarget] = useState<ConsolidationBag | null>(null);
  const [selectedBagParcelIds, setSelectedBagParcelIds] = useState<number[]>([]);

  // Dispatch Modal
  const [dispatchTarget, setDispatchTarget] = useState<LinehaulManifest | null>(null);
  const [dispatchForm, setDispatchForm] = useState({
    vehicle_id: '',
    driver_id: '',
    seal_number: '',
    notes: '',
  });

  // Reconcile Modal
  const [reconcileTarget, setReconcileTarget] = useState<LinehaulManifest | null>(null);
  const [itemOutcomes, setItemOutcomes] = useState<Record<string, 'RECEIVED' | 'DAMAGED' | 'MISSING'>>({});
  const [sealIntact, setSealIntact] = useState(true);
  const [excessInput, setExcessInput] = useState('');
  const [reconcileNotes, setReconcileNotes] = useState('');

  // Report Discrepancy Modal
  const [discModalOpen, setDiscModalOpen] = useState(false);
  const [discForm, setDiscForm] = useState({
    manifest_id: '',
    tracking_number: '',
    discrepancy_type: 'DAMAGED',
    severity: 'HIGH',
    description: '',
  });

  // Resolve Discrepancy Modal
  const [resolveTarget, setResolveTarget] = useState<TransferDiscrepancy | null>(null);
  const [resolveForm, setResolveForm] = useState({
    status: 'RESOLVED',
    resolution_notes: '',
    release_parcel_to_dest: false,
  });

  const loadData = useCallback(async () => {
    try {
      const [manData, branchData, vehData] = await Promise.all([
        linehaulApi.listManifests(),
        branchApi.list({ is_active: true }),
        vehicleApi.list(),
      ]);
      setManifests(manData);
      setBranches(branchData);
      setVehicles(vehData);

      if (isManager) {
        const [bagData, discData, empData, parcelData] = await Promise.all([
          linehaulApi.listBags(),
          linehaulApi.listDiscrepancies(),
          employeeApi.list(),
          parcelApi.list({ status: 'AT_ORIGIN_BRANCH' }),
        ]);
        setBags(bagData);
        setDiscrepancies(discData);
        setDrivers(empData.filter((e) => e.role === 'DELIVERY_AGENT' || e.role === 'BRANCH_MANAGER'));
        setEligibleParcels(parcelData);
      }
      setErrorMsg(null);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to load linehaul operations data');
    } finally {
      setLoading(false);
    }
  }, [isManager]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const showBanner = (msg: string) => {
    setBannerMsg(msg);
    setErrorMsg(null);
  };

  const handleCreateManifest = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await linehaulApi.createManifest({
        origin_branch_id: parseInt(manifestForm.origin_branch_id, 10),
        dest_branch_id: parseInt(manifestForm.dest_branch_id, 10),
        vehicle_id: manifestForm.vehicle_id ? parseInt(manifestForm.vehicle_id, 10) : undefined,
        driver_id: manifestForm.driver_id ? parseInt(manifestForm.driver_id, 10) : undefined,
        seal_number: manifestForm.seal_number || undefined,
        bag_ids: manifestForm.bag_ids,
        parcel_ids: manifestForm.parcel_ids,
        notes: manifestForm.notes || undefined,
      });
      setManifestModalOpen(false);
      setManifestForm({
        origin_branch_id: '',
        dest_branch_id: '',
        vehicle_id: '',
        driver_id: '',
        seal_number: '',
        bag_ids: [],
        parcel_ids: [],
        notes: '',
      });
      showBanner('Linehaul manifest created successfully.');
      await loadData();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to create manifest');
    }
  };

  const handleDispatchManifest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dispatchTarget) return;
    try {
      await linehaulApi.dispatchManifest(dispatchTarget.id, {
        vehicle_id: dispatchForm.vehicle_id ? parseInt(dispatchForm.vehicle_id, 10) : undefined,
        driver_id: dispatchForm.driver_id ? parseInt(dispatchForm.driver_id, 10) : undefined,
        seal_number: dispatchForm.seal_number || undefined,
        notes: dispatchForm.notes || undefined,
      });
      setDispatchTarget(null);
      showBanner(`Manifest ${dispatchTarget.manifest_number} dispatched cleanly (IN_TRANSIT).`);
      await loadData();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to dispatch manifest');
    }
  };

  const handleArriveManifest = async (manifest: LinehaulManifest) => {
    try {
      await linehaulApi.arriveManifest(manifest.id, { seal_intact: true });
      showBanner(`Manifest ${manifest.manifest_number} marked as ARRIVED.`);
      await loadData();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to mark manifest arrival');
    }
  };

  const openReconcileModal = (manifest: LinehaulManifest) => {
    const initial: Record<string, 'RECEIVED' | 'DAMAGED' | 'MISSING'> = {};
    manifest.items.forEach((item) => {
      initial[item.tracking_number] = 'RECEIVED';
    });
    setItemOutcomes(initial);
    setSealIntact(true);
    setExcessInput('');
    setReconcileNotes('');
    setReconcileTarget(manifest);
  };

  const handleReconcileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reconcileTarget) return;
    const received: string[] = [];
    const damaged: string[] = [];
    const missing: string[] = [];
    Object.entries(itemOutcomes).forEach(([tn, outcome]) => {
      if (outcome === 'RECEIVED') received.push(tn);
      else if (outcome === 'DAMAGED') damaged.push(tn);
      else missing.push(tn);
    });
    const excess = excessInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    try {
      const res = await linehaulApi.reconcileManifest(reconcileTarget.id, {
        received_tracking_numbers: received,
        damaged_tracking_numbers: damaged,
        missing_tracking_numbers: missing,
        excess_tracking_numbers: excess,
        seal_intact: sealIntact,
        finalize: true,
        notes: reconcileNotes || undefined,
      });
      setReconcileTarget(null);
      showBanner(
        `Reconciled ${res.manifest.manifest_number}: ${res.received_count} intact, ${res.damaged_count} damaged, ${res.missing_count} missing.`
      );
      await loadData();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to reconcile manifest');
    }
  };

  const handleCreateBag = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await linehaulApi.createBag({
        origin_branch_id: parseInt(bagForm.origin_branch_id, 10),
        dest_branch_id: parseInt(bagForm.dest_branch_id, 10),
        notes: bagForm.notes || undefined,
      });
      setBagModalOpen(false);
      setBagForm({ origin_branch_id: '', dest_branch_id: '', notes: '' });
      showBanner('Consolidation bag created.');
      await loadData();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to create consolidation bag');
    }
  };

  const handleAttachParcelsToBag = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!attachBagTarget) return;
    try {
      await linehaulApi.attachParcelsToBag(attachBagTarget.id, {
        parcel_ids: selectedBagParcelIds,
      });
      setAttachBagTarget(null);
      setSelectedBagParcelIds([]);
      showBanner(`Parcels loaded into bag ${attachBagTarget.bag_code}.`);
      await loadData();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to add parcels to bag');
    }
  };

  const handleSealBag = async (bag: ConsolidationBag) => {
    try {
      await linehaulApi.sealBag(bag.id);
      showBanner(`Bag ${bag.bag_code} sealed and ready for manifesting.`);
      await loadData();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to seal bag');
    }
  };

  const handleDebag = async (bag: ConsolidationBag) => {
    try {
      await linehaulApi.debagBag(bag.id, 'Debagged at destination sorting hub');
      showBanner(`Bag ${bag.bag_code} opened and de-bagged at destination.`);
      await loadData();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to de-bag');
    }
  };

  const handleReportDiscrepancy = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await linehaulApi.reportDiscrepancy({
        manifest_id: parseInt(discForm.manifest_id, 10),
        tracking_number: discForm.tracking_number || undefined,
        discrepancy_type: discForm.discrepancy_type,
        severity: discForm.severity,
        description: discForm.description,
      });
      setDiscModalOpen(false);
      setDiscForm({
        manifest_id: '',
        tracking_number: '',
        discrepancy_type: 'DAMAGED',
        severity: 'HIGH',
        description: '',
      });
      showBanner('Transfer discrepancy logged cleanly.');
      await loadData();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to report discrepancy');
    }
  };

  const handleResolveDiscrepancy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resolveTarget) return;
    try {
      await linehaulApi.resolveDiscrepancy(resolveTarget.id, resolveForm);
      setResolveTarget(null);
      showBanner(`Discrepancy #${resolveTarget.id} updated.`);
      await loadData();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to update discrepancy');
    }
  };

  const corridorEligibleParcels = (originIdStr: string, destIdStr: string) => {
    const o = parseInt(originIdStr, 10);
    const d = parseInt(destIdStr, 10);
    if (!o || !d) return [];
    return eligibleParcels.filter((p) => p.origin_branch_id === o && p.dest_branch_id === d);
  };

  const corridorSealedBags = (originIdStr: string, destIdStr: string) => {
    const o = parseInt(originIdStr, 10);
    const d = parseInt(destIdStr, 10);
    if (!o || !d) return [];
    return bags.filter(
      (b) => b.origin_branch_id === o && b.dest_branch_id === d && b.status === 'SEALED' && !b.manifest_id
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2.5">
            <Boxes className="w-7 h-7 text-indigo-600" />
            Linehaul Transfers & Consolidation
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Manage branch-to-branch vehicle manifests, consolidation bags, arrival receiving scans, and shortage/damage discrepancies.
          </p>
        </div>

        {isManager && (
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setBagModalOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 font-semibold text-sm rounded-xl transition-colors"
            >
              <Plus className="w-4 h-4" />
              New Bag
            </button>
            <button
              onClick={() => setManifestModalOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-xl transition-colors shadow-sm shadow-indigo-600/20"
            >
              <Plus className="w-4 h-4" />
              Create Linehaul Manifest
            </button>
          </div>
        )}
      </div>

      {/* Banners */}
      {bannerMsg && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 px-4 py-3 rounded-xl text-sm flex items-center justify-between">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            {bannerMsg}
          </span>
          <button onClick={() => setBannerMsg(null)} className="text-emerald-600 hover:text-emerald-800 text-xs font-semibold">
            Dismiss
          </button>
        </div>
      )}
      {errorMsg && (
        <div className="bg-rose-50 border border-rose-200 text-rose-800 px-4 py-3 rounded-xl text-sm flex items-center justify-between">
          <span className="flex items-center gap-2">
            <XCircle className="w-4 h-4" />
            {errorMsg}
          </span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-600 hover:text-rose-800 text-xs font-semibold">
            Dismiss
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-slate-200 gap-6 overflow-x-auto">
        <button
          onClick={() => setActiveTab('manifests')}
          className={`pb-3 text-sm font-semibold border-b-2 transition-colors whitespace-nowrap flex items-center gap-2 ${
            activeTab === 'manifests'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <Truck className="w-4 h-4" />
          Transfer Manifests ({manifests.length})
        </button>
        {isManager && (
          <>
            <button
              onClick={() => setActiveTab('bags')}
              className={`pb-3 text-sm font-semibold border-b-2 transition-colors whitespace-nowrap flex items-center gap-2 ${
                activeTab === 'bags'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              <Boxes className="w-4 h-4" />
              Consolidation Bags ({bags.length})
            </button>
            <button
              onClick={() => setActiveTab('discrepancies')}
              className={`pb-3 text-sm font-semibold border-b-2 transition-colors whitespace-nowrap flex items-center gap-2 ${
                activeTab === 'discrepancies'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              <AlertTriangle className="w-4 h-4" />
              Discrepancies ({discrepancies.length})
            </button>
          </>
        )}
      </div>

      {/* Tab Content */}
      {loading ? (
        <div className="p-4 sm:p-12 text-center bg-white rounded-2xl border border-slate-200 text-slate-500">
          Loading linehaul operations...
        </div>
      ) : activeTab === 'manifests' ? (
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
          {manifests.length === 0 ? (
            <div className="p-4 sm:p-12 text-center text-slate-500">
              <Truck className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="font-semibold text-slate-700">No linehaul manifests found</p>
              <p className="text-sm text-slate-500 mt-1">
                Create a branch-to-branch manifest to consolidate bags and dispatch fleet vehicles.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    <th className="py-3.5 px-6">Manifest</th>
                    <th className="py-3.5 px-6">Corridor</th>
                    <th className="py-3.5 px-6">Vehicle & Seal</th>
                    <th className="py-3.5 px-6">Load Summary</th>
                    <th className="py-3.5 px-6">Status</th>
                    <th className="py-3.5 px-6 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm">
                  {manifests.map((m) => (
                    <tr key={m.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-4 px-6">
                        <p className="font-mono font-bold text-slate-900">{m.manifest_number}</p>
                        <p className="text-xs text-slate-400">
                          {new Date(m.created_at).toLocaleString()}
                        </p>
                      </td>
                      <td className="py-4 px-6">
                        <div className="flex items-center gap-1.5 text-slate-800 font-medium">
                          <span>{m.origin_branch_name || `Branch #${m.origin_branch_id}`}</span>
                          <ArrowRightLeft className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span>{m.dest_branch_name || `Branch #${m.dest_branch_id}`}</span>
                        </div>
                      </td>
                      <td className="py-4 px-6">
                        <p className="font-semibold text-slate-800">{m.vehicle_number || 'Unassigned'}</p>
                        <p className="text-xs text-slate-500">
                          {m.seal_number ? `Seal: ${m.seal_number}` : 'Unsealed'}
                          {m.driver_name ? ` • ${m.driver_name}` : ''}
                        </p>
                      </td>
                      <td className="py-4 px-6">
                        <p className="font-semibold text-slate-900">
                          {m.received_parcel_count} / {m.expected_parcel_count} parcels
                        </p>
                        <p className="text-xs text-slate-500">
                          {m.bags.length} bag(s) • {m.total_weight_kg.toFixed(1)} kg
                        </p>
                      </td>
                      <td className="py-4 px-6">
                        <Badge status={m.status} />
                      </td>
                      <td className="py-4 px-6 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {(m.status === 'DRAFT' || m.status === 'SEALED') && isManager && (
                            <button
                              onClick={() => {
                                setDispatchTarget(m);
                                setDispatchForm({
                                  vehicle_id: m.vehicle_id ? m.vehicle_id.toString() : '',
                                  driver_id: m.driver_id ? m.driver_id.toString() : '',
                                  seal_number: m.seal_number || '',
                                  notes: '',
                                });
                              }}
                              className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 text-xs font-semibold"
                            >
                              Dispatch
                            </button>
                          )}
                          {m.status === 'IN_TRANSIT' && (
                            <button
                              onClick={() => handleArriveManifest(m)}
                              className="px-3 py-1.5 rounded-lg bg-cyan-50 text-cyan-700 hover:bg-cyan-100 text-xs font-semibold"
                            >
                              Mark Arrived
                            </button>
                          )}
                          {(m.status === 'IN_TRANSIT' || m.status === 'ARRIVED') && isManager && (
                            <button
                              onClick={() => openReconcileModal(m)}
                              className="px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 text-xs font-semibold inline-flex items-center gap-1"
                            >
                              <PackageCheck className="w-3.5 h-3.5" />
                              Reconcile
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : activeTab === 'bags' ? (
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
          {bags.length === 0 ? (
            <div className="p-4 sm:p-12 text-center text-slate-500">
              <Boxes className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="font-semibold text-slate-700">No consolidation bags created</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    <th className="py-3.5 px-6">Bag Code</th>
                    <th className="py-3.5 px-6">Corridor</th>
                    <th className="py-3.5 px-6">Contents</th>
                    <th className="py-3.5 px-6">Seal</th>
                    <th className="py-3.5 px-6">Status</th>
                    <th className="py-3.5 px-6 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm">
                  {bags.map((bag) => (
                    <tr key={bag.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-4 px-6 font-mono font-bold text-slate-900">{bag.bag_code}</td>
                      <td className="py-4 px-6 text-slate-700">
                        {bag.origin_branch_name} → {bag.dest_branch_name}
                      </td>
                      <td className="py-4 px-6">
                        <span className="font-semibold text-slate-900">{bag.parcel_count} parcels</span>
                        <span className="text-xs text-slate-500 ml-2">({bag.total_weight_kg.toFixed(1)} kg)</span>
                      </td>
                      <td className="py-4 px-6 font-mono text-xs text-slate-600">{bag.seal_number || '—'}</td>
                      <td className="py-4 px-6">
                        <Badge status={bag.status} />
                      </td>
                      <td className="py-4 px-6 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {bag.status === 'OPEN' && (
                            <>
                              <button
                                onClick={() => {
                                  setAttachBagTarget(bag);
                                  setSelectedBagParcelIds([]);
                                }}
                                className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 text-xs font-semibold"
                              >
                                Add Parcels
                              </button>
                              <button
                                onClick={() => handleSealBag(bag)}
                                className="px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 text-xs font-semibold inline-flex items-center gap-1"
                              >
                                <Lock className="w-3.5 h-3.5" />
                                Seal Bag
                              </button>
                            </>
                          )}
                          {bag.status === 'RECEIVED' && (
                            <button
                              onClick={() => handleDebag(bag)}
                              className="px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 text-xs font-semibold inline-flex items-center gap-1"
                            >
                              <Unlock className="w-3.5 h-3.5" />
                              De-bag at Dest
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => setDiscModalOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs rounded-xl"
            >
              <AlertTriangle className="w-4 h-4" />
              Log Transfer Discrepancy
            </button>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
            {discrepancies.length === 0 ? (
              <div className="p-4 sm:p-12 text-center text-slate-500">
                <ShieldCheck className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
                <p className="font-semibold text-slate-700">Zero open transfer discrepancies</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                      <th className="py-3.5 px-6">Manifest / Parcel</th>
                      <th className="py-3.5 px-6">Type & Severity</th>
                      <th className="py-3.5 px-6">Description</th>
                      <th className="py-3.5 px-6">Status</th>
                      <th className="py-3.5 px-6 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-sm">
                    {discrepancies.map((d) => (
                      <tr key={d.id} className="hover:bg-slate-50/70 transition-colors">
                        <td className="py-4 px-6">
                          <p className="font-mono font-semibold text-slate-900">{d.manifest_number || `M#${d.manifest_id}`}</p>
                          <p className="text-xs text-slate-500 font-mono">{d.tracking_number || 'Manifest-level'}</p>
                        </td>
                        <td className="py-4 px-6">
                          <div className="flex items-center gap-2">
                            <Badge status={d.discrepancy_type} />
                            <Badge status={d.severity} />
                          </div>
                        </td>
                        <td className="py-4 px-6 max-w-md text-slate-700">
                          <p>{d.description}</p>
                          {d.resolution_notes && (
                            <p className="text-xs text-emerald-700 mt-1">Resolution: {d.resolution_notes}</p>
                          )}
                        </td>
                        <td className="py-4 px-6">
                          <Badge status={d.status} />
                        </td>
                        <td className="py-4 px-6 text-right">
                          {d.status !== 'RESOLVED' && (
                            <button
                              onClick={() => {
                                setResolveTarget(d);
                                setResolveForm({
                                  status: 'RESOLVED',
                                  resolution_notes: '',
                                  release_parcel_to_dest: false,
                                });
                              }}
                              className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold"
                            >
                              Resolve
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Create Manifest Modal */}
      <Modal
        isOpen={manifestModalOpen}
        onClose={() => setManifestModalOpen(false)}
        title="Create Linehaul Transfer Manifest"
        maxWidth="lg"
      >
        <form onSubmit={handleCreateManifest} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Origin Branch *</label>
              <select
                required
                value={manifestForm.origin_branch_id}
                onChange={(e) =>
                  setManifestForm({ ...manifestForm, origin_branch_id: e.target.value, bag_ids: [], parcel_ids: [] })
                }
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                <option value="">Select origin hub</option>
                {branches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.branch_code} - {b.branch_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Destination Branch *</label>
              <select
                required
                value={manifestForm.dest_branch_id}
                onChange={(e) =>
                  setManifestForm({ ...manifestForm, dest_branch_id: e.target.value, bag_ids: [], parcel_ids: [] })
                }
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                <option value="">Select destination hub</option>
                {branches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.branch_code} - {b.branch_name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Linehaul Vehicle</label>
              <select
                value={manifestForm.vehicle_id}
                onChange={(e) => setManifestForm({ ...manifestForm, vehicle_id: e.target.value })}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                <option value="">Assign later or select available vehicle</option>
                {vehicles
                  .filter((v) => v.status === 'AVAILABLE' && v.is_active)
                  .map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.vehicle_number} ({v.vehicle_type} - {v.max_weight_kg}kg)
                    </option>
                  ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Driver</label>
              <select
                value={manifestForm.driver_id}
                onChange={(e) => setManifestForm({ ...manifestForm, driver_id: e.target.value })}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                <option value="">Optional driver</option>
                {drivers.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.full_name} ({d.role})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {manifestForm.origin_branch_id && manifestForm.dest_branch_id && (
            <div className="space-y-3 bg-slate-50 p-4 rounded-xl border border-slate-200">
              <div>
                <p className="text-xs font-bold text-slate-700 mb-2">
                  Sealed Bags on Corridor ({corridorSealedBags(manifestForm.origin_branch_id, manifestForm.dest_branch_id).length})
                </p>
                <div className="flex flex-wrap gap-2">
                  {corridorSealedBags(manifestForm.origin_branch_id, manifestForm.dest_branch_id).map((bag) => {
                    const checked = manifestForm.bag_ids.includes(bag.id);
                    return (
                      <label key={bag.id} className="inline-flex items-center gap-1.5 text-xs bg-white px-2.5 py-1.5 rounded-lg border border-slate-200 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => {
                            const next = e.target.checked
                              ? [...manifestForm.bag_ids, bag.id]
                              : manifestForm.bag_ids.filter((id) => id !== bag.id);
                            setManifestForm({ ...manifestForm, bag_ids: next });
                          }}
                        />
                        <span className="font-mono font-semibold">{bag.bag_code}</span>
                        <span className="text-slate-500">({bag.parcel_count}p)</span>
                      </label>
                    );
                  })}
                </div>
              </div>
              <div>
                <p className="text-xs font-bold text-slate-700 mb-2">
                  Loose Parcels AT_ORIGIN_BRANCH ({corridorEligibleParcels(manifestForm.origin_branch_id, manifestForm.dest_branch_id).length})
                </p>
                <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto">
                  {corridorEligibleParcels(manifestForm.origin_branch_id, manifestForm.dest_branch_id).map((p) => {
                    const checked = manifestForm.parcel_ids.includes(p.id);
                    return (
                      <label key={p.id} className="inline-flex items-center gap-1.5 text-xs bg-white px-2.5 py-1.5 rounded-lg border border-slate-200 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => {
                            const next = e.target.checked
                              ? [...manifestForm.parcel_ids, p.id]
                              : manifestForm.parcel_ids.filter((id) => id !== p.id);
                            setManifestForm({ ...manifestForm, parcel_ids: next });
                          }}
                        />
                        <span className="font-mono font-semibold">{p.tracking_number}</span>
                        <span className="text-slate-500">({p.weight_kg}kg)</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Seal Number (Optional)</label>
            <input
              type="text"
              placeholder="e.g. SEAL-LH-001"
              value={manifestForm.seal_number}
              onChange={(e) => setManifestForm({ ...manifestForm, seal_number: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm"
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setManifestModalOpen(false)} className="px-4 py-2 text-slate-600 font-semibold text-sm">
              Cancel
            </button>
            <button type="submit" className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-xl text-sm hover:bg-indigo-700">
              Create Manifest
            </button>
          </div>
        </form>
      </Modal>

      {/* Create Bag Modal */}
      <Modal isOpen={bagModalOpen} onClose={() => setBagModalOpen(false)} title="Create Consolidation Bag" maxWidth="md">
        <form onSubmit={handleCreateBag} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Origin Branch *</label>
            <select
              required
              value={bagForm.origin_branch_id}
              onChange={(e) => setBagForm({ ...bagForm, origin_branch_id: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm"
            >
              <option value="">Select origin branch</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.branch_code} - {b.branch_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Destination Branch *</label>
            <select
              required
              value={bagForm.dest_branch_id}
              onChange={(e) => setBagForm({ ...bagForm, dest_branch_id: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm"
            >
              <option value="">Select destination branch</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.branch_code} - {b.branch_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Notes</label>
            <input
              type="text"
              value={bagForm.notes}
              onChange={(e) => setBagForm({ ...bagForm, notes: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setBagModalOpen(false)} className="px-4 py-2 text-slate-600 font-semibold text-sm">
              Cancel
            </button>
            <button type="submit" className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-xl text-sm hover:bg-indigo-700">
              Create Bag
            </button>
          </div>
        </form>
      </Modal>

      {/* Attach Parcels to Bag Modal */}
      <Modal
        isOpen={!!attachBagTarget}
        onClose={() => setAttachBagTarget(null)}
        title={`Consolidate Parcels into ${attachBagTarget?.bag_code || ''}`}
        maxWidth="md"
      >
        {attachBagTarget && (
          <form onSubmit={handleAttachParcelsToBag} className="space-y-4">
            <div className="space-y-2 max-h-60 overflow-y-auto bg-slate-50 p-3 rounded-xl border border-slate-200">
              {corridorEligibleParcels(
                attachBagTarget.origin_branch_id.toString(),
                attachBagTarget.dest_branch_id.toString()
              ).length === 0 ? (
                <p className="text-xs text-slate-500">No eligible AT_ORIGIN_BRANCH parcels found for this corridor.</p>
              ) : (
                corridorEligibleParcels(
                  attachBagTarget.origin_branch_id.toString(),
                  attachBagTarget.dest_branch_id.toString()
                ).map((p) => (
                  <label key={p.id} className="flex items-center justify-between text-xs bg-white p-2.5 rounded-lg border border-slate-200 cursor-pointer">
                    <span className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={selectedBagParcelIds.includes(p.id)}
                        onChange={(e) => {
                          setSelectedBagParcelIds(
                            e.target.checked
                              ? [...selectedBagParcelIds, p.id]
                              : selectedBagParcelIds.filter((id) => id !== p.id)
                          );
                        }}
                      />
                      <span className="font-mono font-semibold">{p.tracking_number}</span>
                    </span>
                    <span className="text-slate-500">{p.weight_kg} kg</span>
                  </label>
                ))
              )}
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={() => setAttachBagTarget(null)} className="px-4 py-2 text-slate-600 font-semibold text-sm">
                Cancel
              </button>
              <button type="submit" disabled={selectedBagParcelIds.length === 0} className="px-6 py-2 bg-indigo-600 disabled:opacity-50 text-white font-semibold rounded-xl text-sm">
                Load Selected Parcels
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* Dispatch Manifest Modal */}
      <Modal
        isOpen={!!dispatchTarget}
        onClose={() => setDispatchTarget(null)}
        title={`Dispatch Manifest ${dispatchTarget?.manifest_number || ''}`}
        maxWidth="md"
      >
        <form onSubmit={handleDispatchManifest} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Assign Vehicle *</label>
            <select
              required
              value={dispatchForm.vehicle_id}
              onChange={(e) => setDispatchForm({ ...dispatchForm, vehicle_id: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm"
            >
              <option value="">Select available vehicle</option>
              {vehicles
                .filter((v) => v.status === 'AVAILABLE' && v.is_active)
                .map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.vehicle_number} ({v.max_weight_kg} kg max)
                  </option>
                ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Linehaul Seal Number</label>
            <input
              type="text"
              placeholder="Auto-generated if blank"
              value={dispatchForm.seal_number}
              onChange={(e) => setDispatchForm({ ...dispatchForm, seal_number: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setDispatchTarget(null)} className="px-4 py-2 text-slate-600 font-semibold text-sm">
              Cancel
            </button>
            <button type="submit" className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-xl text-sm hover:bg-indigo-700">
              Confirm Linehaul Dispatch
            </button>
          </div>
        </form>
      </Modal>

      {/* Reconcile Modal */}
      <Modal
        isOpen={!!reconcileTarget}
        onClose={() => setReconcileTarget(null)}
        title={`Inward Reconciliation: ${reconcileTarget?.manifest_number || ''}`}
        maxWidth="lg"
      >
        {reconcileTarget && (
          <form onSubmit={handleReconcileSubmit} className="space-y-4">
            <div className="max-h-64 overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-xl">
              {reconcileTarget.items.map((item) => (
                <div key={item.id} className="p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-white">
                  <div>
                    <p className="font-mono font-bold text-sm text-slate-900">{item.tracking_number}</p>
                    <p className="text-xs text-slate-500">
                      {item.weight_kg} kg {item.bag_code ? `• Bag ${item.bag_code}` : '• Loose'}
                    </p>
                  </div>
                  <select
                    value={itemOutcomes[item.tracking_number] || 'RECEIVED'}
                    onChange={(e) =>
                      setItemOutcomes({
                        ...itemOutcomes,
                        [item.tracking_number]: e.target.value as 'RECEIVED' | 'DAMAGED' | 'MISSING',
                      })
                    }
                    className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-semibold"
                  >
                    <option value="RECEIVED">Received Intact</option>
                    <option value="DAMAGED">Damaged</option>
                    <option value="MISSING">Missing / Short</option>
                  </select>
                </div>
              ))}
            </div>

            <label className="flex items-center gap-2 text-sm text-slate-700 font-medium">
              <input type="checkbox" checked={sealIntact} onChange={(e) => setSealIntact(e.target.checked)} />
              Linehaul seal intact on arrival ({reconcileTarget.seal_number || 'N/A'})
            </label>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">
                Unexpected Excess Tracking Numbers (comma-separated, optional)
              </label>
              <input
                type="text"
                value={excessInput}
                onChange={(e) => setExcessInput(e.target.value)}
                placeholder="e.g. LF-2026-EXCESS1"
                className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Reconciliation Notes</label>
              <input
                type="text"
                value={reconcileNotes}
                onChange={(e) => setReconcileNotes(e.target.value)}
                className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={() => setReconcileTarget(null)} className="px-4 py-2 text-slate-600 font-semibold text-sm">
                Cancel
              </button>
              <button type="submit" className="px-6 py-2 bg-emerald-600 text-white font-semibold rounded-xl text-sm hover:bg-emerald-700">
                Complete Reconciliation
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* Report Discrepancy Modal */}
      <Modal isOpen={discModalOpen} onClose={() => setDiscModalOpen(false)} title="Log Transfer Discrepancy" maxWidth="md">
        <form onSubmit={handleReportDiscrepancy} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Manifest *</label>
            <select
              required
              value={discForm.manifest_id}
              onChange={(e) => setDiscForm({ ...discForm, manifest_id: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm"
            >
              <option value="">Select dispatched/arrived manifest</option>
              {manifests
                .filter((m) => m.status === 'IN_TRANSIT' || m.status === 'ARRIVED' || m.status === 'RECONCILED')
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.manifest_number} ({m.status})
                  </option>
                ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Type</label>
              <select
                value={discForm.discrepancy_type}
                onChange={(e) => setDiscForm({ ...discForm, discrepancy_type: e.target.value })}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                <option value="MISSING">MISSING</option>
                <option value="DAMAGED">DAMAGED</option>
                <option value="EXCESS">EXCESS</option>
                <option value="SEAL_BROKEN">SEAL_BROKEN</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Severity</label>
              <select
                value={discForm.severity}
                onChange={(e) => setDiscForm({ ...discForm, severity: e.target.value })}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                <option value="LOW">LOW</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="HIGH">HIGH</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Tracking Number (Optional)</label>
            <input
              type="text"
              value={discForm.tracking_number}
              onChange={(e) => setDiscForm({ ...discForm, tracking_number: e.target.value })}
              className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Incident Description *</label>
            <textarea
              required
              minLength={5}
              rows={3}
              value={discForm.description}
              onChange={(e) => setDiscForm({ ...discForm, description: e.target.value })}
              className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setDiscModalOpen(false)} className="px-4 py-2 text-slate-600 font-semibold text-sm">
              Cancel
            </button>
            <button type="submit" className="px-6 py-2 bg-rose-600 text-white font-semibold rounded-xl text-sm">
              Submit Discrepancy
            </button>
          </div>
        </form>
      </Modal>

      {/* Resolve Discrepancy Modal */}
      <Modal
        isOpen={!!resolveTarget}
        onClose={() => setResolveTarget(null)}
        title={`Resolve Discrepancy #${resolveTarget?.id || ''}`}
        maxWidth="md"
      >
        <form onSubmit={handleResolveDiscrepancy} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Resolution Status</label>
            <select
              value={resolveForm.status}
              onChange={(e) => setResolveForm({ ...resolveForm, status: e.target.value })}
              className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
            >
              <option value="INVESTIGATING">INVESTIGATING</option>
              <option value="RESOLVED">RESOLVED</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Resolution Notes *</label>
            <textarea
              required
              minLength={3}
              rows={3}
              value={resolveForm.resolution_notes}
              onChange={(e) => setResolveForm({ ...resolveForm, resolution_notes: e.target.value })}
              className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
            />
          </div>
          {resolveTarget?.parcel_id && resolveForm.status === 'RESOLVED' && (
            <label className="flex items-center gap-2 text-sm text-slate-700 font-medium">
              <input
                type="checkbox"
                checked={resolveForm.release_parcel_to_dest}
                onChange={(e) => setResolveForm({ ...resolveForm, release_parcel_to_dest: e.target.checked })}
              />
              Release parcel from ON_HOLD to AT_DESTINATION_BRANCH
            </label>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setResolveTarget(null)} className="px-4 py-2 text-slate-600 font-semibold text-sm">
              Cancel
            </button>
            <button type="submit" className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-xl text-sm">
              Save Resolution
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
