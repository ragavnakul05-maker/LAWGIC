import React from 'react';
import { Search, Sparkles, LogOut, Shield } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface HeaderProps {
  title: string;
  subtitle?: string;
  onQuickSimulate?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ title, subtitle, onQuickSimulate }) => {
  const { user, logout } = useAuth();

  const getInitials = (name?: string) => {
    if (!name) return 'LA';
    return name
      .split(' ')
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0].toUpperCase())
      .join('');
  };

  return (
    <header className="h-16 border-b border-slate-200/90 bg-white/70 backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-20 shadow-xs">
      <div>
        <h2 className="text-lg font-bold text-slate-900 tracking-tight">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500 font-medium">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-4">
        {/* Search Bar */}
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search contracts, clauses, or rules..."
            className="w-56 lg:w-64 bg-slate-100/90 border border-slate-200/90 rounded-xl pl-9 pr-4 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all"
          />
        </div>

        {onQuickSimulate && (
          <button
            onClick={onQuickSimulate}
            className="hidden sm:flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-semibold text-xs px-3.5 py-2 rounded-xl shadow-md shadow-indigo-600/20 transition-all cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Run What-If Simulation</span>
          </button>
        )}

        {/* User Profile Pill & Sign Out */}
        <div className="flex items-center gap-3 pl-3 border-l border-slate-200">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-600 to-cyan-500 border border-indigo-200 flex items-center justify-center text-xs font-bold text-white shadow-xs">
              {getInitials(user?.full_name)}
            </div>
            <div className="text-left hidden lg:block">
              <p className="text-xs font-bold text-slate-800 leading-tight">
                {user?.full_name || 'Legal Counsel'}
              </p>
              <div className="flex items-center gap-1 text-[10px] text-indigo-600 font-medium">
                <Shield className="w-3 h-3" />
                <span className="truncate max-w-[140px]">{user?.role || 'Verified User'}</span>
              </div>
            </div>
          </div>

          <button
            onClick={logout}
            title="Sign Out"
            className="p-2 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 border border-transparent hover:border-rose-100 transition-all cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};
