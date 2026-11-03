import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Package,
  PackagePlus,
  GitBranch,
  Users,
  UserCheck,
  Truck,
  QrCode,
  FileSpreadsheet,
  User,
  LogOut,
  SendHorizontal,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { Badge } from './Badge';

export const Sidebar: React.FC = () => {
  const { user, logout } = useAuth();
  if (!user) return null;

  const role = user.role;

  const navItems = [
    { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard, roles: ['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER', 'DELIVERY_AGENT', 'CUSTOMER'] },
    { label: 'Book Shipment', path: '/book-parcel', icon: PackagePlus, roles: ['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER', 'CUSTOMER'] },
    { label: 'All Parcels', path: '/parcels', icon: Package, roles: ['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER', 'CUSTOMER', 'DELIVERY_AGENT'] },
    { label: 'Assignments', path: '/assignments', icon: SendHorizontal, roles: ['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER', 'DELIVERY_AGENT'] },
    { label: 'QR Custody Scan', path: '/qr-scanner', icon: QrCode, roles: ['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER', 'DELIVERY_AGENT'] },
    { label: 'Branches', path: '/branches', icon: GitBranch, roles: ['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER'] },
    { label: 'Employees', path: '/employees', icon: Users, roles: ['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER'] },
    { label: 'Customers', path: '/customers', icon: UserCheck, roles: ['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER'] },
    { label: 'Fleet & Vehicles', path: '/vehicles', icon: Truck, roles: ['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER'] },
    { label: 'Reports & Export', path: '/reports', icon: FileSpreadsheet, roles: ['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER'] },
    { label: 'My Profile', path: '/profile', icon: User, roles: ['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER', 'DELIVERY_AGENT', 'CUSTOMER'] },
  ];

  const filteredNav = navItems.filter((item) => item.roles.includes(role));

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 min-h-screen flex flex-col justify-between border-r border-slate-800 shrink-0">
      <div>
        {/* Brand */}
        <div className="h-16 flex items-center gap-3 px-6 border-b border-slate-800/80 bg-slate-950/40">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-blue-500 flex items-center justify-center text-white shadow-md shadow-indigo-500/20">
            <Truck className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-extrabold text-white text-lg tracking-tight">LogiFlows</h1>
            <p className="text-[10px] text-slate-400 font-medium tracking-wide">ENTERPRISE COURIER</p>
          </div>
        </div>

        {/* User Card */}
        <div className="px-5 py-4 border-b border-slate-800/60 bg-slate-800/20">
          <p className="text-xs text-slate-400 font-medium">Logged in as</p>
          <p className="text-sm font-semibold text-white truncate mt-0.5">{user.full_name}</p>
          <div className="mt-2">
            <Badge status={user.role} variant="role" />
          </div>
        </div>

        {/* Navigation links */}
        <nav className="p-4 space-y-1">
          {filteredNav.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                  }`
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Footer / Logout */}
      <div className="p-4 border-t border-slate-800">
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium text-rose-400 hover:bg-rose-500/10 hover:text-rose-300 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
};

