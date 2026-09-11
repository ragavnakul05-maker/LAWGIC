import React, { useEffect, useState } from 'react';
import {
  FileText, Cpu, ShieldAlert, AlertTriangle, TrendingDown, TrendingUp, CheckCircle, Bell, ArrowRight, Sparkles, Activity
} from 'lucide-react';
import { MetricCard } from '../components/MetricCard';
import { fetchDashboardSummary } from '../services/api';
import { DashboardMetrics, ContractSummary, AlertItem } from '../types';

interface DashboardPageProps {
  onNavigate: (tab: string, contractId?: string) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigate }) => {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [recentContracts, setRecentContracts] = useState<ContractSummary[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardSummary()
      .then((data) => {
        setMetrics(data.metrics);
        setRecentContracts(data.recent_contracts);
        setAlerts(data.alerts);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <div className="inline-block w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
        <p className="text-sm text-slate-500 font-medium">Loading LAWGIC Dashboard Intelligence...</p>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* KPI Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <MetricCard
          title="Total Contracts"
          value={metrics?.total_contracts || 0}
          change="+100% active"
          icon={FileText}
          iconColor="text-indigo-600 bg-indigo-50 border-indigo-200"
        />
        <MetricCard
          title="Clauses Extracted"
          value={metrics?.clauses_extracted || 0}
          change="Traceable"
          icon={Cpu}
          iconColor="text-cyan-600 bg-cyan-50 border-cyan-200"
        />
        <MetricCard
          title="Active Valid Rules"
          value={metrics?.active_rules || 0}
          change="Validated IR"
          icon={CheckCircle}
          iconColor="text-emerald-600 bg-emerald-50 border-emerald-200"
        />
        <MetricCard
          title="Pending Reviews"
          value={metrics?.pending_reviews || 0}
          isNegative={true}
          change="Needs Review"
          icon={AlertTriangle}
          iconColor="text-amber-600 bg-amber-50 border-amber-200"
        />
      </div>

      {/* Secondary Financial Impact Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="glass-panel p-5 rounded-2xl flex items-center justify-between border border-rose-200/80 bg-gradient-to-r from-rose-50/50 to-white">
          <div>
            <span className="text-xs font-semibold text-rose-600 uppercase tracking-wider block">Potential Delay Penalties</span>
            <span className="text-2xl font-extrabold text-slate-900">${metrics?.potential_penalties.toLocaleString()}</span>
            <p className="text-[11px] text-slate-500 mt-1">Calculated via Liquidated Damages & SLA Rules</p>
          </div>
          <div className="p-3 rounded-2xl bg-rose-100 text-rose-600 border border-rose-200">
            <TrendingDown className="w-6 h-6" />
          </div>
        </div>

        <div className="glass-panel p-5 rounded-2xl flex items-center justify-between border border-emerald-200/80 bg-gradient-to-r from-emerald-50/50 to-white">
          <div>
            <span className="text-xs font-semibold text-emerald-700 uppercase tracking-wider block">Potential Volume Discounts</span>
            <span className="text-2xl font-extrabold text-slate-900">${metrics?.potential_discounts.toLocaleString()}</span>
            <p className="text-[11px] text-slate-500 mt-1">Calculated via Tiered Bulk Order Quantity Triggers</p>
          </div>
          <div className="p-3 rounded-2xl bg-emerald-100 text-emerald-600 border border-emerald-200">
            <TrendingUp className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Main Content Split: Active Alerts & Recent Contracts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left 2 Cols: Recent Contracts Table */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <FileText className="w-5 h-5 text-indigo-600" />
              Recent Managed Contracts
            </h3>
            <button
              onClick={() => onNavigate('contracts')}
              className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold flex items-center gap-1"
            >
              View All <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-100/90 border-b border-slate-200 text-slate-600 font-mono text-[11px] uppercase">
                <tr>
                  <th className="p-3">Title</th>
                  <th className="p-3">Format</th>
                  <th className="p-3">Pages</th>
                  <th className="p-3">Rules</th>
                  <th className="p-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/80 text-slate-700">
                {recentContracts.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="p-3 font-semibold text-slate-900">{c.title}</td>
                    <td className="p-3 font-mono text-slate-500">{c.file_type}</td>
                    <td className="p-3 font-mono text-slate-600">{c.page_count}</td>
                    <td className="p-3 font-mono text-indigo-600 font-bold">{c.rules_count} Rules</td>
                    <td className="p-3 text-right">
                      <button
                        onClick={() => onNavigate('contracts', c.id)}
                        className="px-3 py-1 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 font-semibold transition-all"
                      >
                        Inspect IR Studio
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Col: Active System Alerts */}
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Bell className="w-5 h-5 text-amber-500" />
              Contract Triggers & Alerts
            </h3>
            <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200 font-mono text-[10px] font-bold">
              {alerts.length} Active
            </span>
          </div>

          <div className="space-y-3">
            {alerts.map((alt) => (
              <div
                key={alt.id}
                className="p-3.5 rounded-xl bg-white border border-slate-200 space-y-1 hover:border-slate-300 shadow-sm transition-colors"
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-800">{alt.title}</span>
                  <span className="font-mono text-[10px] text-indigo-600 font-bold">{alt.rule_code}</span>
                </div>
                <p className="text-xs text-slate-600 leading-normal">{alt.message}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
