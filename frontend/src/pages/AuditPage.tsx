import React, { useEffect, useState } from 'react';
import { ShieldCheck, FileText, Cpu, Calculator, ArrowRight, Eye, Sparkles } from 'lucide-react';
import { fetchAuditExecutionTrail, fetchAuditLogs } from '../services/api';
import { EvidenceModal } from '../components/EvidenceModal';
import { Clause } from '../types';

export const AuditPage: React.FC = () => {
  const [logs, setLogs] = useState<any[]>([]);
  const [selectedExecution, setSelectedExecution] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedClauseForEvidence, setSelectedClauseForEvidence] = useState<Clause | null>(null);

  useEffect(() => {
    fetchAuditLogs()
      .then((data) => {
        setLogs(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  const loadExecutionTrail = (execId: string) => {
    fetchAuditExecutionTrail(execId)
      .then((data) => {
        setSelectedExecution(data);
      })
      .catch((err) => alert(`Error loading audit trail: ${err}`));
  };

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Page Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <ShieldCheck className="w-6 h-6 text-indigo-600" />
          Audit & Provenance Traceability Hub
        </h2>
        <p className="text-xs text-slate-500 font-medium mt-0.5">
          Transparent step-by-step audit trail linking calculated financial outcomes back to original contract clauses.
        </p>
      </div>

      {/* Audit Pipeline Diagram */}
      <div className="glass-panel p-5 rounded-2xl border border-slate-200 flex items-center justify-between font-mono text-xs shadow-xs">
        <div className="flex items-center gap-2 text-indigo-700 font-bold">
          <FileText className="w-4 h-4 text-indigo-600" /> Contract Source
        </div>
        <ArrowRight className="w-4 h-4 text-slate-400" />
        <div className="flex items-center gap-2 text-cyan-700 font-bold">
          <Cpu className="w-4 h-4 text-cyan-600" /> Clause Segment
        </div>
        <ArrowRight className="w-4 h-4 text-slate-400" />
        <div className="flex items-center gap-2 text-purple-700 font-bold">
          <ShieldCheck className="w-4 h-4 text-purple-600" /> Legal IR Rule
        </div>
        <ArrowRight className="w-4 h-4 text-slate-400" />
        <div className="flex items-center gap-2 text-amber-700 font-bold">
          <Calculator className="w-4 h-4 text-amber-600" /> Deterministic Execution
        </div>
        <ArrowRight className="w-4 h-4 text-slate-400" />
        <div className="flex items-center gap-2 text-emerald-700 font-bold">
          <Sparkles className="w-4 h-4 text-emerald-600" /> Financial Result
        </div>
      </div>

      {/* Content Split */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Col: Audit Logs List */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-200 space-y-4">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">System Audit Events</h3>

          {loading ? (
            <div className="text-xs text-slate-500 text-center py-4">Loading audit logs...</div>
          ) : (
            <div className="space-y-3">
              {logs.map((l) => (
                <div
                  key={l.id}
                  onClick={() => {
                    if (l.details?.execution_id) {
                      loadExecutionTrail(l.details.execution_id);
                    }
                  }}
                  className="p-3.5 rounded-xl bg-white border border-slate-200 hover:border-indigo-400 cursor-pointer shadow-xs transition-all space-y-1"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-indigo-600">{l.action}</span>
                    <span className="font-mono text-[10px] text-slate-400">{new Date(l.created_at).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-xs text-slate-700 font-mono text-[11px] truncate font-semibold">
                    {l.contract_title}
                  </p>
                  {l.details?.execution_id && (
                    <span className="inline-block text-[10px] font-mono text-emerald-600 font-bold">
                      Exec ID: {l.details.execution_id} →
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right 2 Cols: Execution Step Breakdown & Evidence */}
        <div className="lg:col-span-2 space-y-6">
          {selectedExecution ? (
            <div className="glass-panel p-6 rounded-2xl border border-emerald-200 space-y-6">
              <div className="flex items-center justify-between border-b border-slate-200 pb-4">
                <div>
                  <h3 className="text-base font-bold text-slate-900">Execution Trail: {selectedExecution.execution_id}</h3>
                  <p className="text-xs text-slate-500 font-mono">Contract: {selectedExecution.contract_title}</p>
                </div>
                <div className="text-right">
                  <span className="text-[10px] text-slate-500 font-bold uppercase block">Net Impact</span>
                  <span className="text-xl font-extrabold font-mono text-emerald-600">
                    ${selectedExecution.financial_impact.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </div>

              {/* Execution Steps */}
              <div className="space-y-4">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Step-by-Step Calculation & Evidence Trace</h4>

                {selectedExecution.steps.map((s: any) => (
                  <div key={s.step_number} className="p-4 rounded-xl bg-white border border-slate-200 space-y-2 text-xs shadow-xs">
                    <div className="flex items-center justify-between font-mono">
                      <span className="font-bold text-slate-900">Step {s.step_number}: [{s.rule_code}] {s.rule_title}</span>
                      <span className="font-bold text-rose-600">${s.subtotal.toLocaleString()}</span>
                    </div>

                    <p className="text-slate-700 leading-relaxed text-xs">{s.description}</p>

                    {s.source_clause && (
                      <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                        <span className="text-[11px] text-slate-500 font-mono">
                          Source: Section {s.source_clause.section} (Page {s.source_clause.page})
                        </span>

                        <button
                          onClick={() => {
                            setSelectedClauseForEvidence({
                              id: s.source_clause.id || 'C001',
                              page_number: s.source_clause.page,
                              section_number: s.source_clause.section,
                              title: s.source_clause.title,
                              original_text: s.source_clause.original_text,
                              clause_type: 'late_payment_interest',
                              rule: {
                                id: 'R001',
                                rule_code: s.rule_code,
                                title: s.rule_title,
                                ir_json: s.rule_ir,
                                validation_status: 'VALID',
                                human_explanation: s.description
                              }
                            });
                          }}
                          className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-semibold"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          View Source Clause
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="glass-panel p-12 rounded-2xl border border-slate-200 text-center space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mx-auto text-indigo-600">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-slate-900">Select an Audit Event to Inspect Execution Trail</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
                Click on any execution event on the left log list to inspect the complete 100% reproducible step-by-step mathematical trace and contract evidence clause.
              </p>
            </div>
          )}
        </div>
      </div>

      <EvidenceModal
        clause={selectedClauseForEvidence}
        onClose={() => setSelectedClauseForEvidence(null)}
      />
    </div>
  );
};
