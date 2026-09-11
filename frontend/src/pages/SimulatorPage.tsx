import React, { useState } from 'react';
import { Sliders, Play, Sparkles, TrendingUp, TrendingDown, RefreshCw, BarChart2 } from 'lucide-react';
import { runSimulation } from '../services/api';
import { SimulationResponse } from '../types';
import { ScenarioComparisonTable } from '../components/ScenarioComparisonTable';

interface SimulatorPageProps {
  defaultContractId?: string;
}

export const SimulatorPage: React.FC<SimulatorPageProps> = ({ defaultContractId = 'DEMO-CONTRACT-001' }) => {
  const [contractId, setContractId] = useState(defaultContractId);
  const [running, setRunning] = useState(false);
  const [simulationResult, setSimulationResult] = useState<SimulationResponse | null>(null);

  // Baseline variable inputs
  const [baselineVars, setBaselineVars] = useState({
    contract_value: 1000000.0,
    invoice_amount: 1000000.0,
    payment_delay_days: 10,
    delivery_delay_days: 5,
    order_quantity: 800,
    sla_uptime_percent: 99.8,
    inflation_rate_percent: 2.0
  });

  // Preset Scenario Permutations
  const [scenariosInput, setScenariosInput] = useState([
    {
      scenario_name: 'Scenario A: Mild Delay (20 Days)',
      variable_overrides: { delivery_delay_days: 20, payment_delay_days: 20 }
    },
    {
      scenario_name: 'Scenario B: Severe Supply Delay (40 Days)',
      variable_overrides: { delivery_delay_days: 40, payment_delay_days: 45 }
    },
    {
      scenario_name: 'Scenario C: High Volume Bulk Order (1,500 Units)',
      variable_overrides: { order_quantity: 1500, delivery_delay_days: 5 }
    }
  ]);

  const handleRunSimulation = async () => {
    setRunning(true);
    try {
      const res = await runSimulation(contractId, baselineVars, scenariosInput);
      setSimulationResult(res);
      setRunning(false);
    } catch (err) {
      alert(`Simulation error: ${err}`);
      setRunning(false);
    }
  };

  const applyPreset = (presetName: string) => {
    if (presetName === 'supply_chain_crisis') {
      setBaselineVars({ ...baselineVars, delivery_delay_days: 35, payment_delay_days: 40 });
    } else if (presetName === 'high_volume') {
      setBaselineVars({ ...baselineVars, order_quantity: 2000, delivery_delay_days: 0 });
    } else if (presetName === 'sla_breach') {
      setBaselineVars({ ...baselineVars, sla_uptime_percent: 98.5 });
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header Banner */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Sliders className="w-6 h-6 text-indigo-600" />
            What-If Scenario Financial Simulator
          </h2>
          <p className="text-xs text-slate-500 font-medium mt-0.5">
            Simulate operational variables against Legal IR rules. Reuses the <strong>Deterministic Engine</strong> (Zero LLM Recalculation).
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => applyPreset('supply_chain_crisis')}
            className="px-3 py-1.5 rounded-xl bg-white hover:bg-rose-50 text-xs font-bold text-rose-700 border border-rose-200 shadow-xs transition-colors"
          >
            Preset: Supply Delay
          </button>
          <button
            onClick={() => applyPreset('high_volume')}
            className="px-3 py-1.5 rounded-xl bg-white hover:bg-emerald-50 text-xs font-bold text-emerald-700 border border-emerald-200 shadow-xs transition-colors"
          >
            Preset: High Volume
          </button>
          <button
            onClick={() => applyPreset('sla_breach')}
            className="px-3 py-1.5 rounded-xl bg-white hover:bg-amber-50 text-xs font-bold text-amber-700 border border-amber-200 shadow-xs transition-colors"
          >
            Preset: SLA Breach
          </button>
        </div>
      </div>

      {/* Simulator Inputs & Presets Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Baseline Input Panel */}
        <div className="glass-panel p-6 rounded-2xl border border-indigo-200/80 space-y-5 shadow-sm">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">1. Set Baseline Contract Variables</h3>

          <div className="space-y-4 text-xs">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-slate-700 font-semibold">Contract Order Value ($)</span>
                <span className="font-mono text-slate-900 font-bold">${baselineVars.contract_value.toLocaleString()}</span>
              </div>
              <input
                type="number"
                value={baselineVars.contract_value}
                onChange={(e) => setBaselineVars({ ...baselineVars, contract_value: parseFloat(e.target.value) || 0 })}
                className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-900 font-mono focus:bg-white focus:border-indigo-500 focus:outline-none"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-slate-700 font-semibold">Delivery Delay Days</span>
                <span className="font-mono text-rose-600 font-bold">{baselineVars.delivery_delay_days} Days</span>
              </div>
              <input
                type="range"
                min={0}
                max={60}
                value={baselineVars.delivery_delay_days}
                onChange={(e) => setBaselineVars({ ...baselineVars, delivery_delay_days: parseInt(e.target.value) })}
                className="w-full accent-indigo-600"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-slate-700 font-semibold">Payment Delay Days</span>
                <span className="font-mono text-amber-600 font-bold">{baselineVars.payment_delay_days} Days</span>
              </div>
              <input
                type="range"
                min={0}
                max={60}
                value={baselineVars.payment_delay_days}
                onChange={(e) => setBaselineVars({ ...baselineVars, payment_delay_days: parseInt(e.target.value) })}
                className="w-full accent-indigo-600"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-slate-700 font-semibold">Order Quantity (Units)</span>
                <span className="font-mono text-cyan-700 font-bold">{baselineVars.order_quantity.toLocaleString()} Units</span>
              </div>
              <input
                type="number"
                value={baselineVars.order_quantity}
                onChange={(e) => setBaselineVars({ ...baselineVars, order_quantity: parseInt(e.target.value) || 0 })}
                className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-900 font-mono focus:bg-white focus:border-indigo-500 focus:outline-none"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-slate-700 font-semibold">Achieved SLA Uptime (%)</span>
                <span className="font-mono text-emerald-600 font-bold">{baselineVars.sla_uptime_percent}%</span>
              </div>
              <input
                type="number"
                step="0.1"
                value={baselineVars.sla_uptime_percent}
                onChange={(e) => setBaselineVars({ ...baselineVars, sla_uptime_percent: parseFloat(e.target.value) || 0 })}
                className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-900 font-mono focus:bg-white focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <button
            onClick={handleRunSimulation}
            disabled={running}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-700 to-cyan-600 hover:from-indigo-500 hover:to-indigo-600 text-white font-bold text-xs shadow-lg shadow-indigo-600/25 transition-all disabled:opacity-50"
          >
            {running ? (
              <span>Running Simulation Engine...</span>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                <span>RUN WHAT-IF SIMULATION</span>
              </>
            )}
          </button>
        </div>

        {/* Right 2 Cols: Simulation Results & Matrix */}
        <div className="lg:col-span-2 space-y-6">
          {simulationResult ? (
            <>
              {/* Visual Bars Comparison Card */}
              <div className="glass-panel p-6 rounded-2xl border border-slate-200 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <BarChart2 className="w-4 h-4 text-indigo-600" />
                    Financial Impact Visual Comparison
                  </h3>
                  <span className="text-xs text-slate-500 font-mono font-semibold">Reused Deterministic Engine</span>
                </div>

                <div className="space-y-4 pt-2">
                  {simulationResult.visual_data.map((v, i) => (
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
                          style={{ width: `${Math.min(100, Math.max(8, (Math.abs(v.impact) / 100000) * 100))}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Scenario Matrix Table */}
              <ScenarioComparisonTable data={simulationResult} />
            </>
          ) : (
            <div className="glass-panel p-12 rounded-2xl border border-slate-200 text-center space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mx-auto text-indigo-600">
                <Sparkles className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-slate-900">Ready to Run What-If Simulations</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
                Adjust baseline operational variables on the left and click <strong>RUN WHAT-IF SIMULATION</strong> to generate an auditable financial impact comparison matrix.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
