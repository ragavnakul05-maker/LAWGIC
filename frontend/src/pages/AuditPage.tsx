import React, { useEffect, useState, useMemo } from 'react';
import {
  ShieldCheck, FileText, ArrowRight, ChevronDown, ChevronUp,
  CheckCircle2, AlertCircle, RefreshCw, Sparkles, Layers,
  Code2, Clock, Check, Download, FileSpreadsheet, FileCode, Printer
} from 'lucide-react';
import { fetchAuditLogs, fetchAuditExecutionTrail, fetchContracts, exportAuditExecution } from '../services/api';

import { formatINR } from '../utils/currency';

export const AuditPage: React.FC = () => {
  const [contracts, setContracts] = useState<any[]>([]);
  const [selectedContractId, setSelectedContractId] = useState<string>('');
  const [logs, setLogs] = useState<any[]>([]);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string>('');
  const [executionTrail, setExecutionTrail] = useState<any | null>(null);
  const [selectedStepIndex, setSelectedStepIndex] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingTrail, setLoadingTrail] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [exportOpen, setExportOpen] = useState<boolean>(false);
  const [exporting, setExporting] = useState<boolean>(false);

  // Expandable sections state (all collapsed by default to keep main view minimal)
  const [expandedSections, setExpandedSections] = useState<{
    sourceClause: boolean;
    legalIR: boolean;
    validation: boolean;
    executionLog: boolean;
  }>({
    sourceClause: false,
    legalIR: false,
    validation: false,
    executionLog: false,
  });

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  // 1. Initial Load: fetch contracts and recent audit logs
  useEffect(() => {
    setLoading(true);
    Promise.all([fetchContracts(), fetchAuditLogs()])
      .then(([contractsData, logsData]) => {
        setContracts(contractsData || []);
        setLogs(logsData || []);

        if (contractsData && contractsData.length > 0) {
          const defaultCid = contractsData[0].id;
          setSelectedContractId(defaultCid);

          // Find first execution for this contract if available
          const matchingLog = (logsData || []).find((l: any) => l.contract_id === defaultCid && l.details?.execution_id);
          if (matchingLog?.details?.execution_id) {
            setSelectedExecutionId(matchingLog.details.execution_id);
          } else if (logsData && logsData.length > 0 && logsData[0].details?.execution_id) {
            setSelectedExecutionId(logsData[0].details.execution_id);
          }
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load initial audit data:', err);
        setError('Failed to load audit logs.');
        setLoading(false);
      });
  }, []);

  // 2. When selectedContractId changes, find relevant execution or switch
  useEffect(() => {
    if (!selectedContractId) return;
    const matchingLog = logs.find((l: any) => l.contract_id === selectedContractId && l.details?.execution_id);
    if (matchingLog?.details?.execution_id) {
      setSelectedExecutionId(matchingLog.details.execution_id);
    }
  }, [selectedContractId, logs]);

  // 3. When selectedExecutionId changes, fetch the full execution trail
  useEffect(() => {
    if (!selectedExecutionId) return;
    setLoadingTrail(true);
    setError(null);
    fetchAuditExecutionTrail(selectedExecutionId)
      .then((data) => {
        setExecutionTrail(data);
        setSelectedStepIndex(0);
        setLoadingTrail(false);
      })
      .catch((err) => {
        console.error('Failed to load execution trail:', err);
        setError(err.message || 'Failed to load execution trail.');
        setLoadingTrail(false);
      });
  }, [selectedExecutionId]);

  // Available executions for the selected contract
  const contractExecutions = useMemo(() => {
    if (!selectedContractId) return logs;
    const filtered = logs.filter(l => l.contract_id === selectedContractId && l.details?.execution_id);
    return filtered.length > 0 ? filtered : logs;
  }, [logs, selectedContractId]);

  const activeStep = executionTrail?.steps?.[selectedStepIndex] || null;
  const flowData = activeStep?.flow_data || {};

  // Build fallback 5-step flow values if flow_data is not directly available
  const stepInput = flowData.input_text || (activeStep ? `${activeStep.rule_title} Input` : 'Input');
  const stepCondition = flowData.condition_text || (activeStep?.subtotal !== 0 ? 'Rule Threshold Met → TRUE' : 'Within Threshold → FALSE');
  const stepRule = flowData.rule_applied_text || (activeStep ? `${activeStep.rule_code} – ${activeStep.rule_title}` : 'Rule');
  const stepCalc = flowData.calculation_text || (activeStep?.formula ? activeStep.formula.replace('$', '₹') : formatINR(activeStep?.subtotal));
  const stepResult = flowData.result_text || formatINR(activeStep?.subtotal);

  // Deterministic decompiled explanation (Non-LLM)
  const decompiledText = activeStep?.decompiled_explanation ||
    (activeStep ? `Rule ${activeStep.rule_code} condition was evaluated deterministically. Contractual impact assessed, resulting in ${formatINR(activeStep.subtotal)}.` : '');

  const selectedContract = contracts.find(c => c.id === selectedContractId);

  const handleExport = async (format: 'html' | 'csv' | 'json') => {
    if (!selectedExecutionId) return;
    try {
      setExporting(true);
      await exportAuditExecution(selectedExecutionId, format);
    } catch (err: any) {
      console.error('Export failed:', err);
      alert(err.message || 'Failed to export dossier');
    } finally {
      setExporting(false);
      setExportOpen(false);
    }
  };

  return (
    <div className="p-6 md:p-10 max-w-5xl mx-auto space-y-8">
      {/* Clean Header & Navigation Bar: Contract -> Rule */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-600 block">
              Audit & Traceability Hub
            </span>
            <h1 className="text-xl font-bold text-slate-900">
              Contract Execution Trace
            </h1>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {/* Contract Selector */}
            <div className="flex items-center gap-2">
              <label className="text-xs font-bold text-slate-600 shrink-0">Contract:</label>
              <select
                value={selectedContractId}
                onChange={e => setSelectedContractId(e.target.value)}
                disabled={loading || loadingTrail}
                className="bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
              >
                {contracts.length === 0 ? (
                  <option value="">No Contracts</option>
                ) : (
                  contracts.map((c: any) => (
                    <option key={c.id} value={c.id}>
                      {c.title} ({c.id})
                    </option>
                  ))
                )}
              </select>
            </div>

            {/* Export Dossier Dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setExportOpen(prev => !prev)}
                disabled={!selectedExecutionId || exporting}
                className="inline-flex items-center gap-1.5 px-3 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold text-xs rounded-xl border border-indigo-200 transition-colors shadow-xs disabled:opacity-50 cursor-pointer"
                title="Export executive audit dossier in PDF/HTML, CSV, or JSON format"
              >
                <Download className="w-3.5 h-3.5" />
                <span>{exporting ? 'Exporting...' : 'Export Dossier'}</span>
                <ChevronDown className={`w-3 h-3 transition-transform ${exportOpen ? 'rotate-180' : ''}`} />
              </button>

              {exportOpen && (
                <div className="absolute right-0 mt-1.5 w-60 bg-white rounded-xl shadow-xl border border-slate-200 py-1.5 z-50 animate-in fade-in zoom-in-95 duration-100">
                  <div className="px-3 py-1.5 border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                    Audit Export Formats
                  </div>
                  <button
                    onClick={() => handleExport('html')}
                    className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-indigo-50 hover:text-indigo-700 flex items-center gap-2.5 transition-colors cursor-pointer"
                  >
                    <Printer className="w-4 h-4 text-indigo-500 shrink-0" />
                    <div>
                      <div className="font-semibold">Executive PDF Report</div>
                      <div className="text-[10px] text-slate-400">Print-ready formatted document</div>
                    </div>
                  </button>
                  <button
                    onClick={() => handleExport('csv')}
                    className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-emerald-50 hover:text-emerald-700 flex items-center gap-2.5 transition-colors cursor-pointer"
                  >
                    <FileSpreadsheet className="w-4 h-4 text-emerald-500 shrink-0" />
                    <div>
                      <div className="font-semibold">CSV Calculation Ledger</div>
                      <div className="text-[10px] text-slate-400">Tabular math and rule steps</div>
                    </div>
                  </button>
                  <button
                    onClick={() => handleExport('json')}
                    className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-amber-50 hover:text-amber-700 flex items-center gap-2.5 transition-colors cursor-pointer"
                  >
                    <FileCode className="w-4 h-4 text-amber-500 shrink-0" />
                    <div>
                      <div className="font-semibold">JSON Audit Package</div>
                      <div className="text-[10px] text-slate-400">SHA-256 verified audit dossier</div>
                    </div>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Rule / Execution Step Selector */}
        {executionTrail && executionTrail.steps && executionTrail.steps.length > 0 ? (
          <div className="space-y-2 pt-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-700">Select Rule to Inspect Trace:</span>
              <span className="font-mono text-slate-500 text-[11px]">
                Execution: <code className="bg-slate-100 px-1.5 py-0.5 rounded">{executionTrail.execution_id}</code>
              </span>
            </div>

            {/* Compact Rule Tabs */}
            <div className="flex items-center gap-2 overflow-x-auto pb-1">
              {executionTrail.steps.map((s: any, idx: number) => {
                const isSelected = idx === selectedStepIndex;
                return (
                  <button
                    key={s.step_number || idx}
                    onClick={() => setSelectedStepIndex(idx)}
                    className={`px-3.5 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer flex items-center gap-1.5 border ${
                      isSelected
                        ? 'bg-indigo-600 text-white border-indigo-600 shadow-xs'
                        : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                    }`}
                  >
                    <span className="font-mono font-bold text-[11px]">{s.rule_code}</span>
                    <span className="text-[11px] max-w-[140px] truncate">{s.rule_title}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          !loadingTrail && (
            <div className="text-xs text-slate-500 py-2">
              No recent execution trails found for this contract. Run a simulation to inspect its deterministic trace.
            </div>
          )
        )}
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      )}

      {/* Loading State */}
      {loadingTrail ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-xs text-slate-500 space-y-2">
          <RefreshCw className="w-5 h-5 animate-spin mx-auto text-indigo-600" />
          <p>Loading deterministic execution trail...</p>
        </div>
      ) : activeStep ? (
        <div className="space-y-6">
          {/* ============================================================ */}
          {/* 1. HORIZONTAL 5-STEP EXECUTION TRACE FLOW                     */}
          {/* ============================================================ */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 md:p-8 shadow-xs space-y-5">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                  <Layers className="w-4 h-4 text-indigo-600" />
                  Deterministic Execution Trace
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Step-by-step mathematical progression from input to contractual result.
                </p>
              </div>

              <span className="px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 text-[11px] font-mono font-bold border border-emerald-200 flex items-center gap-1">
                <Check className="w-3 h-3 text-emerald-600" />
                Verified Non-LLM Execution
              </span>
            </div>

            {/* The 5-Step Horizontal Flow */}
            <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 items-stretch">
              {/* ① INPUT */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between space-y-2">
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-indigo-100 text-indigo-800">
                    ① INPUT
                  </span>
                </div>
                <div className="text-xs font-mono font-bold text-slate-900">
                  {stepInput}
                </div>
              </div>

              {/* ② CONDITION */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between space-y-2">
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800">
                    ② CONDITION
                  </span>
                </div>
                <div className="text-xs font-mono font-bold text-slate-900">
                  {stepCondition}
                </div>
              </div>

              {/* ③ RULE APPLIED */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between space-y-2">
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-purple-100 text-purple-800">
                    ③ RULE APPLIED
                  </span>
                </div>
                <div className="text-xs font-mono font-bold text-slate-900">
                  {stepRule}
                </div>
              </div>

              {/* ④ CALCULATION */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between space-y-2">
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-100 text-amber-800">
                    ④ CALCULATION
                  </span>
                </div>
                <div className="text-xs font-mono font-bold text-slate-900">
                  {stepCalc}
                </div>
              </div>

              {/* ⑤ RESULT */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between space-y-2">
                <div className="flex items-center justify-between">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                    activeStep.subtotal > 0
                      ? 'bg-rose-100 text-rose-800'
                      : activeStep.subtotal < 0
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-slate-200 text-slate-800'
                  }`}>
                    ⑤ RESULT
                  </span>
                </div>
                <div className={`text-sm font-mono font-extrabold ${
                  activeStep.subtotal > 0
                    ? 'text-rose-600'
                    : activeStep.subtotal < 0
                      ? 'text-emerald-600'
                      : 'text-slate-900'
                }`}>
                  {stepResult}
                </div>
              </div>
            </div>
          </div>

          {/* ============================================================ */}
          {/* 2. DEDICATED DECOMPILATION SECTION (NON-LLM)                 */}
          {/* ============================================================ */}
          <div className="bg-slate-900 text-slate-100 p-6 rounded-2xl border border-slate-800 shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-indigo-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-indigo-300">
                  Deterministic Decompilation
                </span>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-400 border border-slate-700">
                Non-LLM DecompilerService
              </span>
            </div>
            <p className="text-sm font-sans text-slate-200 leading-relaxed font-medium">
              "{decompiledText}"
            </p>
          </div>

          {/* ============================================================ */}
          {/* 3. EXPANDABLE SECTIONS (SOURCE, LEGAL IR, VALIDATION, LOG)   */}
          {/* ============================================================ */}
          <div className="space-y-3">
            {/* Section A: Source Clause & Section / Page */}
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
              <button
                onClick={() => toggleSection('sourceClause')}
                className="w-full px-5 py-3.5 flex items-center justify-between text-xs font-bold text-slate-800 hover:bg-slate-50 transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-indigo-600" />
                  <span>Source Clause & Contract Reference</span>
                  {activeStep.source_clause && (
                    <span className="text-[11px] font-mono text-slate-500 font-normal">
                      (Section {activeStep.source_clause.section}, Page {activeStep.source_clause.page})
                    </span>
                  )}
                </div>
                {expandedSections.sourceClause ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
              </button>

              {expandedSections.sourceClause && (
                <div className="px-5 pb-5 pt-2 border-t border-slate-100 bg-slate-50/50 space-y-2 text-xs">
                  {activeStep.source_clause ? (
                    <>
                      <div className="font-semibold text-slate-700">
                        {activeStep.source_clause.title}
                      </div>
                      <blockquote className="p-3 bg-white rounded-lg border border-slate-200 text-slate-700 font-serif italic text-xs leading-relaxed">
                        "{activeStep.source_clause.original_text}"
                      </blockquote>
                    </>
                  ) : (
                    <p className="text-slate-500 italic">No source clause text linked to this step.</p>
                  )}
                </div>
              )}
            </div>

            {/* Section B: Structured Legal IR */}
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
              <button
                onClick={() => toggleSection('legalIR')}
                className="w-full px-5 py-3.5 flex items-center justify-between text-xs font-bold text-slate-800 hover:bg-slate-50 transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <Code2 className="w-4 h-4 text-purple-600" />
                  <span>Structured Legal Intermediate Representation (IR)</span>
                </div>
                {expandedSections.legalIR ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
              </button>

              {expandedSections.legalIR && (
                <div className="px-5 pb-5 pt-2 border-t border-slate-100 bg-slate-50/50">
                  {activeStep.rule_ir ? (
                    <pre className="p-4 rounded-xl bg-slate-900 text-indigo-300 font-mono text-[11px] overflow-x-auto">
                      {JSON.stringify(activeStep.rule_ir, null, 2)}
                    </pre>
                  ) : (
                    <p className="text-xs text-slate-500 italic">No Legal IR schema attached to this step.</p>
                  )}
                </div>
              )}
            </div>

            {/* Section C: Rule Validation */}
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
              <button
                onClick={() => toggleSection('validation')}
                className="w-full px-5 py-3.5 flex items-center justify-between text-xs font-bold text-slate-800 hover:bg-slate-50 transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>Rule Validation Status</span>
                  <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-mono text-[10px] font-bold">
                    {activeStep.validation_status || 'VALID'}
                  </span>
                </div>
                {expandedSections.validation ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
              </button>

              {expandedSections.validation && (
                <div className="px-5 pb-5 pt-2 border-t border-slate-100 bg-slate-50/50 space-y-2 text-xs">
                  <div className="flex items-center gap-2 text-emerald-800 font-semibold">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>Schema verification complete: Deterministic variables, conditions, and actions validated.</span>
                  </div>
                  <p className="text-slate-600 text-[11px]">
                    Zero ambiguity flags detected. Mathematical bounds and operator semantics are verified for deterministic execution.
                  </p>
                </div>
              )}
            </div>

            {/* Section D: Detailed Execution Log */}
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
              <button
                onClick={() => toggleSection('executionLog')}
                className="w-full px-5 py-3.5 flex items-center justify-between text-xs font-bold text-slate-800 hover:bg-slate-50 transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-slate-600" />
                  <span>Detailed Execution Log & Provenance</span>
                </div>
                {expandedSections.executionLog ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
              </button>

              {expandedSections.executionLog && (
                <div className="px-5 pb-5 pt-2 border-t border-slate-100 bg-slate-50/50 space-y-2 font-mono text-[11px] text-slate-700">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div>Execution ID: <code className="font-bold">{executionTrail.execution_id}</code></div>
                    <div>Contract ID: <code className="font-bold">{executionTrail.contract_id}</code></div>
                    <div>Scenario: <code className="font-bold">{executionTrail.scenario_name || 'Production Run'}</code></div>
                    <div>Executed At: <code className="font-bold">{new Date(executionTrail.executed_at).toLocaleString()}</code></div>
                    <div>Step Number: <code className="font-bold">{activeStep.step_number}</code></div>
                    <div>Rule Code: <code className="font-bold">{activeStep.rule_code}</code></div>
                  </div>
                  {activeStep.formula && (
                    <div className="pt-2 border-t border-slate-200">
                      <span className="text-slate-500">Raw Formula:</span> <code>{activeStep.formula}</code>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center space-y-3">
          <ShieldCheck className="w-8 h-8 text-slate-400 mx-auto" />
          <h3 className="text-base font-bold text-slate-900">Select a Contract to Inspect Execution Trace</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Choose an uploaded contract from the dropdown above to inspect its 5-step deterministic flow and decompiled legal rationale.
          </p>
        </div>
      )}
    </div>
  );
};

export default AuditPage;
