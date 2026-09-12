import React, { useState, useEffect } from 'react';
import { X, Code2, ShieldCheck, AlertTriangle } from 'lucide-react';
import { RuleSummary } from '../types';

interface RuleEditorModalProps {
  rule: RuleSummary | null;
  onClose: () => void;
  onValidate: (ruleId: string) => void;
}

export const RuleEditorModal: React.FC<RuleEditorModalProps> = ({ rule, onClose, onValidate }) => {
  // Fix 2: useState must be called before any early return (Rules of Hooks).
  // Initialise to '' and sync via useEffect whenever rule changes.
  const [jsonContent, setJsonContent] = useState('');

  useEffect(() => {
    if (rule) {
      setJsonContent(JSON.stringify(rule.ir_json, null, 2));
    }
  }, [rule]);

  if (!rule) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white border border-slate-200 w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="p-6 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-50 border border-purple-200 flex items-center justify-center text-purple-600">
              <Code2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Legal IR Rule Definition ({rule.rule_code})</h3>
              <p className="text-xs text-slate-500 font-medium">Structured Machine-Readable Specification</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg bg-slate-100 text-slate-500 hover:text-slate-900">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-700">Rule Type: <span className="text-indigo-600 uppercase font-mono font-bold">{rule.rule_type}</span></span>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
              rule.validation_status === 'VALID' ? 'bg-emerald-100 text-emerald-700 border border-emerald-200' : 'bg-amber-100 text-amber-700 border border-amber-200'
            }`}>
              {rule.validation_status}
            </span>
          </div>

          <textarea
            value={jsonContent}
            onChange={(e) => setJsonContent(e.target.value)}
            rows={14}
            className="w-full bg-slate-900 border border-slate-700 rounded-xl p-4 text-xs font-mono text-emerald-400 focus:outline-none focus:border-indigo-500 leading-relaxed shadow-inner"
          />

          {rule.review_notes && (
            <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-600" />
              <span>{rule.review_notes}</span>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <button
            onClick={() => onValidate(rule.id)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-xs font-semibold text-white shadow-md shadow-indigo-600/20"
          >
            <ShieldCheck className="w-4 h-4" />
            Re-Validate Schema
          </button>
          <button onClick={onClose} className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-xs font-semibold text-slate-700 border border-slate-300">
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
