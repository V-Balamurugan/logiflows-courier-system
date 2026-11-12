import React, { useState, useEffect } from 'react';
import { Users, UserPlus, Search, Phone, Mail, GitBranch, Briefcase, KeyRound, Copy, Check } from 'lucide-react';
import { employeeApi, branchApi } from '../api';
import { User, Branch, EmployeeInviteResponse } from '../types';
import { Modal } from '../components/Modal';
import { Badge } from '../components/Badge';

export const EmployeesPage: React.FC = () => {
  const [employees, setEmployees] = useState<User[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [inviteDetails, setInviteDetails] = useState<EmployeeInviteResponse | null>(null);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    password: '',
    phone: '',
    role: 'DELIVERY_AGENT',
    branch_id: '',
  });

  const loadData = async () => {
    setLoading(true);
    try {
      const [empList, branchList] = await Promise.all([
        employeeApi.list(),
        branchApi.list(),
      ]);
      setEmployees(empList);
      setBranches(branchList);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleGenerateInvite = async (empId: number) => {
    setInviteLoading(true);
    setInviteModalOpen(true);
    setCopied(false);
    try {
      const res = await employeeApi.invite(empId);
      setInviteDetails(res);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to generate one-time invite token');
      setInviteModalOpen(false);
    } finally {
      setInviteLoading(false);
    }
  };

  const handleCopyInvite = () => {
    if (inviteDetails?.invite_url) {
      navigator.clipboard.writeText(inviteDetails.invite_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await employeeApi.create({
        ...formData,
        branch_id: formData.branch_id ? parseInt(formData.branch_id) : undefined,
      });
      setIsModalOpen(false);
      setFormData({
        full_name: '',
        email: '',
        password: '',
        phone: '',
        role: 'DELIVERY_AGENT',
        branch_id: '',
      });
      loadData();
    } catch (err) {
      alert('Error creating employee. Verify email is unique.');
    }
  };

  const filteredEmployees = employees.filter(
    (e) =>
      e.full_name.toLowerCase().includes(search.toLowerCase()) ||
      e.email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Staff & Employee Roster</h1>
          <p className="text-xs text-slate-500 mt-1">
            Manage organization administrators, branch hub managers, and field delivery agents.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-sm flex items-center gap-2 transition-all"
        >
          <UserPlus className="w-4 h-4" />
          <span>Onboard Employee</span>
        </button>
      </div>

      <div className="flex items-center gap-4 bg-white p-4 rounded-2xl border border-slate-200 shadow-2xs">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search employee by name, email..."
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
          />
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 uppercase font-semibold">
                <th className="py-3.5 px-6">Employee</th>
                <th className="py-3.5 px-4">Role</th>
                <th className="py-3.5 px-4">Assigned Branch Hub</th>
                <th className="py-3.5 px-4">Contact Phone</th>
                <th className="py-3.5 px-6 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {filteredEmployees.map((emp) => {
                const branchObj = branches.find((b) => b.id === emp.branch_id);
                return (
                  <tr key={emp.id} className="hover:bg-slate-50/80">
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-slate-700">
                          {emp.full_name.charAt(0)}
                        </div>
                        <div>
                          <p className="font-bold text-slate-900">{emp.full_name}</p>
                          <p className="text-[11px] text-slate-500 flex items-center gap-1 mt-0.5">
                            <Mail className="w-3 h-3" /> {emp.email}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="py-4 px-4">
                      <Badge status={emp.role} variant="role" />
                    </td>
                    <td className="py-4 px-4 text-slate-600">
                      {branchObj ? (
                        <span className="flex items-center gap-1.5 font-semibold text-slate-800">
                          <GitBranch className="w-3.5 h-3.5 text-indigo-500" />
                          <span>{branchObj.branch_name} ({branchObj.branch_code})</span>
                        </span>
                      ) : (
                        <span className="text-slate-400">Headquarters / All Hubs</span>
                      )}
                    </td>
                    <td className="py-4 px-4 text-slate-600">
                      {emp.phone || 'N/A'}
                    </td>
                    <td className="py-4 px-6 text-right space-x-2 whitespace-nowrap">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        Active
                      </span>
                      <button
                        onClick={() => handleGenerateInvite(emp.id)}
                        className="px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 font-semibold text-[11px] transition-colors inline-flex items-center gap-1"
                        title="Generate one-time invite token link"
                      >
                        <KeyRound className="w-3 h-3" />
                        <span>Invite Link</span>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Onboard Employee Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Onboard New Employee">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Full Name *</label>
            <input
              type="text"
              required
              placeholder="e.g. Ramesh Saxena"
              value={formData.full_name}
              onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
              className="w-full px-3 py-2 border rounded-xl text-xs"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Email Address *</label>
            <input
              type="email"
              required
              placeholder="ramesh@logiflows.com"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full px-3 py-2 border rounded-xl text-xs"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Temporary Password *</label>
            <input
              type="password"
              required
              minLength={6}
              placeholder="••••••••"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className="w-full px-3 py-2 border rounded-xl text-xs"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Contact Phone</label>
            <input
              type="text"
              placeholder="+91 98765 43210"
              value={formData.phone}
              onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              className="w-full px-3 py-2 border rounded-xl text-xs"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Role *</label>
              <select
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              >
                <option value="DELIVERY_AGENT">Delivery Agent</option>
                <option value="BRANCH_MANAGER">Branch Manager</option>
                <option value="ORG_ADMIN">Organization Admin</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Branch Hub</label>
              <select
                value={formData.branch_id}
                onChange={(e) => setFormData({ ...formData, branch_id: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl text-xs"
              >
                <option value="">Select branch hub...</option>
                {branches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.branch_name} ({b.branch_code})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button
            type="submit"
            className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-md mt-4"
          >
            Create Staff Profile
          </button>
        </form>
      </Modal>

      {/* One-Time Invite Token Modal */}
      <Modal
        isOpen={inviteModalOpen}
        onClose={() => { setInviteModalOpen(false); setInviteDetails(null); }}
        title="One-Time Staff Activation Token"
      >
        {inviteLoading ? (
          <div className="py-8 text-center text-slate-400 text-xs">
            Generating cryptographically signed invite link...
          </div>
        ) : inviteDetails ? (
          <div className="space-y-4">
            <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-xl text-xs text-indigo-900">
              <p className="font-semibold">Cryptographic Single-Use Invitation</p>
              <p className="text-[11px] text-indigo-700 mt-0.5">
                This token is valid for {inviteDetails.expires_in_hours} hours. Once consumed to activate credentials, it will be automatically revoked.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                Activation Link ({inviteDetails.email})
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={inviteDetails.invite_url}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono text-slate-700 select-all"
                />
                <button
                  type="button"
                  onClick={handleCopyInvite}
                  className="px-3 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-sm flex items-center gap-1.5 shrink-0"
                >
                  {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  <span>{copied ? 'Copied!' : 'Copy'}</span>
                </button>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => { setInviteModalOpen(false); setInviteDetails(null); }}
                className="px-4 py-2 border border-slate-200 rounded-xl text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                Done
              </button>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
};

