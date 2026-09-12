import React, { useState, useEffect } from 'react';
import { Sliders, Play, Sparkles, Plus, Trash2, BarChart2, CheckCircle, MessageSquare, ArrowRight, Zap, FileText, Info } from 'lucide-react';
import { runSimulation, fetchContracts, fetchContractDetail } from '../services/api';
import { SimulationResponse, ContractDetail } from '../types';
import { ScenarioComparisonTable } from '../components/ScenarioComparisonTable';

interface SimulatorPageProps {
  defaultContractId?: string;
}

// Map rule types to their primary variables for dynamic UI filtering
const RULE_TYPE_VARIABLE_MAP: Record<string, string[]> = {
  late_payment_interest: ['invoice_amount', 'payment_delay_days'],
  delivery_delay_penalty: ['contract_value', 'delivery_delay_days'],
  volume_discount: ['contract_value', 'order_quantity'],
  sla_penalty: ['invoice_amount', 'sla_uptime_percent'],
  price_escalation: ['contract_value', 'inflation_rate_percent']
};

export const SimulatorPage: React.FC<SimulatorPageProps> = ({ defaultContractId = 'DEMO-CONTRACT-001' }) => {
  const [contractId, setContractId] = useState(defaultContractId);
  const [contracts, setContracts] = useState<any[]>([]);
  const [selectedContract, setSelectedContract] = useState<ContractDetail | null>(null);
  const [loadingContract, setLoadingContract] = useState(false);
  const [running, setRunning] = useState(false);
  const [simulationResult, setSimulationResult] = useState<SimulationResponse | null>(null);

  // Natural Language Prompt State
  const [nlQuery, setNlQuery] = useState('');
  const [nlParseNotice, setNlParseNotice] = useState<string | null>(null);

  // Baseline variable inputs
  const [baselineVars, setBaselineVars] = useState<Record<string, any>>({
    contract_value: 1000000.0,
    invoice_amount: 1000000.0,
    payment_delay_days: 0,
    delivery_delay_days: 0,
    order_quantity: 500,
    sla_uptime_percent: 100.0,
    inflation_rate_percent: 0.0
  });

  // Dynamic Scenarios List
  const [scenariosInput, setScenariosInput] = useState<Array<{ scenario_name: string; variable_overrides: Record<string, any> }>>([
    {
      scenario_name: 'Scenario 1: Delivery Delay (20 Days)',
      variable_overrides: { delivery_delay_days: 20 }
    },
    {
      scenario_name: 'Scenario 2: Severe Delay (40 Days)',
      variable_overrides: { delivery_delay_days: 40 }
    }
  ]);

  // Active variables needed by the current contract's rules
  const [activeVariableKeys, setActiveVariableKeys] = useState<string[]>([
    'contract_value', 'invoice_amount', 'delivery_delay_days', 'payment_delay_days'
  ]);

  // Load contract list on mount
  useEffect(() => {
    fetchContracts().then(data => {
      setContracts(data);
      if (data.length > 0 && !defaultContractId) {
        setContractId(data[0].id);
      }
    }).catch(console.error);
  }, []);

  // Load contract detail whenever selected contract changes
  useEffect(() => {
    if (!contractId) return;
    setLoadingContract(true);
    fetchContractDetail(contractId)
      .then(detail => {
        setSelectedContract(detail);
        setLoadingContract(false);
        adaptSimulatorToContract(detail);
      })
      .catch(err => {
        console.error('Failed to load contract detail', err);
        setLoadingContract(false);
      });
  }, [contractId]);

  const adaptSimulatorToContract = (contract: ContractDetail) => {
    const rules = (contract.clauses || []).map(c => c.rule).filter(Boolean);
    const ruleTypes = rules.map(r => r?.ir_json?.type).filter(Boolean) as string[];

    // Extract all relevant variable keys for this contract's rules
    const keysSet = new Set<string>(['contract_value', 'invoice_amount']);
    ruleTypes.forEach(rt => {
      const vars = RULE_TYPE_VARIABLE_MAP[rt] || [];
      vars.forEach(v => keysSet.add(v));
    });
    const relevantKeys = Array.from(keysSet);
    setActiveVariableKeys(relevantKeys);

    // Initialise baseline variables for relevant keys
    const newVars: Record<string, any> = {
      contract_value: 1000000.0,
      invoice_amount: 1000000.0,
      payment_delay_days: 0,
      delivery_delay_days: 0,
      order_quantity: 500,
      sla_uptime_percent: 100.0,
      inflation_rate_percent: 0.0
    };

    // Smart default scenarios tailored to the contract's specific rules
    const defaultScenarios: Array<{ scenario_name: string; variable_overrides: Record<string, any> }> = [];

    if (ruleTypes.includes('delivery_delay_penalty')) {
      newVars.delivery_delay_days = 5;
      defaultScenarios.push(
        { scenario_name: 'Scenario A: 15 Days Delivery Delay', variable_overrides: { delivery_delay_days: 15 } },
        { scenario_name: 'Scenario B: 35 Days Severe Delay (Capped)', variable_overrides: { delivery_delay_days: 35 } }
      );
    }

    if (ruleTypes.includes('late_payment_interest')) {
      newVars.payment_delay_days = 10;
      defaultScenarios.push(
        { scenario_name: 'Scenario C: 45 Days Late Payment', variable_overrides: { payment_delay_days: 45 } }
      );
    }

    if (ruleTypes.includes('volume_discount')) {
      newVars.order_quantity = 800;
      defaultScenarios.push(
        { scenario_name: 'Scenario D: 1,500 Units Bulk Tier Discount', variable_overrides: { order_quantity: 1500 } }
      );
    }

    if (ruleTypes.includes('sla_penalty')) {
      newVars.sla_uptime_percent = 99.8;
      defaultScenarios.push(
        { scenario_name: 'Scenario E: SLA Breach (98.5% Uptime)', variable_overrides: { sla_uptime_percent: 98.5 } }
      );
    }

    if (ruleTypes.includes('price_escalation')) {
      newVars.inflation_rate_percent = 1.5;
      defaultScenarios.push(
        { scenario_name: 'Scenario F: High Inflation (4.5% CPI)', variable_overrides: { inflation_rate_percent: 4.5 } }
      );
    }

    if (defaultScenarios.length === 0) {
      defaultScenarios.push(
        { scenario_name: 'Scenario A: 20 Days Delay', variable_overrides: { delivery_delay_days: 20 } },
        { scenario_name: 'Scenario B: 40 Days Delay', variable_overrides: { delivery_delay_days: 40 } }
      );
    }

    setBaselineVars(newVars);
    setScenariosInput(defaultScenarios);
    setSimulationResult(null);
  };

  // Natural Language Query Parser
  const handleParseNLQuery = () => {
    if (!nlQuery.trim()) return;

    const lower = nlQuery.toLowerCase();
    const overrides: Record<string, any> = {};
    const extractedDetails: string[] = [];

    // Extract numbers with context
    // 1. Delivery delay days
    const delMatch = lower.match(/(?:delivery|deliver|delayed|delay|late by)\s*(?:is|by|of)?\s*(\d+)\s*(?:days|day)?/i) ||
                     lower.match(/(\d+)\s*(?:days|day)\s*(?:delivery|delay|delayed)/i);
    if (delMatch) {
      const val = parseInt(delMatch[1]);
      overrides.delivery_delay_days = val;
      extractedDetails.push(`Delivery Delay: ${val} Days`);
    }

    // 2. Payment delay days
    const payMatch = lower.match(/(?:payment|paid|invoice|late payment)\s*(?:is|by|of|late by)?\s*(\d+)\s*(?:days|day)?/i) ||
                     lower.match(/(\d+)\s*(?:days|day)\s*(?:payment|late payment)/i);
    if (payMatch) {
      const val = parseInt(payMatch[1]);
      overrides.payment_delay_days = val;
      extractedDetails.push(`Payment Delay: ${val} Days`);
    }

    // 3. Order quantity
    const qtyMatch = lower.match(/(?:quantity|order|units|volume|bulk)\s*(?:of|is|=)?\s*(\d[\d,]*)\s*(?:units|pcs)?/i) ||
                     lower.match(/(\d[\d,]*)\s*(?:units|pcs|quantity)/i);
    if (qtyMatch) {
      const val = parseInt(qtyMatch[1].replace(/,/g, ''));
      overrides.order_quantity = val;
      extractedDetails.push(`Order Quantity: ${val.toLocaleString()} Units`);
    }

    // 4. SLA Uptime percent
    const slaMatch = lower.match(/(?:sla|uptime|availability)\s*(?:is|of|falls to|at)?\s*(\d+(?:\.\d+)?)\s*%/i) ||
                     lower.match(/(\d+(?:\.\d+)?)\s*%\s*(?:sla|uptime|availability)/i);
    if (slaMatch) {
      const val = parseFloat(slaMatch[1]);
      overrides.sla_uptime_percent = val;
      extractedDetails.push(`SLA Uptime: ${val}%`);
    }

    // 5. Inflation rate percent
    const infMatch = lower.match(/(?:inflation|cpi|price increase)\s*(?:is|of|at)?\s*(\d+(?:\.\d+)?)\s*%/i) ||
                     lower.match(/(\d+(?:\.\d+)?)\s*%\s*(?:inflation|cpi)/i);
    if (infMatch) {
      const val = parseFloat(infMatch[1]);
      overrides.inflation_rate_percent = val;
      extractedDetails.push(`Inflation Rate: ${val}%`);
    }

    if (Object.keys(overrides).length === 0) {
      setNlParseNotice('Could not extract parameters. Try phrasing like: "What if delivery is delayed by 25 days and order quantity is 1500 units?"');
      return;
    }

    // Create new scenario from parsed prompt
    const scenarioTitle = `Custom Prompt: "${nlQuery.length > 35 ? nlQuery.substring(0, 32) + '...' : nlQuery}"`;
    const newScenarios = [
      ...scenariosInput,
      { scenario_name: scenarioTitle, variable_overrides: overrides }
    ];

    setScenariosInput(newScenarios);
    setNlParseNotice(`Extracted parameters: ${extractedDetails.join(', ')}. Added as new scenario!`);

    // Auto-trigger simulation run
    runSimulation(contractId, baselineVars, newScenarios)
      .then(res => setSimulationResult(res))
      .catch(console.error);
  };

  const handleRunSimulation = async () => {
    setRunning(true);
    try {
      const res = await runSimulation(contractId, baselineVars, scenariosInput);
      setSimulationResult(res);
      setRunning(false);
    } catch (err: any) {
      alert(`Simulation Error: ${err.message || err}`);
      setRunning(false);
    }
  };

  // Scenario management functions
  const addScenario = () => {
    const nextNum = scenariosInput.length + 1;
    setScenariosInput([
      ...scenariosInput,
      {
        scenario_name: `Scenario ${nextNum}: Custom Test`,
        variable_overrides: { delivery_delay_days: 25 }
      }
    ]);
  };

  const removeScenario = (index: number) => {
    if (scenariosInput.length <= 1) {
      alert('Simulation requires at least one scenario.');
      return;
    }
    setScenariosInput(scenariosInput.filter((_, i) => i !== index));
  };

  const updateScenarioName = (index: number, name: string) => {
    const updated = [...scenariosInput];
    updated[index].scenario_name = name;
    setScenariosInput(updated);
  };

  const updateScenarioOverride = (index: number, key: string, val: any) => {
    const updated = [...scenariosInput];
    updated[index].variable_overrides = {
      ...updated[index].variable_overrides,
      [key]: val
    };
    setScenariosInput(updated);
  };

  const contractRules = (selectedContract?.clauses || []).map(c => ({
    clause_section: c.section_number,
    clause_title: c.title,
    rule: c.rule
  })).filter(item => item.rule);

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Sliders className="w-6 h-6 text-indigo-600" />
            What-If Scenario Financial Simulator
          </h2>
          <p className="text-xs text-slate-500 font-medium mt-0.5">
            Parameters adapt dynamically per contract rules. Combine <strong>Natural Language Queries</strong> or <strong>Direct Numerical Overrides</strong>.
          </p>
        </div>

        {/* Contract Selection Dropdown */}
        <div className="glass-panel p-3 rounded-2xl flex items-center gap-3 border border-indigo-100 bg-white shadow-xs">
          <label className="text-xs font-bold text-slate-700 whitespace-nowrap">Target Contract:</label>
          <select
            value={contractId}
            onChange={e => setContractId(e.target.value)}
            className="border border-slate-200 rounded-xl px-3 py-1.5 text-xs font-semibold bg-slate-50 text-slate-900 focus:bg-white focus:outline-none focus:border-indigo-500 min-w-[240px]"
          >
            {contracts.length === 0 ? (
              <option value={contractId}>{contractId}</option>
            ) : (
              contracts.map((c: any) => (
                <option key={c.id} value={c.id}>{c.title} ({c.id})</option>
              ))
            )}
          </select>
        </div>
      </div>

      {/* Contract Rules & Parameters Banner */}
      {selectedContract && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-600" />
              Active Contract Legal IR Rules ({contractRules.length})
            </h3>
            <span className="text-[11px] font-mono text-slate-500">Parameters adapt automatically to this contract</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {contractRules.map((item, idx) => {
              const r = item.rule;
              if (!r) return null;
              return (
                <div key={idx} className="p-3.5 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-indigo-600 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded-md">
                      {r.rule_code}
                    </span>
                    <span className="text-[10px] font-mono font-semibold text-slate-500">§{item.clause_section}</span>
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-900">{r.title}</h4>
                    <p className="text-[11px] text-slate-600 mt-0.5 line-clamp-2 leading-relaxed">{r.human_explanation}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Natural Language What-If Prompt Box */}
      <div className="glass-panel p-5 rounded-2xl border border-indigo-200/80 bg-gradient-to-r from-indigo-50/50 via-white to-cyan-50/30 space-y-3 shadow-xs">
        <div className="flex items-center justify-between">
          <label className="text-xs font-bold text-slate-900 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-600" />
            Natural Language What-If Query
          </label>
          <span className="text-[11px] text-slate-500">e.g. &ldquo;What if delivery is delayed by 25 days and payment is 30 days late?&rdquo;</span>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <input
              type="text"
              value={nlQuery}
              onChange={e => setNlQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleParseNLQuery()}
              placeholder="Type in plain language: 'What if delivery is late by 30 days and volume is 1500 units?'"
              className="w-full bg-white border border-slate-300 rounded-xl px-4 py-2.5 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 font-medium shadow-xs"
            />
          </div>
          <button
            onClick={handleParseNLQuery}
            className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-md shadow-indigo-600/20 whitespace-nowrap transition-all"
          >
            <Zap className="w-4 h-4" />
            Apply Query
          </button>
        </div>

        {nlParseNotice && (
          <div className="p-2.5 rounded-xl bg-indigo-50 border border-indigo-200 text-xs text-indigo-800 flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-indigo-600 shrink-0" />
            <span>{nlParseNotice}</span>
          </div>
        )}
      </div>

      {/* Simulator Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Baseline Variables & Scenario Builder */}
        <div className="space-y-6">
          {/* Baseline Variable Inputs (Filtered by contract rules) */}
          <div className="glass-panel p-6 rounded-2xl border border-indigo-200/80 space-y-5 shadow-sm">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center justify-between">
              <span>1. Baseline Operational Inputs</span>
              <span className="text-[10px] text-indigo-600 font-mono font-bold">Contract Parameters</span>
            </h3>

            <div className="space-y-4 text-xs">
              {activeVariableKeys.includes('contract_value') && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-slate-700 font-semibold">Contract / Order Value ($)</span>
                    <span className="font-mono text-slate-900 font-bold">${(baselineVars.contract_value || 0).toLocaleString()}</span>
                  </div>
                  <input
                    type="number"
                    value={baselineVars.contract_value || ''}
                    onChange={(e) => setBaselineVars({ ...baselineVars, contract_value: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-900 font-mono focus:bg-white focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              )}

              {activeVariableKeys.includes('invoice_amount') && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-slate-700 font-semibold">Invoice Amount ($)</span>
                    <span className="font-mono text-slate-900 font-bold">${(baselineVars.invoice_amount || 0).toLocaleString()}</span>
                  </div>
                  <input
                    type="number"
                    value={baselineVars.invoice_amount || ''}
                    onChange={(e) => setBaselineVars({ ...baselineVars, invoice_amount: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-900 font-mono focus:bg-white focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              )}

              {activeVariableKeys.includes('delivery_delay_days') && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-slate-700 font-semibold">Delivery Delay (Days)</span>
                    <span className="font-mono text-rose-600 font-bold">{baselineVars.delivery_delay_days || 0} Days</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={60}
                    value={baselineVars.delivery_delay_days || 0}
                    onChange={(e) => setBaselineVars({ ...baselineVars, delivery_delay_days: parseInt(e.target.value) || 0 })}
                    className="w-full accent-indigo-600"
                  />
                </div>
              )}

              {activeVariableKeys.includes('payment_delay_days') && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-slate-700 font-semibold">Payment Delay (Days)</span>
                    <span className="font-mono text-amber-600 font-bold">{baselineVars.payment_delay_days || 0} Days</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={60}
                    value={baselineVars.payment_delay_days || 0}
                    onChange={(e) => setBaselineVars({ ...baselineVars, payment_delay_days: parseInt(e.target.value) || 0 })}
                    className="w-full accent-indigo-600"
                  />
                </div>
              )}

              {activeVariableKeys.includes('order_quantity') && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-slate-700 font-semibold">Order Quantity (Units)</span>
                    <span className="font-mono text-cyan-700 font-bold">{(baselineVars.order_quantity || 0).toLocaleString()} Units</span>
                  </div>
                  <input
                    type="number"
                    value={baselineVars.order_quantity || ''}
                    onChange={(e) => setBaselineVars({ ...baselineVars, order_quantity: parseInt(e.target.value) || 0 })}
                    className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-900 font-mono focus:bg-white focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              )}

              {activeVariableKeys.includes('sla_uptime_percent') && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-slate-700 font-semibold">Achieved SLA Uptime (%)</span>
                    <span className="font-mono text-emerald-600 font-bold">{baselineVars.sla_uptime_percent || 100}%</span>
                  </div>
                  <input
                    type="number"
                    step="0.1"
                    value={baselineVars.sla_uptime_percent || ''}
                    onChange={(e) => setBaselineVars({ ...baselineVars, sla_uptime_percent: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-900 font-mono focus:bg-white focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              )}

              {activeVariableKeys.includes('inflation_rate_percent') && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-slate-700 font-semibold">CPI Inflation Rate (%)</span>
                    <span className="font-mono text-indigo-600 font-bold">{baselineVars.inflation_rate_percent || 0}%</span>
                  </div>
                  <input
                    type="number"
                    step="0.1"
                    value={baselineVars.inflation_rate_percent || ''}
                    onChange={(e) => setBaselineVars({ ...baselineVars, inflation_rate_percent: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-900 font-mono focus:bg-white focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              )}
            </div>
          </div>

          {/* Interactive Scenario Builder */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-200 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">2. What-If Scenarios ({scenariosInput.length})</h3>
              <button
                onClick={addScenario}
                className="flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 px-2.5 py-1 rounded-lg transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Scenario
              </button>
            </div>

            <div className="space-y-3">
              {scenariosInput.map((sc, idx) => (
                <div key={idx} className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <input
                      type="text"
                      value={sc.scenario_name}
                      onChange={e => updateScenarioName(idx, e.target.value)}
                      className="font-bold text-slate-900 bg-white border border-slate-200 rounded-lg px-2 py-1 flex-1 text-xs focus:outline-none focus:border-indigo-400"
                    />
                    <button
                      onClick={() => removeScenario(idx)}
                      className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                      title="Remove Scenario"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {/* Override controls */}
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    {activeVariableKeys.includes('delivery_delay_days') && (
                      <div>
                        <label className="text-slate-500 block mb-0.5">Delivery Delay (Days)</label>
                        <input
                          type="number"
                          value={sc.variable_overrides.delivery_delay_days ?? baselineVars.delivery_delay_days}
                          onChange={e => updateScenarioOverride(idx, 'delivery_delay_days', parseInt(e.target.value) || 0)}
                          className="w-full bg-white border border-slate-200 rounded px-2 py-1 font-mono focus:outline-none focus:border-indigo-400"
                        />
                      </div>
                    )}
                    {activeVariableKeys.includes('payment_delay_days') && (
                      <div>
                        <label className="text-slate-500 block mb-0.5">Payment Delay (Days)</label>
                        <input
                          type="number"
                          value={sc.variable_overrides.payment_delay_days ?? baselineVars.payment_delay_days}
                          onChange={e => updateScenarioOverride(idx, 'payment_delay_days', parseInt(e.target.value) || 0)}
                          className="w-full bg-white border border-slate-200 rounded px-2 py-1 font-mono focus:outline-none focus:border-indigo-400"
                        />
                      </div>
                    )}
                    {activeVariableKeys.includes('order_quantity') && (
                      <div>
                        <label className="text-slate-500 block mb-0.5">Order Quantity (Units)</label>
                        <input
                          type="number"
                          value={sc.variable_overrides.order_quantity ?? baselineVars.order_quantity}
                          onChange={e => updateScenarioOverride(idx, 'order_quantity', parseInt(e.target.value) || 0)}
                          className="w-full bg-white border border-slate-200 rounded px-2 py-1 font-mono focus:outline-none focus:border-indigo-400"
                        />
                      </div>
                    )}
                    {activeVariableKeys.includes('sla_uptime_percent') && (
                      <div>
                        <label className="text-slate-500 block mb-0.5">SLA Uptime (%)</label>
                        <input
                          type="number"
                          step="0.1"
                          value={sc.variable_overrides.sla_uptime_percent ?? baselineVars.sla_uptime_percent}
                          onChange={e => updateScenarioOverride(idx, 'sla_uptime_percent', parseFloat(e.target.value) || 0)}
                          className="w-full bg-white border border-slate-200 rounded px-2 py-1 font-mono focus:outline-none focus:border-indigo-400"
                        />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={handleRunSimulation}
              disabled={running || loadingContract}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-700 to-cyan-600 hover:from-indigo-500 hover:to-indigo-600 text-white font-bold text-xs shadow-lg shadow-indigo-600/25 transition-all disabled:opacity-50 mt-2"
            >
              {running ? (
                <span>Executing Simulation Engine...</span>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current" />
                  <span>RUN WHAT-IF SIMULATION</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Right 2 Columns: Financial Comparison Matrix & Visual Charts */}
        <div className="lg:col-span-2 space-y-6">
          {simulationResult ? (
            <>
              {/* Visual Impact Comparison Bar Chart */}
              <div className="glass-panel p-6 rounded-2xl border border-slate-200 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <BarChart2 className="w-4 h-4 text-indigo-600" />
                    Scenario Financial Impact Visual Scale
                  </h3>
                  <span className="text-xs text-indigo-600 font-mono font-semibold">100% Deterministic Engine</span>
                </div>

                <div className="space-y-4 pt-2">
                  {(() => {
                    const maxImpact = Math.max(...(simulationResult.visual_data?.map((v: any) => Math.abs(v.impact || 0)) || [1]), 1);
                    return simulationResult.visual_data.map((v, i) => (
                      <div key={i} className="space-y-1">
                        <div className="flex items-center justify-between text-xs font-mono">
                          <span className="font-bold text-slate-800">{v.name}</span>
                          <span className={`font-bold ${v.impact > 0 ? 'text-rose-600' : v.impact < 0 ? 'text-emerald-600' : 'text-slate-700'}`}>
                            ${v.impact.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                          </span>
                        </div>
                        <div className="w-full bg-slate-100 h-3.5 rounded-full overflow-hidden border border-slate-200 p-0.5">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              v.impact > 0 ? 'bg-rose-500' : v.impact < 0 ? 'bg-emerald-500' : 'bg-indigo-600'
                            }`}
                            style={{ width: `${Math.min(100, Math.max(8, (Math.abs(v.impact) / maxImpact) * 100))}%` }}
                          />
                        </div>
                      </div>
                    ));
                  })()}
                </div>
              </div>

              {/* Matrix Table */}
              <ScenarioComparisonTable data={simulationResult} />
            </>
          ) : (
            <div className="glass-panel p-12 rounded-2xl border border-slate-200 text-center space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mx-auto text-indigo-600">
                <Sparkles className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-slate-900">Ready to Run What-If Simulations</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
                Select your contract on the left. Type natural language queries or adjust numeric overrides, then click <strong>RUN WHAT-IF SIMULATION</strong> to generate an auditable financial impact comparison matrix.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
