export interface RuleSourceInfo {
  page: number;
  section?: string;
  clause_number?: string;
  text: string;
}

export interface RuleCondition {
  variable: string;
  operator: string;
  value: any;
  unit?: string;
}

export interface RuleAction {
  type: string;
  rate?: number;
  amount?: number;
  period?: string;
  grace_period_days?: number;
  base_variable?: string;
  description?: string;
}

export interface RuleCaps {
  max_amount?: number;
  max_percentage?: number;
  min_amount?: number;
}

export interface LegalIR {
  rule_id: string;
  type: string;
  title: string;
  source: RuleSourceInfo;
  conditions: RuleCondition[];
  actions: RuleAction[];
  caps?: RuleCaps;
  ambiguity_flag?: boolean;
  review_reason?: string;
}

export interface Clause {
  id: string;
  page_number: number;
  section_number: string;
  title: string;
  original_text: string;
  clause_type: string;
  rule?: {
    id: string;
    rule_code: string;
    title: string;
    ir_json: LegalIR;
    validation_status: 'VALID' | 'NEEDS_REVIEW' | 'INVALID';
    review_notes?: string;
    human_explanation?: string;
  };
}

export interface ContractDetail {
  id: string;
  title: string;
  filename: string;
  file_type: string;
  page_count: number;
  status: string;
  created_at: string;
  pages: { page_number: number; text_content: string }[];
  clauses: Clause[];
}

export interface ContractSummary {
  id: string;
  title: string;
  filename: string;
  file_type: string;
  page_count: number;
  clauses_count: number;
  rules_count: number;
  status: string;
  created_at: string;
}

export interface RuleSummary {
  id: string;
  contract_id: string;
  clause_id: string;
  rule_code: string;
  rule_type: string;
  title: string;
  ir_json: LegalIR;
  validation_status: 'VALID' | 'NEEDS_REVIEW' | 'INVALID';
  review_notes?: string;
  human_explanation?: string;
  created_at: string;
  source: {
    page: number;
    section: string;
    clause_text: string;
  };
}

export interface ExecutionStepResult {
  step_number: number;
  rule_code: string;
  title: string;
  description: string;
  formula?: string;
  subtotal: number;
  source_clause: RuleSourceInfo;
}

export interface RuleExecutionOutput {
  execution_id: string;
  contract_id: string;
  total_financial_impact: number;
  summary: Record<string, any>;
  calculation_steps: ExecutionStepResult[];
  applied_rules: string[];
  human_explanation: string;
  executed_at: string;
}

export interface ScenarioComparisonItem {
  scenario_name: string;
  variables: Record<string, any>;
  financial_impact: number;
  difference_from_baseline: number;
  percentage_change: number;
  calculation_summary: string;
}

export interface SimulationResponse {
  contract_id: string;
  baseline: ScenarioComparisonItem;
  scenarios: ScenarioComparisonItem[];
  visual_data: Record<string, any>[];
}

export interface ScenarioInput {
  name: string;
  variable_overrides: Record<string, any>;
}

export interface ContractParameterItem {
  variable_name: string;
  label: string;
  unit?: string;
  default_value: number;
  description: string;
  rule_code: string;
  rule_title: string;
  rule_type: string;
  threshold?: number;
  rate_or_amount?: string;
  cap?: string;
  source_clause: RuleSourceInfo;
  clause_id?: string;
  input_type?: string;
  min_value?: number;
  max_value?: number;
  step?: number;
}

export interface ContractSimulatorSchemaResponse {
  contract_id: string;
  contract_title: string;
  parameters: ContractParameterItem[];
  baseline_variables: Record<string, any>;
  suggested_presets: ScenarioInput[];
  rules_count: number;
}

export interface ContractRuleComparisonResult {
  rule_code: string;
  rule_title: string;
  rule_type: string;
  clause_id?: string;
  source_clause?: RuleSourceInfo;
  parameter_name: string;
  parameter_label: string;
  unit: string;
  original_parameter_value: any;
  what_if_parameter_value: any;
  original_result: number;
  what_if_result: number;
  difference: number;
  formula: string;
  calculation_breakdown: string;
  reason: string;
  cap_applied: boolean;
  cap_detail: string;
  decompiled_explanation: string;
  applied_conditions: string[];
}

export interface ContractSimulationCompareRequest {
  contract_id: string;
  original_variables?: Record<string, any>;
  what_if_variables: Record<string, any>;
}

export interface ContractSimulationComparisonResponse {
  contract_id: string;
  contract_title: string;
  original_total_impact: number;
  what_if_total_impact: number;
  net_difference: number;
  rules_evaluated_count: number;
  rules_triggered_count: number;
  rules: ContractRuleComparisonResult[];
  overall_human_explanation: string;
  audit_trace_id: string;
  user_id?: string;
  user_name?: string;
  executed_at: string;
}

export interface MatchedRuleInfo {
  rule_code: string;
  title: string;
  rule_type: string;
  source: RuleSourceInfo;
  description?: string;
}

export interface QuestionParseResponse {
  contract_id: string;
  question: string;
  status: 'READY' | 'NEEDS_CONFIRMATION';
  matched_rule: MatchedRuleInfo;
  extracted_parameters: Record<string, any>;
  missing_parameters: string[];
  suggested_values: Record<string, any>;
  assumptions: string[];
  confirmation_prompt: string;
}

export interface QuestionCalculateResponse {
  contract_id: string;
  rule_code: string;
  total_financial_impact: number;
  formula?: string;
  calculation_steps: ExecutionStepResult[];
  applied_rules: string[];
  human_explanation: string;
  source_clause?: RuleSourceInfo;
  assumptions: string[];
  audit_trace_id: string;
}

export interface DashboardMetrics {
  total_contracts: number;
  clauses_extracted: number;
  active_rules: number;
  pending_reviews: number;
  potential_penalties: number;
  potential_discounts: number;
}

export interface AlertItem {
  id: string;
  type: 'WARNING' | 'DANGER' | 'SUCCESS' | 'INFO';
  title: string;
  message: string;
  contract_id: string;
  rule_code: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterCredentials {
  email: string;
  password: string;
  full_name: string;
  role?: string;
}

export interface DemoUser {
  email: string;
  password: string;
  full_name: string;
  role: string;
  description: string;
}

