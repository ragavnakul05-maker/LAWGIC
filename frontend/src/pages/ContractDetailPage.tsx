import React, { useEffect, useState } from 'react';
import {
  FileText, ShieldCheck, Play, Sliders, Eye, Sparkles, ChevronLeft, ChevronRight, CheckCircle2, Calculator, AlertTriangle
} from 'lucide-react';
import { ClauseCard } from '../components/ClauseCard';
import { EvidenceModal } from '../components/EvidenceModal';
import { RuleEditorModal } from '../components/RuleEditorModal';
import { fetchContractDetail, validateRule, executeContractRules } from '../services/api';
import { ContractDetail, Clause, RuleExecutionOutput, RuleSummary } from '../types';

interface ContractDetailPageProps {
  contractId: string;
  onBack: () => void;
  onSimulate: (contractId: string, prefillVars?: Record<string, any>) => void;
}

export const ContractDetailPage: React.FC<ContractDetailPageProps> = ({ contractId, onBack, onSimulate }) => {
  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [activePageNum, setActivePageNum] = useState<number>(1);
  const [selectedClauseForEvidence, setSelectedClauseForEvidence] = useState<Clause | null>(null);
  const [selectedRuleForModal, setSelectedRuleForModal] = useState<RuleSummary | null>(null);
  const [executionResult, setExecutionResult] = useState<RuleExecutionOutput | null>(null);
  const [executing, setExecuting] = useState(false);
  const [showGeneralClauses, setShowGeneralClauses] = useState(false);

  // Input Variables Sandbox State
  const [variables, setVariables] = useState({
    contract_value: 1000000.0,
    invoice_amount: 1000000.0,
    payment_delay_days: 35,
    delivery_delay_days: 24,
    order_quantity: 1200,
    sla_uptime_percent: 99.1,
    inflation_rate_percent: 2.5
  });

  const loadContract = () => {
    fetchContractDetail(contractId)
      .then((data) => {
        setContract(data);
      })
      .catch((err) => console.error(err));
  };

  useEffect(() => {
    loadContract();
  }, [contractId]);

  const handleValidate = async (ruleId: string) => {
    try {
      await validateRule(ruleId);
      loadContract();
    } catch (err) {
      alert(`Validation error: ${err}`);
    }
  };

  const handleExecute = async () => {
    setExecuting(true);
    try {
      const res = await executeContractRules(contractId, variables);
      setExecutionResult(res);
      setExecuting(false);
    } catch (err) {
      alert(`Execution error: ${err}`);
      setExecuting(false);
    }
  };

  if (!contract) {
    return <div className="p-8 text-center text-slate-500">Loading contract studio details...</div>;
  }

  const activePageObj = contract.pages.find((p) => p.page_number === activePageNum) || contract.pages[0];

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col overflow-hidden">
      {/* Top Studio Control Bar */}
      <div className="p-4 border-b border-slate-200 bg-white/80 backdrop-blur-md flex items-center justify-between shrink-0 shadow-xs">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors border border-slate-300"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <div>
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              {contract.title}
              <span className="px-2 py-0.5 rounded bg-indigo-100 text-indigo-700 text-[10px] font-mono font-bold">
                {contract.id}
              </span>
            </h2>
            <p className="text-[11px] text-slate-500 font-medium">
              {contract.page_count} Pages • {contract.clauses.length} Extracted Clauses • Deterministic Rule Execution Studio
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => onSimulate(contract.id, variables)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs transition-colors shadow-md shadow-indigo-600/20"
          >
            <Sliders className="w-4 h-4" />
            Open Simulator
          </button>
        </div>
      </div>

      {/* 3-Pane Layout */}
      <div className="flex-1 grid grid-cols-12 overflow-hidden">
        {/* LEFT PANE (Col 1-3): Document Text Viewer */}
        <div className="col-span-3 border-r border-slate-200 bg-slate-50/70 p-4 flex flex-col overflow-hidden">
          <div className="flex items-center justify-between mb-3 shrink-0">
            <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">Document Text Viewer</span>
            <div className="flex items-center gap-1">
              <button
                disabled={activePageNum <= 1}
                onClick={() => setActivePageNum((p) => Math.max(1, p - 1))}
                className="p-1 rounded bg-slate-200 text-slate-700 disabled:opacity-40 hover:bg-slate-300"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <span className="text-xs font-mono px-2 text-slate-700 font-semibold">
                {activePageNum} / {contract.page_count}
              </span>
              <button
                disabled={activePageNum >= contract.page_count}
                onClick={() => setActivePageNum((p) => Math.min(contract.page_count, p + 1))}
                className="p-1 rounded bg-slate-200 text-slate-700 disabled:opacity-40 hover:bg-slate-300"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <div className="flex-1 bg-white p-4 rounded-xl border border-slate-200 overflow-y-auto font-serif text-xs leading-relaxed text-slate-800 select-text whitespace-pre-wrap shadow-inner">
            {activePageObj?.text_content || 'No text extracted for this page.'}
          </div>
        </div>

        {/* CENTER PANE (Col 4-7): Extracted Clause Cards List */}
        <div className="col-span-4 border-r border-slate-200 p-4 overflow-y-auto space-y-4 bg-slate-50/30">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Extracted Contract Clauses</h3>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowGeneralClauses(v => !v)}
                className={`text-xs px-2 py-1 rounded-lg border font-medium transition-colors ${
                  showGeneralClauses
                    ? 'bg-slate-200 text-slate-700 border-slate-300'
                    : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50'
                }`}
              >
                {showGeneralClauses ? 'Hide General Clauses' : 'Show General Clauses'}
              </button>
              <span className="text-xs text-indigo-600 font-mono font-bold">{contract.clauses.length} Clauses</span>
            </div>
          </div>

          <div className="space-y-4">
            {(() => {
              const displayedClauses = (contract.clauses || []).filter((cl: any) =>
                showGeneralClauses || !['general_clause', 'renewal_condition', 'termination_condition'].includes(cl.clause_type)
              );
              return displayedClauses.map((c) => (
                <ClauseCard
                  key={c.id}
                  clause={c}
                  onViewRule={(cl) => {
                    if (cl.rule) {
                      setSelectedRuleForModal({
                        id: cl.rule.id,
                        contract_id: contract.id,
                        clause_id: cl.id,
                        rule_code: cl.rule.rule_code,
                        rule_type: cl.clause_type,
                        title: cl.rule.title,
                        ir_json: cl.rule.ir_json,
                        validation_status: cl.rule.validation_status,
                        review_notes: cl.rule.review_notes,
                        human_explanation: cl.rule.human_explanation,
                        created_at: '',
                        source: { page: cl.page_number, section: cl.section_number, clause_text: cl.original_text }
                      });
                    }
                  }}
                  onValidate={handleValidate}
                  onSimulate={(cl) => onSimulate(contract.id, variables)}
                  onShowEvidence={(cl) => setSelectedClauseForEvidence(cl)}
                />
              ));
            })()}
          </div>
        </div>

        {/* RIGHT PANE (Col 8-12): Deterministic Sandbox Execution Panel */}
        <div className="col-span-5 p-4 overflow-y-auto space-y-6 bg-slate-50/50">
          <div className="glass-panel p-5 rounded-2xl border border-indigo-200 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Calculator className="w-4 h-4 text-indigo-600" />
                Input Variable Sandbox & Deterministic Execution
              </h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-700 font-bold border border-emerald-200">
                Zero LLM Math
              </span>
            </div>

            {/* Form Inputs Grid */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <label className="text-[11px] font-semibold text-slate-700 block mb-1">Contract Value ($)</label>
                <input
                  type="number"
                  value={variables.contract_value}
                  onChange={(e) => setVariables({ ...variables, contract_value: parseFloat(e.target.value) || 0 })}
                  className="w-full bg-slate-100 border border-slate-200 rounded-lg p-2 text-slate-900 font-mono text-xs focus:bg-white focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-700 block mb-1">Payment Delay (Days)</label>
                <input
                  type="number"
                  value={variables.payment_delay_days}
                  onChange={(e) => setVariables({ ...variables, payment_delay_days: parseInt(e.target.value) || 0 })}
                  className="w-full bg-slate-100 border border-slate-200 rounded-lg p-2 text-slate-900 font-mono text-xs focus:bg-white focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-700 block mb-1">Delivery Delay (Days)</label>
                <input
                  type="number"
                  value={variables.delivery_delay_days}
                  onChange={(e) => setVariables({ ...variables, delivery_delay_days: parseInt(e.target.value) || 0 })}
                  className="w-full bg-slate-100 border border-slate-200 rounded-lg p-2 text-slate-900 font-mono text-xs focus:bg-white focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-700 block mb-1">Order Quantity (Units)</label>
                <input
                  type="number"
                  value={variables.order_quantity}
                  onChange={(e) => setVariables({ ...variables, order_quantity: parseInt(e.target.value) || 0 })}
                  className="w-full bg-slate-100 border border-slate-200 rounded-lg p-2 text-slate-900 font-mono text-xs focus:bg-white focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-700 block mb-1">SLA Uptime (%)</label>
                <input
                  type="number"
                  step="0.1"
                  value={variables.sla_uptime_percent}
                  onChange={(e) => setVariables({ ...variables, sla_uptime_percent: parseFloat(e.target.value) || 0 })}
                  className="w-full bg-slate-100 border border-slate-200 rounded-lg p-2 text-slate-900 font-mono text-xs focus:bg-white focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-700 block mb-1">Inflation Rate (%)</label>
                <input
                  type="number"
                  step="0.1"
                  value={variables.inflation_rate_percent}
                  onChange={(e) => setVariables({ ...variables, inflation_rate_percent: parseFloat(e.target.value) || 0 })}
                  className="w-full bg-slate-100 border border-slate-200 rounded-lg p-2 text-slate-900 font-mono text-xs focus:bg-white focus:border-indigo-500"
                />
              </div>
            </div>

            <button
              onClick={handleExecute}
              disabled={executing}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-700 to-cyan-600 hover:from-indigo-500 hover:to-indigo-600 text-white font-bold text-xs shadow-lg shadow-indigo-600/20 transition-all disabled:opacity-50"
            >
              {executing ? (
                <span>Executing Deterministic Rules...</span>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current" />
                  <span>Execute Deterministic Rules</span>
                </>
              )}
            </button>
          </div>

          {/* Execution Output Panel */}
          {executionResult && (
            <div className="glass-panel p-5 rounded-2xl border border-emerald-200 space-y-4 animate-in fade-in duration-200 shadow-sm">
              <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                <div>
                  <span className="text-[10px] text-slate-500 uppercase font-bold tracking-wider block">Total Financial Impact</span>
                  <span className={`text-2xl font-extrabold font-mono ${
                    executionResult.total_financial_impact > 0 ? 'text-rose-600' : executionResult.total_financial_impact < 0 ? 'text-emerald-600' : 'text-slate-800'
                  }`}>
                    ${executionResult.total_financial_impact.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <span className="px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-700 border border-emerald-200 font-mono text-xs font-bold">
                  {executionResult.applied_rules.length} Rules Applied
                </span>
              </div>

              {/* Step-by-Step Breakdown */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Calculation Trace Steps</h4>
                {executionResult.calculation_steps.map((step) => (
                  <div key={step.step_number} className="p-3 rounded-xl bg-white border border-slate-200 text-xs space-y-1.5 shadow-xs">
                    <div className="flex items-center justify-between font-mono">
                      <span className="font-bold text-slate-900">
                        Step {step.step_number}: [{step.rule_code}] {step.title}
                      </span>
                      <span className={`font-bold ${step.subtotal > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                        ${step.subtotal.toLocaleString()}
                      </span>
                    </div>
                    <p className="text-slate-700 leading-normal text-[11px]">{step.description}</p>
                    {step.formula && (
                      <div className="font-mono text-[10px] text-indigo-700 bg-indigo-50 px-2 py-1 rounded border border-indigo-100">
                        Formula: {step.formula}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      <EvidenceModal
        clause={selectedClauseForEvidence}
        onClose={() => setSelectedClauseForEvidence(null)}
      />

      <RuleEditorModal
        rule={selectedRuleForModal}
        onClose={() => setSelectedRuleForModal(null)}
        onValidate={handleValidate}
      />
    </div>
  );
};
