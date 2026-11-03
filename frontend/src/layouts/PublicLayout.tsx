import React from 'react';
import { Outlet, Link } from 'react-router-dom';
import { Truck, Search, ShieldCheck } from 'lucide-react';

export const PublicLayout: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      <header className="bg-white/80 backdrop-blur-md border-b border-slate-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-blue-500 flex items-center justify-center text-white shadow-md shadow-indigo-500/20">
              <Truck className="w-5 h-5" />
            </div>
            <div>
              <span className="font-extrabold text-xl text-slate-900 tracking-tight">LogiFlows</span>
              <span className="ml-2 text-xs font-semibold px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-600">Enterprise</span>
            </div>
          </Link>

          <nav className="flex items-center gap-6">
            <Link to="/tracking" className="text-sm font-semibold text-slate-600 hover:text-indigo-600 flex items-center gap-1.5 transition-colors">
              <Search className="w-4 h-4" />
              <span>Track Shipment</span>
            </Link>
            <div className="h-4 w-px bg-slate-200"></div>
            <Link to="/login" className="text-sm font-semibold text-slate-700 hover:text-indigo-600 transition-colors">
              Sign In
            </Link>
            <Link
              to="/register"
              className="text-sm font-semibold px-4 py-2 rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 transition-all shadow-sm shadow-indigo-600/30"
            >
              Get Started
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="bg-slate-900 text-slate-400 py-12 border-t border-slate-800">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white">
              <Truck className="w-4 h-4" />
            </div>
            <p className="text-sm font-medium text-slate-300">&copy; 2026 LogiFlows Logistics Systems Inc. All rights reserved.</p>
          </div>
          <div className="flex items-center gap-6 text-xs">
            <span className="flex items-center gap-1.5 text-emerald-400">
              <ShieldCheck className="w-4 h-4" />
              <span>ISO 9001 & SOC2 Certified Logistics Platform</span>
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
};

