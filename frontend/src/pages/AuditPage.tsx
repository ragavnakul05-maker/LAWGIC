import React, { useEffect, useState } from 'react';
import { ShieldCheck, FileText, Cpu, Calculator, ArrowRight, Eye, Sparkles, Filter, CheckCircle2, BookOpen } from 'lucide-react';
import { fetchAuditExecutionTrail, fetchAuditLogs, fetchContracts } from '../services/api';
import { EvidenceModal } from '../components/EvidenceModal';
import { Clause } from '../types';

export const AuditPage: React.FC = () => {
  const [contracts, setContracts] = useState<any[]>([]);
  const [selectedContractId, setSelectedContractId] = useState<string>('');
  const [logs, setLogs] = useState<any[]>([]);
  const [selectedExecution, setSelectedExecution] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedClauseForEvidence, setSelectedClauseForEvidence] = useState<Clause | null>(null);

  useEffect(() => {
    fetchContracts()
      .then(data => {
        setContracts(data);
      })
      .catch(console.error);

    loadLogs();
  }, []);

  const loadLogs = (contractId?: string) => {
    setLoading(true);
    fetchAuditLogs(contractId || undefined)
      .then((data) => {
        setLogs(data);
        setLoading(false);
        // Auto-select first execution if available
        const firstWithExec = data.find(l => l.details?.execution_id);
        if (firstWithExec?.details?.execution_id) {
          loadExecutionTrail(firstWithExec.details.execution_id);
        }
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  };

  const handleContractFilterChange = (cId: string) => {
    setSelectedContractId(cId);
    loadLogs(cId || undefined);
    setSelectedExecution(null);
  };

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
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <ShieldCheck className="w-6 h-6 text-indigo-600" />
            Audit & Provenance Traceability Hub
          </h2>
          <p className="text-xs text-slate-500 font-medium mt-0.5">
            Transparent step-by-step audit trail linking calculated financial outcomes back to original contract clauses and plain English decompilation.
          </p>
        </div>

        {/* Contract Filter Selector */}
        <div className="glass-panel p-3 rounded-2xl flex items-center gap-3 border border-indigo-100 bg-white shadow-xs">
          <Filter className="w-4 h-4 text-indigo-600" />
          <label className="text-xs font-bold text-slate-700 whitespace-nowrap">Filter Contract:</label>
          <select
            value={selectedContractId}
            onChange={e => handleContractFilterChange(e.target.value)}
            className="border border-slate-200 rounded-xl px-3 py-1.5 text-xs font-semibold bg-slate-50 text-slate-900 focus:bg-white focus:outline-none focus:border-indigo-500 min-w-[220px]"
          >
            <option value="">All Contracts</option>
            {contracts.map((c: any) => (
              <option key={c.id} value={c.id}>{c.title} ({c.id})</option>
            ))}
          </select>
        </div>
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
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">System Audit Events ({logs.length})</h3>
            <span className="text-[10px] font-mono text-slate-400">Click to Inspect</span>
          </div>

          {loading ? (
            <div className="text-xs text-slate-500 text-center py-6">Loading audit logs...</div>
          ) : logs.length === 0 ? (
            <div className="text-xs text-slate-400 text-center py-6">No execution audit events found.</div>
          ) : (
            <div className="space-y-3 max-h-[650px] overflow-y-auto pr-1">
              {logs.map((l) => {
                const isSelected = selectedExecution?.execution_id === l.details?.execution_id;
                return (
                  <div
                    key={l.id}
                    onClick={() => {
                      if (l.details?.execution_id) {
                        loadExecutionTrail(l.details.execution_id);
                      }
                    }}
                    className={`p-3.5 rounded-xl border transition-all space-y-1 cursor-pointer shadow-xs ${
                      isSelected
                        ? 'bg-indigo-50/80 border-indigo-500 ring-1 ring-indigo-500/20'
                        : 'bg-white border-slate-200 hover:border-indigo-300'
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className={`font-bold uppercase tracking-wider text-[11px] ${
                        l.action.includes('SIMULATION') ? 'text-purple-600' : 'text-indigo-600'
                      }`}>{l.action.replace(/_/g, ' ')}</span>
                      <span className="font-mono text-[10px] text-slate-400">{new Date(l.created_at).toLocaleTimeString()}</span>
                    </div>
                    <p className="text-xs text-slate-800 font-semibold truncate">
                      {l.contract_title}
                    </p>
                    {l.details?.execution_id && (
                      <span className="inline-block text-[10px] font-mono text-emerald-600 font-bold mt-1">
                        Exec ID: {l.details.execution_id} →
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right 2 Cols: Execution Step Breakdown & Plain English Summary */}
        <div className="lg:col-span-2 space-y-6">
          {selectedExecution ? (
            <div className="glass-panel p-6 rounded-2xl border border-emerald-200 space-y-6">
              <div className="flex items-center justify-between border-b border-slate-200 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-indigo-100 text-indigo-700 font-mono text-[11px] font-bold">
                      {selectedExecution.scenario_name || 'Rule Execution'}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-slate-900 mt-1">Execution Trail: {selectedExecution.execution_id}</h3>
                  <p className="text-xs text-slate-500 font-mono">Contract: {selectedExecution.contract_title}</p>
                </div>
                <div className="text-right">
                  <span className="text-[10px] text-slate-500 font-bold uppercase block">Net Impact</span>
                  <span className={`text-xl font-extrabold font-mono ${selectedExecution.financial_impact > 0 ? 'text-rose-600' : selectedExecution.financial_impact < 0 ? 'text-emerald-600' : 'text-slate-800'}`}>
                    ${selectedExecution.financial_impact.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </div>

              {/* Execution Steps */}
              <div className="space-y-4">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center justify-between">
                  <span>Step-by-Step Calculation & Evidence Trace ({selectedExecution.steps.length} Steps)</span>
                  <span className="text-[11px] font-mono text-indigo-600">Deterministic Engine</span>
                </h4>

                {selectedExecution.steps.map((s: any) => (
                  <div key={s.step_number} className="p-4 rounded-xl bg-white border border-slate-200 space-y-2.5 text-xs shadow-xs">
                    <div className="flex items-center justify-between font-mono">
                      <span className="font-bold text-slate-900">Step {s.step_number}: [{s.rule_code}] {s.rule_title}</span>
                      <span className={`font-bold font-mono text-sm ${s.subtotal > 0 ? 'text-rose-600' : s.subtotal < 0 ? 'text-emerald-600' : 'text-slate-700'}`}>
                        ${s.subtotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </span>
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
                                human_explanation: s.decompiled_text || s.human_explanation || s.description
                              }
                            });
                          }}
                          className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-semibold bg-indigo-50 border border-indigo-100 px-2 py-1 rounded-lg transition-colors"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          View Source Clause Evidence
                        </button>
                      </div>
                    )}

                    {/* Individual Step Plain English Decompilation */}
                    {(s.decompiled_text || s.human_explanation) && (
                      <div className="mt-2 p-3 rounded-xl bg-indigo-50/80 border border-indigo-100 text-indigo-900 space-y-1">
                        <p className="text-[11px] font-bold text-indigo-700 flex items-center gap-1.5">
                          <BookOpen className="w-3.5 h-3.5 text-indigo-600" />
                          Plain English Decompiled Logic
                        </p>
                        <p className="text-xs text-indigo-950 font-medium leading-relaxed">
                          {s.decompiled_text || s.human_explanation}
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Complete Contract Backtracking & Plain English Legal Summary Box */}
              <div className="p-5 rounded-2xl bg-gradient-to-br from-indigo-900 via-slate-900 to-slate-950 text-white space-y-3.5 shadow-xl border border-indigo-700/50">
                <div className="flex items-center justify-between border-b border-indigo-800/80 pb-3">
                  <div className="flex items-center gap-2">
                    <BookOpen className="w-5 h-5 text-indigo-400" />
                    <h4 className="text-sm font-bold tracking-wide">Complete Backtracking & Plain English Summary</h4>
                  </div>
                  <span className="text-[10px] font-mono font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 px-2 py-0.5 rounded-full">
                    Deterministic Provenance
                  </span>
                </div>

                <div className="space-y-3 text-xs leading-relaxed text-indigo-100">
                  <p>
                    <strong className="text-white">Contract:</strong> {selectedExecution.contract_title} ({selectedExecution.contract_id})
                  </p>

                  <p>
                    <strong className="text-white">Input Operational Variables:</strong>{' '}
                    <span className="font-mono text-cyan-300">
                      {Object.entries(selectedExecution.input_variables || {}).map(([k, v]) => `${k.replace(/_/g, ' ')} = ${v}`).join(' | ')}
                    </span>
                  </p>

                  <div className="space-y-2 pt-1">
                    <p className="font-bold text-white uppercase text-[11px] tracking-wider">Triggered Legal Logic (Plain English):</p>
                    {selectedExecution.steps.map((s: any) => (
                      <div key={s.step_number} className="p-2.5 rounded-lg bg-indigo-950/80 border border-indigo-800/50 text-[11px]">
                        <span className="font-mono font-bold text-cyan-400">Step {s.step_number} [{s.rule_code}]: </span>
                        <span>{s.decompiled_text || s.description}</span>
                        {s.source_clause && (
                          <span className="text-indigo-300 font-mono text-[10px] block mt-1">
                            ↳ Backtracked to Clause Section {s.source_clause.section} (Page {s.source_clause.page})
                          </span>
                        )}
                      </div>
                    ))}
                  </div>

                  <div className="pt-2 border-t border-indigo-800/60 flex items-center justify-between font-mono">
                    <span className="font-bold text-white text-xs">Final Net Financial Impact:</span>
                    <span className={`text-base font-extrabold ${selectedExecution.financial_impact > 0 ? 'text-rose-400' : selectedExecution.financial_impact < 0 ? 'text-emerald-400' : 'text-white'}`}>
                      ${selectedExecution.financial_impact.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="glass-panel p-12 rounded-2xl border border-slate-200 text-center space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mx-auto text-indigo-600">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-slate-900">Select an Audit Event to Inspect Execution Trail</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
                Click on any execution event on the left log list to inspect the complete 100% reproducible step-by-step mathematical trace, contract evidence clause, and plain English decompilation summary.
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

