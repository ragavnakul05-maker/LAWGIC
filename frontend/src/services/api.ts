import {
  ContractSummary, ContractDetail, RuleSummary, RuleExecutionOutput,
  SimulationResponse, DashboardMetrics, AlertItem,
  User, AuthResponse, LoginCredentials, RegisterCredentials, DemoUser,
  ContractSimulatorSchemaResponse, QuestionParseResponse, QuestionCalculateResponse,
  ContractSimulationComparisonResponse
} from '../types';

const envApiUrl = (import.meta as any).env?.VITE_API_URL;
const API_BASE = envApiUrl ? envApiUrl.replace(/\/$/, '') + '/api' : '/api';
const TOKEN_KEY = 'lawgic_jwt_token';

// ---------------------------------------------------------------------------
// Token Management
// ---------------------------------------------------------------------------

export function getAuthToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAuthToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch (err) {
    console.error('Failed to store auth token', err);
  }
}

export function removeAuthToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch (err) {
    console.error('Failed to remove auth token', err);
  }
}

// ---------------------------------------------------------------------------
// Authenticated Fetch Helper
// ---------------------------------------------------------------------------

export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  return fetch(url, { ...options, headers });
}

// ---------------------------------------------------------------------------
// Authentication Endpoints
// ---------------------------------------------------------------------------

export async function loginUser(credentials: LoginCredentials): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Authentication failed. Please check your credentials.');
  }

  const data: AuthResponse = await res.json();
  if (data.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

export async function registerUser(credentials: RegisterCredentials): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Registration failed. Please review your details.');
  }

  const data: AuthResponse = await res.json();
  if (data.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

export async function getCurrentUser(): Promise<User> {
  const res = await authFetch(`${API_BASE}/auth/me`);
  if (!res.ok) {
    removeAuthToken();
    throw new Error('Session expired or invalid. Please sign in again.');
  }
  return res.json();
}

export async function fetchDemoUsers(): Promise<DemoUser[]> {
  const res = await fetch(`${API_BASE}/auth/demo-users`);
  if (!res.ok) throw new Error('Failed to load demo accounts.');
  return res.json();
}

export async function requestPasswordReset(email: string): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to process password reset request.');
  }
  return data;
}

export async function verifyResetToken(token: string): Promise<{ valid: boolean; message: string }> {
  const cleanToken = (token || '').trim().replace(/\/$/, '');
  const res = await fetch(`${API_BASE}/auth/verify-reset-token?token=${encodeURIComponent(cleanToken)}`);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || 'Invalid or expired password reset token.');
  }
  return data;
}

export async function resetPassword(token: string, new_password: string): Promise<{ message: string }> {
  const cleanToken = (token || '').trim().replace(/\/$/, '');
  const res = await fetch(`${API_BASE}/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: cleanToken, new_password }),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to reset password.');
  }
  return data;
}

export async function changePassword(current_password: string, new_password: string): Promise<{ message: string }> {
  const res = await authFetch(`${API_BASE}/auth/change-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ current_password, new_password }),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to update password.');
  }
  return data;
}

// ---------------------------------------------------------------------------
// Business Operations Endpoints
// ---------------------------------------------------------------------------

export async function fetchDashboardSummary(): Promise<{
  metrics: DashboardMetrics;
  recent_contracts: ContractSummary[];
  alerts: AlertItem[];
}> {
  const res = await authFetch(`${API_BASE}/dashboard/summary`);
  if (!res.ok) throw new Error('Failed to fetch dashboard summary');
  return res.json();
}

export async function fetchContracts(): Promise<ContractSummary[]> {
  const res = await authFetch(`${API_BASE}/contracts`);
  if (!res.ok) throw new Error('Failed to fetch contracts');
  return res.json();
}

export async function fetchContractDetail(id: string): Promise<ContractDetail> {
  const res = await authFetch(`${API_BASE}/contracts/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch contract ${id}`);
  return res.json();
}

export async function uploadContract(file: File): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await authFetch(`${API_BASE}/contracts/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Upload failed');
  }
  return res.json();
}

export async function fetchRules(ruleType?: string, status?: string): Promise<RuleSummary[]> {
  const url = new URL(`${window.location.origin}${API_BASE}/rules`);
  if (ruleType) url.searchParams.append('rule_type', ruleType);
  if (status) url.searchParams.append('validation_status', status);

  const res = await authFetch(url.toString());
  if (!res.ok) throw new Error('Failed to fetch rules');
  return res.json();
}

export async function validateRule(ruleId: string): Promise<any> {
  const res = await authFetch(`${API_BASE}/rules/${ruleId}/validate`, { method: 'POST' });
  if (!res.ok) throw new Error('Validation failed');
  return res.json();
}

export async function executeContractRules(contractId: string, variables: Record<string, any>): Promise<RuleExecutionOutput> {
  const res = await authFetch(`${API_BASE}/rules/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contract_id: contractId, variables }),
  });
  if (!res.ok) throw new Error('Rule execution failed');
  return res.json();
}

