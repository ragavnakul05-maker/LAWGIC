import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoginPage } from './pages/LoginPage';
import { Navbar } from './components/Navbar';
import { Header } from './components/Header';
import { DashboardPage } from './pages/DashboardPage';
import { ContractsPage } from './pages/ContractsPage';
import { ContractDetailPage } from './pages/ContractDetailPage';
import { RulesPage } from './pages/RulesPage';
import { SimulatorPage } from './pages/SimulatorPage';
import { AuditPage } from './pages/AuditPage';
import { StatutoryRAGPage } from './pages/StatutoryRAGPage';
import { SettingsPage } from './pages/SettingsPage';
import { Zap } from 'lucide-react';

function MainAppContent() {
  const { isAuthenticated, isLoading } = useAuth();
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [selectedContractId, setSelectedContractId] = useState<string>('DEMO-CONTRACT-001');

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center space-y-4">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-indigo-500 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-xl shadow-indigo-500/30 animate-pulse">
          <Zap className="w-7 h-7 text-white fill-current" />
        </div>
        <div className="flex items-center gap-2 text-indigo-400 font-mono text-xs">
          <div className="w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
          <span>Verifying LAWGIC session...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  const handleNavigate = (tab: string, contractId?: string) => {
    if (contractId) setSelectedContractId(contractId);
    setActiveTab(tab);
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <DashboardPage onNavigate={handleNavigate} />;
      case 'contracts':
        return (
          <ContractsPage
            onSelectContract={(id) => {
              setSelectedContractId(id);
              setActiveTab('contract_detail');
            }}
          />
        );
      case 'contract_detail':
        return (
          <ContractDetailPage
            contractId={selectedContractId}
            onBack={() => setActiveTab('contracts')}
            onSimulate={(id) => {
              setSelectedContractId(id);
              setActiveTab('simulator');
            }}
          />
        );
      case 'rules':
        return <RulesPage />;
      case 'simulator':
        return <SimulatorPage defaultContractId={selectedContractId} />;
      case 'audit':
        return <AuditPage />;
      case 'rag':
        return <StatutoryRAGPage />;
      case 'settings':
        return <SettingsPage />;
      default:
        return <DashboardPage onNavigate={handleNavigate} />;
    }
  };

  const getPageTitle = () => {
    switch (activeTab) {
      case 'dashboard': return 'Executive Contract Intelligence Dashboard';
      case 'contracts': return 'Contract Document Management';
      case 'contract_detail': return 'Interactive Contract Analysis Studio';
      case 'rules': return 'Structured Legal IR Repository';
      case 'simulator': return 'What-If Financial Simulator';
      case 'audit': return 'Audit & Traceability Hub';
      case 'rag': return 'Statutory Legal Reference RAG';
      case 'settings': return 'System Settings & LLM Configuration';
      default: return 'LAWGIC Dashboard';
    }
  };

  return (
    <div className="relative min-h-screen bg-slate-50 text-slate-800 font-sans overflow-x-hidden selection:bg-indigo-500 selection:text-white">
      {/* Realistic Animated Floating Ambient Orbs & Subtle Grid Mesh */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute -top-32 -left-32 w-[32rem] h-[32rem] bg-indigo-300/40 rounded-full blur-3xl animate-orb-1" />
        <div className="absolute top-1/4 -right-32 w-[30rem] h-[30rem] bg-cyan-300/35 rounded-full blur-3xl animate-orb-2" />
        <div className="absolute -bottom-32 left-1/3 w-[36rem] h-[36rem] bg-violet-300/30 rounded-full blur-3xl animate-orb-3" />
        <div className="absolute inset-0 bg-[radial-gradient(#cbd5e1_1px,transparent_1px)] [background-size:28px_28px] opacity-40" />
      </div>

      <div className="relative z-10 flex min-h-screen">
        <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />
        <div className="flex-1 flex flex-col min-w-0">
          <Header
            title={getPageTitle()}
            subtitle="Contract -> Legal IR -> Validation -> Deterministic Math"
            onQuickSimulate={() => setActiveTab('simulator')}
          />
          <main className="flex-1 overflow-y-auto">
            {renderContent()}
          </main>
        </div>
      </div>
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <MainAppContent />
    </AuthProvider>
  );
}

export default App;
