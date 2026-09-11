import React from 'react';
import { SimulationResponse } from '../types';
import { TrendingUp, TrendingDown, Minus, CheckCircle2 } from 'lucide-react';

interface ScenarioComparisonTableProps {
  data: SimulationResponse | null;
}

export const ScenarioComparisonTable: React.FC<ScenarioComparisonTableProps> = ({ data }) => {
  if (!data) return null;

  const baseline = data.baseline;
  const scenarios = data.scenarios;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-bold text-slate-900 tracking-tight">Scenario Financial Impact Matrix</h4>
        <span className="text-xs text-indigo-600 font-semibold">Calculated via Deterministic Rule Engine</span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-100/80 border-b border-slate-200 text-slate-600 font-mono text-[11px] uppercase tracking-wider">
            <tr>
              <th className="p-3.5">Scenario</th>
              <th className="p-3.5">Key Variable Inputs</th>
              <th className="p-3.5 text-right">Financial Impact ($)</th>
              <th className="p-3.5 text-right">Delta ($)</th>
              <th className="p-3.5 text-right">% Change</th>
              <th className="p-3.5">Rule Summary</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 text-slate-700">
            {/* Baseline Row */}
            <tr className="bg-indigo-50/50 font-medium">
              <td className="p-3.5 font-bold text-indigo-700 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-indigo-600" />
                {baseline.scenario_name}
              </td>
              <td className="p-3.5 font-mono text-[11px] text-slate-600">
                {Object.entries(baseline.variables).slice(0, 3).map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`).join(', ')}
              </td>
              <td className="p-3.5 text-right font-mono font-bold text-slate-900">
                ${baseline.financial_impact.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </td>
              <td className="p-3.5 text-right font-mono text-slate-500">$0.00</td>
              <td className="p-3.5 text-right font-mono text-slate-500">0.0%</td>
              <td className="p-3.5 text-[11px] text-slate-500 truncate max-w-xs">{baseline.calculation_summary}</td>
            </tr>

            {/* Scenario Rows */}
            {scenarios.map((sc, idx) => {
              const isIncrease = sc.difference_from_baseline > 0;
              const isDecrease = sc.difference_from_baseline < 0;

              return (
                <tr key={idx} className="hover:bg-slate-50 transition-colors">
                  <td className="p-3.5 font-semibold text-slate-900">{sc.scenario_name}</td>
                  <td className="p-3.5 font-mono text-[11px] text-slate-600">
                    {Object.entries(sc.variables).slice(0, 3).map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`).join(', ')}
                  </td>
                  <td className={`p-3.5 text-right font-mono font-bold ${
                    isIncrease ? 'text-rose-600' : isDecrease ? 'text-emerald-600' : 'text-slate-800'
                  }`}>
                    ${sc.financial_impact.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td className={`p-3.5 text-right font-mono font-semibold ${
                    isIncrease ? 'text-rose-600' : isDecrease ? 'text-emerald-600' : 'text-slate-500'
                  }`}>
                    {isIncrease ? `+$${sc.difference_from_baseline.toLocaleString()}` : `$${sc.difference_from_baseline.toLocaleString()}`}
                  </td>
                  <td className="p-3.5 text-right">
                    <span className={`inline-flex items-center gap-1 font-mono font-bold text-[11px] px-2.5 py-0.5 rounded-full ${
                      isIncrease ? 'bg-rose-100 text-rose-700' : isDecrease ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'
                    }`}>
                      {isIncrease && <TrendingUp className="w-3 h-3" />}
                      {isDecrease && <TrendingDown className="w-3 h-3" />}
                      {!isIncrease && !isDecrease && <Minus className="w-3 h-3" />}
                      {sc.percentage_change > 0 ? `+${sc.percentage_change}%` : `${sc.percentage_change}%`}
                    </span>
                  </td>
                  <td className="p-3.5 text-[11px] text-slate-600 truncate max-w-xs">
                    {sc.calculation_summary}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
