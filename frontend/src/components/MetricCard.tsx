import React from 'react';
import { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  change?: string;
  isNegative?: boolean;
  icon: LucideIcon;
  iconColor?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  change,
  isNegative = false,
  icon: Icon,
  iconColor = 'text-indigo-600 bg-indigo-50 border-indigo-200'
}) => {
  return (
    <div className="glass-panel glass-panel-hover p-5 rounded-2xl relative overflow-hidden">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{title}</span>
        <div className={`p-2.5 rounded-xl border ${iconColor}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
      <div className="mt-3 flex items-baseline justify-between">
        <h3 className="text-2xl font-extrabold text-slate-900 tracking-tight">{value}</h3>
        {change && (
          <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${
            isNegative ? 'bg-rose-100 text-rose-700 border border-rose-200' : 'bg-emerald-100 text-emerald-700 border border-emerald-200'
          }`}>
            {change}
          </span>
        )}
      </div>
    </div>
  );
};
