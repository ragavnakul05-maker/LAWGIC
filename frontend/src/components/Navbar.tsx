import React from 'react';
import {
  LayoutDashboard, FileText, Cpu, Sliders, ShieldCheck, FileCheck2, Settings, Zap, LogOut
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab }) => {
  const { user, logout } = useAuth();

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'contracts', label: 'Contracts', icon: FileText },
    { id: 'rules', label: 'Legal Rules (IR)', icon: Cpu },
    { id: 'simulator', label: 'What-If Simulator', icon: Sliders },
    { id: 'audit', label: 'Audit & Trace', icon: ShieldCheck },
    { id: 'rag', label: 'Statutory RAG', icon: FileCheck2 },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-64 bg-white/80 backdrop-blur-xl border-r border-slate-200/90 flex flex-col justify-between shrink-0 min-h-screen z-20 shadow-sm">
      <div>
        {/* Brand Logo & Tagline */}
        <div className="p-6 border-b border-slate-200/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-500 flex items-center justify-center shadow-md shadow-indigo-500/25">
              <Zap className="w-5 h-5 text-white fill-current" />
            </div>
            <div>
              <h1 className="font-extrabold text-xl tracking-tight text-slate-900">
                LAWGIC
              </h1>
              <p className="text-[10px] font-bold text-indigo-600 tracking-wider uppercase">
                Executable Rule Engine
              </p>
            </div>
          </div>
          <div className="mt-3 px-2.5 py-1.5 rounded-lg bg-indigo-50/80 border border-indigo-100 text-[11px] text-indigo-700 font-semibold shadow-xs">
            Contract → Legal IR → Math
          </div>
        </div>

        {/* Navigation Menu */}
        <nav className="p-4 space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all cursor-pointer ${
                  isActive
                    ? 'bg-gradient-to-r from-indigo-600 to-indigo-700 text-white shadow-md shadow-indigo-600/20 border border-indigo-500/30'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/90'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-500'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom User & System Status Card */}
      <div className="p-4 space-y-2.5">
        {/* User Quick Switch / Status */}
        {user && (
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-between shadow-xs">
            <div className="min-w-0 pr-2">
              <p className="text-xs font-bold text-slate-900 truncate">{user.full_name}</p>
              <p className="text-[10px] text-slate-500 truncate">{user.email}</p>
            </div>
            <button
              onClick={logout}
              title="Sign Out"
              className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Engine Status Pill */}
        <div className="p-3 rounded-xl bg-indigo-50/60 border border-indigo-100/80 shadow-xs">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-slate-700 font-medium text-[11px]">Engine Mode</span>
            <span className="inline-flex items-center gap-1.5 text-emerald-600 font-bold text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              Deterministic
            </span>
          </div>
          <p className="text-[10px] text-slate-500 leading-tight">
            Zero LLM math hallucination. 100% auditable.
          </p>
        </div>
      </div>
    </aside>
  );
};