export async function runSimulation(contractId: string, baselineVariables: Record<string, any>, scenarios: any[]): Promise<SimulationResponse> {
  const res = await authFetch(`${API_BASE}/simulations/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contract_id: contractId,
      baseline_variables: baselineVariables,
      scenarios: scenarios,
    }),
  });
  if (!res.ok) throw new Error('Simulation failed');
  return res.json();
}

export async function compareContractSimulation(
  contractId: string,
  whatIfVariables: Record<string, any>,
  originalVariables?: Record<string, any>
): Promise<ContractSimulationComparisonResponse> {
  const res = await authFetch(`${API_BASE}/simulations/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contract_id: contractId,
      original_variables: originalVariables,
      what_if_variables: whatIfVariables,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Contract simulation comparison failed');
  }
  return res.json();
}

export async function fetchContractSimulatorSchema(contractId: string): Promise<ContractSimulatorSchemaResponse> {
  const res = await authFetch(`${API_BASE}/simulations/contracts/${contractId}/parameters`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch contract simulator parameters');
  }
  return res.json();
}

export async function parseSimulationQuestion(contractId: string, question: string): Promise<QuestionParseResponse> {
  const res = await authFetch(`${API_BASE}/simulations/parse-question`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contract_id: contractId,
      question: question,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to parse simulation question');
  }
  return res.json();
}

export async function calculateSimulationQuestion(
  contractId: string,
  ruleCode: string,
  variables: Record<string, any>,
  assumptions?: string[]
): Promise<QuestionCalculateResponse> {
  const res = await authFetch(`${API_BASE}/simulations/calculate-question`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contract_id: contractId,
      rule_code: ruleCode,
      variables: variables,
      assumptions: assumptions || [],
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to calculate question simulation');
  }
  return res.json();
}


export async function fetchAuditExecutionTrail(executionId: string): Promise<any> {
  const res = await authFetch(`${API_BASE}/audit/executions/${executionId}`);
  if (!res.ok) throw new Error('Failed to fetch execution audit trail');
  return res.json();
}

export async function fetchAuditLogs(contractId?: string): Promise<any[]> {
  const url = new URL(`${window.location.origin}${API_BASE}/audit/logs`);
  if (contractId) url.searchParams.append('contract_id', contractId);

  const res = await authFetch(url.toString());
  if (!res.ok) throw new Error('Failed to fetch audit logs');
  return res.json();
}

export async function searchRAGStatutoryLaws(query: string): Promise<any> {
  const res = await authFetch(`${API_BASE}/rag/search?query=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error('RAG search failed');
  return res.json();
}

export async function fetchPenaltyBreakdown(): Promise<any> {
  const res = await authFetch(`${API_BASE}/dashboard/breakdown`);
  if (!res.ok) throw new Error('Failed to fetch penalty breakdown');
  return res.json();
}

export async function exportAuditExecution(executionId: string, format: 'html' | 'csv' | 'json'): Promise<void> {
  const res = await authFetch(`${API_BASE}/audit/executions/${executionId}/export?format=${format}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to export audit execution');
  }

  if (format === 'html') {
    const htmlText = await res.text();
    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.document.write(htmlText);
      printWindow.document.close();
    }
  } else {
    const blob = await res.blob();
    const disposition = res.headers.get('content-disposition');
    let filename = `audit_dossier_${executionId}.${format}`;
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename="?([^"]+)"?/);
      if (match && match[1]) filename = match[1];
    }
    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(blobUrl);
  }
}

export async function exportSimulationReport(comparisonData: any, format: 'html' | 'csv' | 'json'): Promise<void> {
  const res = await authFetch(`${API_BASE}/simulations/export?format=${format}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(comparisonData),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to export simulation report');
  }

  if (format === 'html') {
    const htmlText = await res.text();
    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.document.write(htmlText);
      printWindow.document.close();
    }
  } else {
    const blob = await res.blob();
    const disposition = res.headers.get('content-disposition');
    let filename = `simulation_report.${format}`;
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename="?([^"]+)"?/);
      if (match && match[1]) filename = match[1];
    }
    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(blobUrl);
  }
}

