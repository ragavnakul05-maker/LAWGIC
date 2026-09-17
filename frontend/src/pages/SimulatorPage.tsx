import React, { useState, useEffect, useMemo } from 'react';
import {
  Play, RefreshCw, AlertCircle, RotateCcw, Download, ChevronDown, FileSpreadsheet, FileCode, Printer
} from 'lucide-react';
import {
  fetchContracts, fetchContractSimulatorSchema, compareContractSimulation, exportSimulationReport
} from '../services/api';
import {
  ContractSimulatorSchemaResponse, ContractSimulationComparisonResponse,
  ContractRuleComparisonResult
} from '../types';
import { formatINR, formatINRImpact as formatImpact } from '../utils/currency';

interface SimulatorPageProps {
  defaultContractId?: string;
}

interface AggregatedCategoryResult {
  key: string;
  parameterLabel: string;
  unit: string;
  originalParameterValue: any;
  whatIfParameterValue: any;
  originalResult: number;
  whatIfResult: number;
  difference: number;
  section1Label: string;
  section5Category: string;
  rulesCount: number;
}

// Canonical category mapper & rule aggregator
const aggregateRulesByCategory = (
  rules: ContractRuleComparisonResult[] = [],
  originalVars: Record<string, any> = {},
  whatIfVars: Record<string, any> = {}
): AggregatedCategoryResult[] => {
  const categoryMap = new Map<string, AggregatedCategoryResult>();

  for (const rule of rules) {
    let key = rule.parameter_name;
    let paramLabel = rule.parameter_label;
    let unit = rule.unit || '';
    let s1Label = 'Total Result';
    let s5Category = 'Result';

    // Map to canonical Legal IR semantic identity
    if (rule.parameter_name === 'delivery_delay_days' || rule.rule_type === 'delivery_delay_penalty') {
      key = 'delivery_delay_days';
      paramLabel = 'Delivery Delay';
      unit = 'days';
      s1Label = 'Total Delivery Penalty';
      s5Category = 'Delivery Penalty';
    } else if (rule.parameter_name === 'payment_delay_days' || rule.rule_type === 'late_payment_interest') {
      key = 'payment_delay_days';
      paramLabel = 'Payment Delay';
      unit = 'days';
      s1Label = 'Total Interest';
      s5Category = 'Interest';
    } else if (rule.parameter_name === 'order_quantity' || rule.rule_type === 'volume_discount') {
      key = 'order_quantity';
      paramLabel = 'Order Quantity';
      unit = 'units';
      s1Label = 'Total Discount';
      s5Category = 'Discount';
    } else if (rule.parameter_name === 'sla_uptime_percent' || rule.rule_type === 'sla_penalty') {
      key = 'sla_uptime_percent';
      paramLabel = 'SLA Uptime';
      unit = '%';
      s1Label = 'Total SLA Deduction';
      s5Category = 'SLA Deduction';
    } else if (rule.parameter_name === 'inflation_rate_percent' || rule.rule_type === 'price_escalation') {
      key = 'inflation_rate_percent';
      paramLabel = 'Annual Inflation Rate';
      unit = '%';
      s1Label = 'Total Price Adjustment';
      s5Category = 'Price Adjustment';
    } else {
      key = rule.parameter_name || rule.rule_type;
      paramLabel = rule.parameter_label || rule.rule_title;
      unit = rule.unit || '';
      s1Label = `Total ${paramLabel}`;
      s5Category = paramLabel;
    }

    const origParamVal = originalVars[key] !== undefined ? originalVars[key] : rule.original_parameter_value;
    const whatIfParamVal = whatIfVars[key] !== undefined ? whatIfVars[key] : (rule.what_if_parameter_value ?? origParamVal);

    if (!categoryMap.has(key)) {
      categoryMap.set(key, {
        key,
        parameterLabel: paramLabel,
        unit,
        originalParameterValue: origParamVal,
        whatIfParameterValue: whatIfParamVal,
        originalResult: rule.original_result,
        whatIfResult: rule.what_if_result,
        difference: rule.difference,
        section1Label: s1Label,
        section5Category: s5Category,
        rulesCount: 1,
      });
    } else {
      const existing = categoryMap.get(key)!;
      existing.originalResult = Math.round((existing.originalResult + rule.original_result) * 100) / 100;
      existing.whatIfResult = Math.round((existing.whatIfResult + rule.what_if_result) * 100) / 100;
      existing.difference = Math.round((existing.whatIfResult - existing.originalResult) * 100) / 100;
      existing.rulesCount += 1;
    }
  }

  return Array.from(categoryMap.values());
};

