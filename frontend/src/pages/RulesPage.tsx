import React, { useEffect, useState } from 'react';
import { Cpu, ShieldCheck, AlertTriangle, Filter, Search, Code2 } from 'lucide-react';
import { fetchRules, validateRule } from '../services/api';
import { RuleSummary } from '../types';
import { RuleEditorModal } from '../components/RuleEditorModal';

export const RulesPage: React.FC = () => {
  const [rules, setRules] = useState<RuleSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFilter, setSelectedFilter] = useState<string>('ALL');
  const [selectedRuleModal, setSelectedRuleModal] = useState<RuleSummary | null>(null);

  const loadRules = () => {
    fetchRules()
      .then((data) => {
        setRules(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadRules();
  }, []);

  const filterOptions = [
    { id: 'ALL', label: 'All Rules' },
    { id: 'late_payment_interest', label: 'Payment Interest' },
    { id: 'delivery_delay_penalty', label: 'Delivery Penalties' },
    { id: 'volume_discount', label: 'Volume Discounts' },
    { id: 'sla_penalty', label: 'SLA Breach' },
    { id: 'price_escalation', label: 'Price Escalation' },
    { id: 'renewal_condition', label: 'Renewal' },
  ];

  const filteredRules = rules.filter((r) => {
    if (selectedFilter === 'ALL') return true;
    return r.rule_type === selectedFilter;
  });

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Structured Legal IR Repository</h2>
          <p className="text-xs text-slate-500 font-medium mt-0.5">
            Validated machine-readable business rules decompiled from contractual clauses.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-600">Filter Category:</span>
          <select
            value={selectedFilter}
            onChange={(e) => setSelectedFilter(e.target.value)}
            className="bg-white border border-slate-200 rounded-xl px-3 py-1.5 text-xs font-semibold text-slate-800 focus:border-indigo-500 shadow-xs"
          >
            {filterOptions.map((f) => (
              <option key={f.id} value={f.id}>{f.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Rules Table */}
      <div className="glass-panel rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-100/90 border-b border-slate-200 text-slate-600 font-mono text-[11px] uppercase tracking-wider">
            <tr>
              <th className="p-4">Rule Code</th>
              <th className="p-4">Rule Title</th>
              <th className="p-4">Type</th>
              <th className="p-4">Condition</th>
              <th className="p-4">Action</th>
              <th className="p-4">Status</th>
              <th className="p-4">Source Clause</th>
              <th className="p-4 text-right">Inspect IR</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 text-slate-700">
            {loading ? (
              <tr>
                <td colSpan={8} className="p-8 text-center text-slate-500">Loading Legal IR repository...</td>
              </tr>
            ) : filteredRules.length === 0 ? (
              <tr>
                <td colSpan={8} className="p-8 text-center text-slate-500">No rules matching selected category filter.</td>
              </tr>
            ) : (
              filteredRules.map((r) => {
                const isValid = r.validation_status === 'VALID';
                const cond = r.ir_json.conditions?.[0];
                const act = r.ir_json.actions?.[0];

                return (
                  <tr key={r.id} className="hover:bg-slate-50 transition-colors">
                    <td className="p-4 font-mono font-bold text-indigo-600">{r.rule_code}</td>
                    <td className="p-4 font-semibold text-slate-900">{r.title}</td>
                    <td className="p-4">
                      <span className="px-2.5 py-1 rounded-md bg-slate-100 text-slate-700 font-mono text-[10px] capitalize border border-slate-200">
                        {r.rule_type.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="p-4 font-mono text-[11px] text-slate-600">
                      {cond ? `${cond.variable} ${cond.operator} ${cond.value}` : 'Active'}
                    </td>
                    <td className="p-4 font-mono text-[11px] text-emerald-600 font-bold">
                      {act ? `${act.type} ${act.rate ? (act.rate * 100) + '%' : '$' + (act.amount || 0)}` : 'Execute'}
                    </td>
                    <td className="p-4">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full font-mono text-[10px] font-bold ${
                        isValid ? 'bg-emerald-100 text-emerald-700 border border-emerald-200' : 'bg-amber-100 text-amber-700 border border-amber-200'
                      }`}>
                        {isValid ? <ShieldCheck className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                        {r.validation_status}
                      </span>
                    </td>
                    <td className="p-4 font-mono text-[11px] text-slate-500">
                      Sec {r.source.section} (Pg {r.source.page})
                    </td>
                    <td className="p-4 text-right">
                      <button
                        onClick={() => setSelectedRuleModal(r)}
                        className="px-3 py-1 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 font-semibold transition-all"
                      >
                        Inspect IR
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <RuleEditorModal
        rule={selectedRuleModal}
        onClose={() => setSelectedRuleModal(null)}
        onValidate={async (ruleId) => {
          await validateRule(ruleId);
          loadRules();
        }}
      />
    </div>
  );
};
