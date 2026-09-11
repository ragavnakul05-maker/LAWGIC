import React from 'react';
import { Clause } from '../types';
import { FileText, ShieldCheck, AlertTriangle, Play, Eye, Sliders } from 'lucide-react';

interface ClauseCardProps {
  clause: Clause;
  onViewRule: (clause: Clause) => void;
  onValidate: (ruleId: string) => void;
  onSimulate: (clause: Clause) => void;
  onShowEvidence: (clause: Clause) => void;
}

export const ClauseCard: React.FC<ClauseCardProps> = ({
  clause,
  onViewRule,
  onValidate,
  onSimulate,
  onShowEvidence
}) => {
  const rule = clause.rule;
  const isValid = rule?.validation_status === 'VALID';
  const isReview = rule?.validation_status === 'NEEDS_REVIEW';

  return (
    <div className="glass-panel glass-panel-hover p-5 rounded-2xl border border-slate-200 space-y-4">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-md bg-indigo-50 border border-indigo-200 text-indigo-700 font-mono text-xs font-bold">
            Section {clause.section_number}
          </span>
          <span className="text-xs text-slate-500 font-medium">Page {clause.page_number}</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 capitalize font-medium">
            {clause.clause_type.replace(/_/g, ' ')}
          </span>
        </div>

        {/* Validation Status Badge */}
        {rule && (
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
            isValid
              ? 'bg-emerald-100 text-emerald-700 border border-emerald-200'
              : 'bg-amber-100 text-amber-700 border border-amber-200'
          }`}>
            {isValid ? <ShieldCheck className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
            {rule.validation_status}
          </span>
        )}
      </div>

      {/* Clause Text */}
      <div>
        <h4 className="text-sm font-semibold text-slate-900 mb-1">{clause.title}</h4>
        <p className="text-xs text-slate-700 leading-relaxed bg-slate-50/90 p-3 rounded-xl border border-slate-200 font-serif italic">
          "{clause.original_text}"
        </p>
      </div>

      {/* Legal IR Structured Conditions & Actions Preview */}
      {rule?.ir_json && (
        <div className="p-3 rounded-xl bg-slate-900 text-slate-100 border border-slate-800 space-y-2 text-xs">
          <div className="flex items-center justify-between text-slate-400 font-mono text-[11px]">
            <span>Structured Legal IR ({rule.rule_code})</span>
            <span className="text-cyan-400 font-bold">Deterministic Logic</span>
          </div>

          <div className="grid grid-cols-2 gap-2 pt-1">
            <div className="bg-slate-800/90 p-2 rounded-lg border border-slate-700">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-0.5">Condition</span>
              <span className="font-mono text-slate-200 text-[11px]">
                {rule.ir_json.conditions?.[0]
                  ? `${rule.ir_json.conditions[0].variable} ${rule.ir_json.conditions[0].operator} ${rule.ir_json.conditions[0].value}`
                  : 'IF baseline active'}
              </span>
            </div>

            <div className="bg-slate-800/90 p-2 rounded-lg border border-slate-700">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-0.5">Action & Cap</span>
              <span className="font-mono text-emerald-400 text-[11px]">
                {rule.ir_json.actions?.[0]
                  ? `${rule.ir_json.actions[0].type} ${rule.ir_json.actions[0].rate ? (rule.ir_json.actions[0].rate * 100) + '%' : '$' + rule.ir_json.actions[0].amount}`
                  : 'Execute Rule'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-200">
        <button
          onClick={() => onShowEvidence(clause)}
          className="flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-800 font-semibold transition-colors"
        >
          <Eye className="w-3.5 h-3.5" />
          Show Evidence
        </button>

        <div className="flex items-center gap-2">
          {rule && (
            <button
              onClick={() => onValidate(rule.id)}
              className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-xs font-semibold text-slate-700 transition-colors border border-slate-300"
            >
              Validate
            </button>
          )}

          <button
            onClick={() => onViewRule(clause)}
            className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-xs font-semibold text-slate-700 transition-colors border border-slate-300"
          >
            View IR
          </button>

          <button
            onClick={() => onSimulate(clause)}
            className="flex items-center gap-1 px-3 py-1 rounded-lg bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-xs font-semibold text-white shadow-md shadow-indigo-600/20 transition-all"
          >
            <Sliders className="w-3.5 h-3.5" />
            Simulate
          </button>
        </div>
      </div>
    </div>
  );
};
