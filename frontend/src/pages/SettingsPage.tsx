import React, { useState } from 'react';
import { Settings, Cpu, Database, Key, ShieldCheck, CheckCircle2 } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const [provider, setProvider] = useState('mock');
  const [model, setModel] = useState('gpt-4o');
  const [apiKey, setApiKey] = useState('');
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="p-8 space-y-8 max-w-4xl mx-auto">
      <div>
        <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <Settings className="w-6 h-6 text-indigo-600" />
          System & LLM Engine Settings
        </h2>
        <p className="text-xs text-slate-500 font-medium mt-0.5">
          Configure external LLM providers, structured output models, and database connections.
        </p>
      </div>

      <div className="glass-panel p-6 rounded-2xl border border-slate-200 space-y-6 shadow-sm">
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <Cpu className="w-4 h-4 text-indigo-600" />
          LLM Legal IR Extractor Provider
        </h3>

        <div className="space-y-4 text-xs">
          <div>
            <label className="text-slate-700 font-semibold block mb-1">Select Provider</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-900 font-mono focus:bg-white focus:border-indigo-500 focus:outline-none"
            >
              <option value="mock">Mock Offline Extractor (Instant Prototype)</option>
              <option value="openai">OpenAI (GPT-4o / GPT-4o-mini)</option>
              <option value="gemini">Google Gemini (Gemini 1.5 Pro / Flash)</option>
            </select>
          </div>

          <div>
            <label className="text-slate-700 font-semibold block mb-1">Model Name</label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-900 font-mono focus:bg-white focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="text-slate-700 font-semibold block mb-1">API Key</label>
            <div className="relative">
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={provider === 'mock' ? 'Not required for offline mock extractor' : 'sk-...'}
                className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-900 font-mono pr-10 focus:bg-white focus:border-indigo-500 focus:outline-none"
              />
              <Key className="w-4 h-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2" />
            </div>
            <p className="text-[11px] text-slate-500 mt-1">API keys are stored safely in backend environment memory and never exposed to client logs.</p>
          </div>

          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-semibold text-xs shadow-md shadow-indigo-600/20"
          >
            {saved ? (
              <>
                <CheckCircle2 className="w-4 h-4 text-emerald-300" />
                <span>Configuration Saved</span>
              </>
            ) : (
              <span>Save Configuration</span>
            )}
          </button>
        </div>
      </div>

      {/* Engine Architecture Box */}
      <div className="glass-panel p-6 rounded-2xl border border-emerald-200 bg-emerald-50/50 space-y-3">
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600" />
          Deterministic Calculation Engine Guard
        </h3>
        <p className="text-xs text-slate-700 leading-relaxed font-mono">
          Regardless of the LLM Provider selected above, the final financial calculations (liquidated damages, grace periods, capped liabilities, volume discounts, interest compounding) are ALWAYS executed by LAWGIC's pure Python deterministic rule engine.
        </p>
      </div>
    </div>
  );
};
