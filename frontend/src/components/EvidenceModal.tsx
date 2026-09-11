import React from 'react';
import { X, ShieldCheck, FileText, Sparkles, Code2 } from 'lucide-react';
import { Clause } from '../types';

interface EvidenceModalProps {
  clause: Clause | null;
  onClose: () => void;
}

export const EvidenceModal: React.FC<EvidenceModalProps> = ({ clause, onClose }) => {
  if (!clause) return null;

  const rule = clause.rule;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white border border-slate-200 w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-6 border-b border-slate-200 flex items-center justify-between bg-slate-50/80">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Source Clause Audit Evidence</h3>
              <p className="text-xs text-slate-500 font-medium">Traceable Provenance Verification</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-slate-100 text-slate-500 hover:text-slate-900 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
          {/* Metadata Bar */}
          <div className="grid grid-cols-3 gap-3 p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs">
            <div>
              <span className="text-slate-500 font-semibold uppercase tracking-wider block text-[10px]">Page Number</span>
              <span className="font-mono text-slate-800 text-xs font-bold">Page {clause.page_number}</span>
            </div>
            <div>
              <span className="text-slate-500 font-semibold uppercase tracking-wider block text-[10px]">Section Number</span>
              <span className="font-mono text-indigo-600 text-xs font-bold">Section {clause.section_number}</span>
            </div>
            <div>
              <span className="text-slate-500 font-semibold uppercase tracking-wider block text-[10px]">Clause Code</span>
              <span className="font-mono text-emerald-600 text-xs font-bold">{rule?.rule_code || 'R001'}</span>
            </div>
          </div>

          {/* Original Clause Text */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-600" />
              Original Contract Clause Text
            </label>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 font-serif italic text-slate-800 text-sm leading-relaxed relative">
              <div className="absolute top-2 right-2 px-2 py-0.5 rounded bg-indigo-100 text-indigo-700 text-[10px] font-mono not-italic font-bold">
                VERIFIED SOURCE
              </div>
              "{clause.original_text}"
            </div>
          </div>

          {/* Decompiled Human Explanation */}
          {rule?.human_explanation && (
            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-emerald-600" />
                Decompiled Executable Logic
              </label>
              <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-slate-800 text-xs leading-relaxed font-mono">
                {rule.human_explanation}
              </div>
            </div>
          )}

          {/* JSON Legal IR Trace */}
          {rule?.ir_json && (
            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-2">
                <Code2 className="w-4 h-4 text-purple-600" />
                Machine-Readable Legal IR (JSON)
              </label>
              <pre className="p-4 rounded-xl bg-slate-900 text-emerald-400 font-mono text-[11px] overflow-x-auto max-h-48 shadow-inner">
                {JSON.stringify(rule.ir_json, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <span className="text-[11px] text-slate-500 font-medium">Deterministic Engine Audit Stamp • 100% Traceable</span>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-xs font-semibold text-white transition-colors shadow-sm"
          >
            Close Audit View
          </button>
        </div>
      </div>
    </div>
  );
};