export const SimulatorPage: React.FC<SimulatorPageProps> = ({ defaultContractId = 'DEMO-CONTRACT-001' }) => {
  const [contractId, setContractId] = useState(defaultContractId);
  const [contracts, setContracts] = useState<any[]>([]);
  const [schema, setSchema] = useState<ContractSimulatorSchemaResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Original contract baseline variables
  const [originalVars, setOriginalVars] = useState<Record<string, any>>({});

  // What-If modified variables (editable by user)
  const [whatIfVars, setWhatIfVars] = useState<Record<string, any>>({});

  // Original Contract Simulation results (Baseline)
  const [baselineComparison, setBaselineComparison] = useState<ContractSimulationComparisonResponse | null>(null);

  // What-If Simulation results (after user clicks Simulate)
  const [whatIfComparison, setWhatIfComparison] = useState<ContractSimulationComparisonResponse | null>(null);

  // Export State
  const [exportOpen, setExportOpen] = useState<boolean>(false);
  const [exporting, setExporting] = useState<boolean>(false);

  // Load uploaded contracts on mount
  useEffect(() => {
    fetchContracts().then(data => {
      setContracts(data);
      if (data && data.length > 0) {
        if (!data.some((c: any) => c.id === contractId)) {
          setContractId(data[0].id);
        }
      }
    }).catch(err => {
      console.error('Failed to load contracts:', err);
    });
  }, []);

  // When contractId changes, load parameters & baseline simulation results
  useEffect(() => {
    if (!contractId) return;
    loadContractData(contractId);
  }, [contractId]);

  const loadContractData = async (id: string) => {
    setLoading(true);
    setError(null);
    setWhatIfComparison(null);

    try {
      // 1. Fetch dynamic contract schema
      const schemaData = await fetchContractSimulatorSchema(id);
      setSchema(schemaData);

      const baseline = schemaData.baseline_variables || {};
      setOriginalVars(baseline);
      setWhatIfVars({ ...baseline });

      // 2. Automatically calculate Original Contract Scenario results using deterministic engine
      try {
        const baselineRes = await compareContractSimulation(id, baseline, baseline);
        setBaselineComparison(baselineRes);
      } catch (calcErr: any) {
        console.warn('Could not pre-calculate baseline simulation:', calcErr);
        setBaselineComparison(null);
      }
    } catch (err: any) {
      console.error('Failed to load contract parameters:', err);
      setError(err.message || 'Failed to load parameters for this contract.');
      setSchema(null);
      setBaselineComparison(null);
      setOriginalVars({});
      setWhatIfVars({});
    } finally {
      setLoading(false);
    }
  };

  // Run What-If Simulation using existing deterministic rule engine
  const handleSimulate = async () => {
    if (!contractId || !schema) return;
    setSimulating(true);
    setError(null);

    try {
      const res = await compareContractSimulation(contractId, whatIfVars, originalVars);
      setWhatIfComparison(res);
    } catch (err: any) {
      console.error('What-If simulation error:', err);
      setError(err.message || 'Failed to run simulation.');
    } finally {
      setSimulating(false);
    }
  };

  // Reset What-If variables to match original contract values
  const handleReset = () => {
    setWhatIfVars({ ...originalVars });
    setWhatIfComparison(null);
  };

  // Export simulation comparison report
  const handleExport = async (format: 'html' | 'csv' | 'json') => {
    if (!whatIfComparison) return;
    try {
      setExporting(true);
      await exportSimulationReport(whatIfComparison, format);
    } catch (err: any) {
      console.error('Export failed:', err);
      alert(err.message || 'Failed to export simulation report');
    } finally {
      setExporting(false);
      setExportOpen(false);
    }
  };

  const selectedContract = contracts.find(c => c.id === contractId);

  // Deduplicate parameters strictly by canonical variable_name
  const allParams = schema?.parameters || [];
  const uniqueParams = useMemo(() => {
    const map = new Map<string, typeof allParams[0]>();
    for (const p of allParams) {
      if (!map.has(p.variable_name)) {
        map.set(p.variable_name, p);
      }
    }
    return Array.from(map.values());
  }, [allParams]);

  const uniqueBaseParams = uniqueParams.filter(
    p => p.variable_name === 'contract_value' || p.variable_name === 'invoice_amount'
  );
  const uniqueOperationalParams = uniqueParams.filter(
    p => p.variable_name !== 'contract_value' && p.variable_name !== 'invoice_amount'
  );

  // Aggregated original contract rules (Section 1)
  const aggregatedBaseline = useMemo(() => {
    if (!baselineComparison?.rules) return [];
    return aggregateRulesByCategory(baselineComparison.rules, originalVars, originalVars);
  }, [baselineComparison, originalVars]);

  // Aggregated what-if simulation results (Section 5 Result)
  const aggregatedWhatIf = useMemo(() => {
    if (!whatIfComparison?.rules) return [];
    return aggregateRulesByCategory(whatIfComparison.rules, originalVars, whatIfVars);
  }, [whatIfComparison, originalVars, whatIfVars]);

  return (
    <div className="p-6 md:p-10 max-w-4xl mx-auto space-y-8">
      {/* Clean Contract Selector Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-600 block">
            What-If Simulator
          </span>
          <h1 className="text-xl font-bold text-slate-900">
            {selectedContract ? selectedContract.title : 'Select a Contract'}
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <label className="text-xs font-bold text-slate-600 shrink-0">Contract:</label>
          <select
            value={contractId}
            onChange={e => setContractId(e.target.value)}
            disabled={loading || simulating}
            className="bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
          >
            {contracts.length === 0 ? (
              <option value={contractId}>{contractId}</option>
            ) : (
              contracts.map((c: any) => (
                <option key={c.id} value={c.id}>
                  {c.title} ({c.id})
                </option>
              ))
            )}
          </select>
          {loading && <RefreshCw className="w-4 h-4 text-indigo-600 animate-spin" />}
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      )}

      {/* ============================================================ */}
      {/* SECTION 1: CONTRACT SIMULATION (ORIGINAL / ACTUAL SCENARIO) */}
      {/* ============================================================ */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 md:p-8 shadow-xs space-y-6">
        <div className="border-b border-slate-100 pb-4">
          <h2 className="text-base font-extrabold text-slate-900 uppercase tracking-wider">
            1. Contract Simulation
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Current uploaded contract scenario with unique actionable terms and aggregated calculated results.
          </p>
        </div>

        {loading ? (
          <div className="py-8 text-center text-xs text-slate-500 space-y-2">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto text-indigo-600" />
            <p>Evaluating contract rules and calculating baseline scenario...</p>
          </div>
        ) : aggregatedBaseline.length === 0 ? (
          <div className="p-5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 text-center">
            No actionable financial rules (penalties, discounts, SLA deductions) exist in this contract.
          </div>
        ) : (
          <div className="space-y-4">
            {/* List of Unique Actionable Terms with Aggregated Financial Results */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {aggregatedBaseline.map((item) => {
                const isDiscount = item.section5Category === 'Discount';
                const displayedResult = isDiscount
                  ? Math.abs(item.originalResult)
                  : item.originalResult;

                return (
                  <div
                    key={item.key}
                    className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-700">
                        {item.parameterLabel}:
                      </span>
                      <span className="font-bold font-mono text-slate-900 text-sm">
                        {item.originalParameterValue} {item.unit}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs pt-2.5 border-t border-slate-200/70">
                      <span className="font-semibold text-slate-700">
                        {item.section1Label}:
                      </span>
                      <span className="font-bold font-mono text-indigo-950 text-sm">
                        {formatINR(displayedResult)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Base Contract Value / Invoice Amount (Each shown strictly once) */}
            {uniqueBaseParams.map((param) => {
              const currentVal = originalVars[param.variable_name] ?? param.default_value;
              return (
                <div
                  key={param.variable_name}
                  className="flex items-center justify-between p-3.5 rounded-xl bg-slate-100/70 border border-slate-200 text-xs"
                >
                  <span className="font-semibold text-slate-700">
                    Current {param.label}:
                  </span>
                  <span className="font-mono font-bold text-slate-900 text-sm">
                    {formatINR(currentVal)}
                  </span>
                </div>
              );
            })}

            {/* Total Original Contract Impact Summary */}
            {baselineComparison && (
              <div className="flex items-center justify-between p-4 rounded-xl bg-indigo-50/70 border border-indigo-100 text-xs">
                <span className="font-bold text-indigo-950 uppercase tracking-wide">
                  Original Contract Total Result:
                </span>
                <span className="font-mono font-extrabold text-indigo-950 text-base">
                  {formatINR(baselineComparison.original_total_impact)}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ============================================================ */}
      {/* SECTION 2: WHAT-IF SIMULATION (EDITABLE WHAT-IF PARAMETERS)   */}
      {/* ============================================================ */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 md:p-8 shadow-xs space-y-6">
        <div className="border-b border-slate-100 pb-4">
          <h2 className="text-base font-extrabold text-slate-900 uppercase tracking-wider">
            2. What-If Simulation
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Modify unique parameters below to simulate hypothetical scenarios and view comparative impact.
          </p>
        </div>

        {loading ? (
          <div className="py-6 text-center text-xs text-slate-400">Loading parameters...</div>
        ) : uniqueParams.length === 0 ? (
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-500 text-center">
            No adjustable parameters available for this contract.
          </div>
        ) : (
          <div className="space-y-6">
            {/* Editable Input Parameters (Each shown strictly once with Original value clearly visible) */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Unique Operational parameters (Delivery Delay, Payment Delay, Order Quantity, SLA Uptime, etc.) */}
              {uniqueOperationalParams.map((param) => {
                const origVal = originalVars[param.variable_name] !== undefined
                  ? originalVars[param.variable_name]
                  : param.default_value;
                const currentWhatIfVal = whatIfVars[param.variable_name] !== undefined
                  ? whatIfVars[param.variable_name]
                  : origVal;

                return (
                  <div
                    key={param.variable_name}
                    className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-800">
                        {param.label}
                      </span>
                      <span className="text-[11px] font-mono text-slate-500">
                        Original: <strong className="text-slate-800">{origVal} {param.unit}</strong>
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-indigo-700 shrink-0">
                        What-If:
                      </span>
                      <input
                        type="number"
                        value={currentWhatIfVal}
                        step={param.step ?? (param.variable_name.includes('percent') ? 0.1 : 1)}
                        onChange={(e) => setWhatIfVars({
                          ...whatIfVars,
                          [param.variable_name]: parseFloat(e.target.value) || 0
                        })}
                        className="w-full bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs font-mono font-bold text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all"
                      />
                      {param.unit && (
                        <span className="text-xs font-semibold text-slate-500 shrink-0 min-w-[2.5rem]">
                          {param.unit}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Unique Base monetary parameters (Contract Value / Invoice Amount) */}
              {uniqueBaseParams.map((param) => {
                const origVal = originalVars[param.variable_name] !== undefined
                  ? originalVars[param.variable_name]
                  : param.default_value;
                const currentWhatIfVal = whatIfVars[param.variable_name] !== undefined
                  ? whatIfVars[param.variable_name]
                  : origVal;

                return (
                  <div
                    key={param.variable_name}
                    className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-800">
                        {param.label}
                      </span>
                      <span className="text-[11px] font-mono text-slate-500">
                        Original: <strong className="text-slate-800">{formatINR(origVal)}</strong>
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-indigo-700 shrink-0">
                        What-If:
                      </span>
                      <div className="relative w-full">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs font-bold text-slate-500">
                          ₹
                        </span>
                        <input
                          type="number"
                          value={currentWhatIfVal}
                          step={10000}
                          onChange={(e) => setWhatIfVars({
                            ...whatIfVars,
                            [param.variable_name]: parseFloat(e.target.value) || 0
                          })}
                          className="w-full bg-white border border-slate-300 rounded-lg pl-7 pr-3 py-1.5 text-xs font-mono font-bold text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all"
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Simulate Action Buttons */}
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                onClick={handleSimulate}
                disabled={simulating || loading}
                className="px-8 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-md shadow-indigo-600/20 transition-all cursor-pointer disabled:opacity-50"
              >
                {simulating ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Simulating...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-current" />
                    <span>Simulate</span>
                  </>
                )}
              </button>

              <button
                onClick={handleReset}
                disabled={simulating || loading}
                className="px-4 py-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Reset</span>
              </button>
            </div>

            {/* ============================================================ */}
            {/* SIMULATION RESULT DISPLAY (AGGREGATED BY CATEGORY)           */}
            {/* ============================================================ */}
            {whatIfComparison && (
              <div className="mt-8 pt-6 border-t border-slate-200/80 space-y-6 animate-in fade-in duration-300">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-extrabold uppercase tracking-wider text-slate-900">
                      Result:
                    </span>
                    <span className="text-[11px] font-mono text-slate-500">
                      Evaluated across all {whatIfComparison.rules.length} contract rule(s)
                    </span>
                  </div>

                  {/* Export Scenario Report Dropdown */}
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setExportOpen(prev => !prev)}
                      disabled={exporting}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold text-xs rounded-xl border border-indigo-200 transition-colors shadow-xs disabled:opacity-50 cursor-pointer"
                      title="Export What-If Scenario Comparison Report"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>{exporting ? 'Exporting...' : 'Export Report'}</span>
                      <ChevronDown className={`w-3 h-3 transition-transform ${exportOpen ? 'rotate-180' : ''}`} />
                    </button>

                    {exportOpen && (
                      <div className="absolute right-0 mt-1.5 w-56 bg-white rounded-xl shadow-xl border border-slate-200 py-1.5 z-50 animate-in fade-in zoom-in-95 duration-100">
                        <div className="px-3 py-1.5 border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                          Export Formats
                        </div>
                        <button
                          onClick={() => handleExport('html')}
                          className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-indigo-50 hover:text-indigo-700 flex items-center gap-2.5 transition-colors cursor-pointer"
                        >
                          <Printer className="w-4 h-4 text-indigo-500 shrink-0" />
                          <div>
                            <div className="font-semibold">Executive PDF Report</div>
                            <div className="text-[10px] text-slate-400">Printable comparison sheet</div>
                          </div>
                        </button>
                        <button
                          onClick={() => handleExport('csv')}
                          className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-emerald-50 hover:text-emerald-700 flex items-center gap-2.5 transition-colors cursor-pointer"
                        >
                          <FileSpreadsheet className="w-4 h-4 text-emerald-500 shrink-0" />
                          <div>
                            <div className="font-semibold">CSV Spreadsheet</div>
                            <div className="text-[10px] text-slate-400">Tabular delta analysis</div>
                          </div>
                        </button>
                        <button
                          onClick={() => handleExport('json')}
                          className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-amber-50 hover:text-amber-700 flex items-center gap-2.5 transition-colors cursor-pointer"
                        >
                          <FileCode className="w-4 h-4 text-amber-500 shrink-0" />
                          <div>
                            <div className="font-semibold">JSON Package</div>
                            <div className="text-[10px] text-slate-400">Raw comparison schema</div>
                          </div>
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Overall Contract Total Result Tiles */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block">
                      Total Original
                    </span>
                    <div className="text-lg font-mono font-bold text-slate-800">
                      {formatINR(whatIfComparison.original_total_impact)}
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-indigo-50/70 border border-indigo-200 space-y-1">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-700 block">
                      Total What-If
                    </span>
                    <div className="text-lg font-mono font-bold text-indigo-900">
                      {formatINR(whatIfComparison.what_if_total_impact)}
                    </div>
                  </div>

                  <div className={`p-4 rounded-xl border space-y-1 ${
                    whatIfComparison.net_difference > 0
                      ? 'bg-rose-50 border-rose-200'
                      : whatIfComparison.net_difference < 0
                        ? 'bg-emerald-50 border-emerald-200'
                        : 'bg-slate-50 border-slate-200'
                  }`}>
                    <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 block">
                      Total Impact
                    </span>
                    <div className={`text-lg font-mono font-extrabold ${
                      whatIfComparison.net_difference > 0
                        ? 'text-rose-600'
                        : whatIfComparison.net_difference < 0
                          ? 'text-emerald-600'
                          : 'text-slate-800'
                    }`}>
                      {formatImpact(whatIfComparison.net_difference)}
                    </div>
                  </div>
                </div>

                {/* Aggregated Result Cards Per Parameter / Category */}
                <div className="space-y-3 pt-1">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 block">
                    Category Breakdown:
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                    {aggregatedWhatIf.map((item) => {
                      const isDiscount = item.section5Category === 'Discount';
                      const origVal = isDiscount ? Math.abs(item.originalResult) : item.originalResult;
                      const whatIfVal = isDiscount ? Math.abs(item.whatIfResult) : item.whatIfResult;

                      return (
                        <div
                          key={item.key}
                          className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5"
                        >
                          <span className="text-xs font-bold text-slate-900 block">
                            {item.section5Category}
                          </span>

                          <div className="space-y-1.5 text-xs font-mono">
                            <div className="flex justify-between text-slate-600">
                              <span>Original:</span>
                              <span className="font-semibold text-slate-800">{formatINR(origVal)}</span>
                            </div>
                            <div className="flex justify-between text-indigo-900">
                              <span>What-If:</span>
                              <span className="font-bold text-indigo-900">{formatINR(whatIfVal)}</span>
                            </div>
                            <div className="flex justify-between pt-1.5 border-t border-slate-200 font-bold">
                              <span className="text-slate-600">Impact:</span>
                              <span className={
                                item.difference > 0
                                  ? 'text-rose-600'
                                  : item.difference < 0
                                    ? 'text-emerald-600'
                                    : 'text-slate-600'
                              }>
                                {formatImpact(item.difference)}
                              </span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default SimulatorPage;
