import React, { useEffect, useState } from 'react';
import { Upload, FileText, CheckCircle2, ArrowRight, ShieldCheck, Cpu } from 'lucide-react';
import { fetchContracts, uploadContract } from '../services/api';
import { ContractSummary } from '../types';

interface ContractsPageProps {
  onSelectContract: (id: string) => void;
}

export const ContractsPage: React.FC<ContractsPageProps> = ({ onSelectContract }) => {
  const [contracts, setContracts] = useState<ContractSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const loadContracts = () => {
    fetchContracts()
      .then((data) => {
        setContracts(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadContracts();
  }, []);

  const handleFileUpload = async (file: File) => {
    setUploading(true);
    try {
      const res = await uploadContract(file);
      setUploading(false);
      loadContracts();
      if (res.contract_id) {
        onSelectContract(res.contract_id);
      }
    } catch (err) {
      alert(`Upload error: ${err}`);
      setUploading(false);
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header Title */}
      <div>
        <h2 className="text-xl font-bold text-slate-900">Contract Document Repository</h2>
        <p className="text-xs text-slate-500 font-medium mt-0.5">
          Upload PDF, DOCX, or scanned contracts for automated section segmentation and Legal IR extraction.
        </p>
      </div>

      {/* Upload Zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFileUpload(e.dataTransfer.files[0]);
          }
        }}
        className={`glass-panel p-10 rounded-2xl border-2 border-dashed transition-all text-center space-y-4 ${
          dragActive ? 'border-indigo-500 bg-indigo-50/60' : 'border-slate-300 hover:border-slate-400 bg-white/70'
        }`}
      >
        <div className="w-14 h-14 rounded-2xl bg-indigo-50 border border-indigo-200 flex items-center justify-center mx-auto text-indigo-600 shadow-md shadow-indigo-500/10">
          <Upload className="w-7 h-7" />
        </div>

        <div>
          <h3 className="text-base font-bold text-slate-900">Drag and drop your contract file here</h3>
          <p className="text-xs text-slate-500 mt-1">Supports PDF, DOCX, and TXT agreements (page & section numbers preserved)</p>
        </div>

        <div>
          <label className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-semibold text-xs cursor-pointer shadow-md shadow-indigo-600/20 transition-all">
            <span>Browse Files</span>
            <input
              type="file"
              accept=".pdf,.docx,.doc,.txt"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleFileUpload(e.target.files[0]);
                }
              }}
              className="hidden"
            />
          </label>
        </div>

        {uploading && (
          <div className="flex items-center justify-center gap-2 text-xs text-indigo-600 font-semibold pt-2">
            <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
            Parsing pages, segmenting clauses & generating Legal IR...
          </div>
        )}
      </div>

      {/* Contracts Grid */}
      <div className="space-y-4">
        <h3 className="text-base font-bold text-slate-900">Managed Agreements ({contracts.length})</h3>

        {loading ? (
          <div className="p-8 text-center text-xs text-slate-500">Loading contracts...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {contracts.map((c) => (
              <div key={c.id} className="glass-panel glass-panel-hover p-6 rounded-2xl space-y-4 border border-slate-200">
                <div className="flex items-start justify-between">
                  <div className="p-3 rounded-xl bg-indigo-50 border border-indigo-100 text-indigo-600">
                    <FileText className="w-6 h-6" />
                  </div>
                  <span className="px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-700 border border-emerald-200 font-mono text-[10px] font-bold">
                    {c.status}
                  </span>
                </div>

                <div>
                  <h4 className="font-bold text-slate-900 text-sm line-clamp-1">{c.title}</h4>
                  <p className="text-xs text-slate-500 font-mono mt-0.5">{c.filename}</p>
                </div>

                <div className="grid grid-cols-3 gap-2 py-2 border-y border-slate-200 text-xs">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-bold block">Pages</span>
                    <span className="font-mono text-slate-800 font-bold">{c.page_count}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-bold block">Clauses</span>
                    <span className="font-mono text-cyan-700 font-bold">{c.clauses_count}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-bold block">Legal IR</span>
                    <span className="font-mono text-indigo-600 font-bold">{c.rules_count} Rules</span>
                  </div>
                </div>

                <button
                  onClick={() => onSelectContract(c.id)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold text-xs transition-colors border border-indigo-200"
                >
                  <span>Open Analysis Studio</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
