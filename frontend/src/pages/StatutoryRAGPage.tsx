import React, { useState } from 'react';
import { FileCheck2, Search, BookOpen, ExternalLink, ShieldCheck } from 'lucide-react';
import { searchRAGStatutoryLaws } from '../services/api';

export const StatutoryRAGPage: React.FC = () => {
  const [query, setQuery] = useState('liquidated damages penalty UCC 2-718');
  const [results, setResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);

  const handleSearch = async () => {
    setSearching(true);
    try {
      const data = await searchRAGStatutoryLaws(query);
      setResults(data.external_legal_references || []);
      setSearching(false);
    } catch (err) {
      alert(`Search error: ${err}`);
      setSearching(false);
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <FileCheck2 className="w-6 h-6 text-indigo-600" />
          Statutory RAG Legal Reference Hub
        </h2>
        <p className="text-xs text-slate-500 font-medium mt-0.5">
          Search external statutory laws, UCC commercial codes, and legal precedents to support contract interpretation.
        </p>
      </div>

      {/* RAG Separation Warning Box */}
      <div className="p-4 rounded-xl bg-indigo-50 border border-indigo-200 text-xs text-indigo-900 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-indigo-600 shrink-0" />
          <span>
            <strong>Architectural Guarantee:</strong> External legal statutory references retrieved here do NOT overwrite internal contract clause logic.
          </span>
        </div>
        <span className="px-2 py-0.5 rounded bg-indigo-100 text-indigo-700 text-[10px] font-mono font-bold">RAG Isolated</span>
      </div>

      {/* Search Input Bar */}
      <div className="glass-panel p-4 rounded-2xl border border-slate-200 flex items-center gap-3 shadow-xs">
        <Search className="w-5 h-5 text-slate-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter legal topic, statute code, or query (e.g. Prompt Payment Act, UCC 2-718, SLA metrics)..."
          className="flex-1 bg-transparent text-sm text-slate-900 placeholder-slate-400 focus:outline-none font-sans"
        />
        <button
          onClick={handleSearch}
          disabled={searching}
          className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-semibold text-xs transition-all shadow-md shadow-indigo-600/20"
        >
          {searching ? 'Searching...' : 'Search Statutory Laws'}
        </button>
      </div>

      {/* Results Grid */}
      <div className="space-y-4">
        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">External Legal Precedents & References</h3>

        {results.length === 0 ? (
          <div className="glass-panel p-8 rounded-2xl text-center text-xs text-slate-500">
            Enter a query above to retrieve statutory legal references from vector knowledge base.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {results.map((doc: any, i: number) => (
              <div key={i} className="glass-panel p-6 rounded-2xl border border-slate-200 space-y-3 relative overflow-hidden">
                <div className="absolute top-3 right-3 px-2 py-0.5 rounded bg-cyan-100 text-cyan-800 text-[10px] font-mono font-bold border border-cyan-200">
                  EXTERNAL LEGAL REFERENCE
                </div>

                <div className="flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-indigo-600" />
                  <span className="font-mono text-xs text-indigo-700 font-bold">{doc.statute_code}</span>
                  <span className="text-[11px] text-slate-500">({doc.jurisdiction})</span>
                </div>

                <h4 className="font-bold text-slate-900 text-sm">{doc.title}</h4>

                <p className="text-xs text-slate-700 leading-relaxed font-serif italic bg-slate-50 p-3 rounded-xl border border-slate-200">
                  "{doc.content}"
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
