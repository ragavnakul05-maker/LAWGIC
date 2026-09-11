from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field, ConfigDict
from app.core.database import Base

# ==========================================
# SQLALCHEMY ORM MODELS
# ==========================================

class ContractModel(Base):
    __tablename__ = "contracts"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    page_count = Column(Integer, default=1)
    status = Column(String, default="PARSED") # UPLOADED, PARSED, ANALYZED
    created_at = Column(DateTime, default=datetime.utcnow)

    pages = relationship("ContractPageModel", back_populates="contract", cascade="all, delete-orphan")
    clauses = relationship("ClauseModel", back_populates="contract", cascade="all, delete-orphan")
    rules = relationship("RuleModel", back_populates="contract", cascade="all, delete-orphan")
    executions = relationship("ExecutionModel", back_populates="contract", cascade="all, delete-orphan")

class ContractPageModel(Base):
    __tablename__ = "contract_pages"

    id = Column(String, primary_key=True, index=True)
    contract_id = Column(String, ForeignKey("contracts.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    text_content = Column(Text, nullable=False)

    contract = relationship("ContractModel", back_populates="pages")

class ClauseModel(Base):
    __tablename__ = "clauses"

    id = Column(String, primary_key=True, index=True)
    contract_id = Column(String, ForeignKey("contracts.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    section_number = Column(String, nullable=True)
    clause_number = Column(String, nullable=True)
    title = Column(String, nullable=True)
    original_text = Column(Text, nullable=False)
    clause_type = Column(String, nullable=False) # late_payment_interest, delivery_delay_penalty, volume_discount, sla_penalty, etc.

    contract = relationship("ContractModel", back_populates="clauses")
    rules = relationship("RuleModel", back_populates="clause", cascade="all, delete-orphan")

class RuleModel(Base):
    __tablename__ = "rules"

    id = Column(String, primary_key=True, index=True)
    contract_id = Column(String, ForeignKey("contracts.id"), nullable=False)
    clause_id = Column(String, ForeignKey("clauses.id"), nullable=False)
    rule_code = Column(String, nullable=False) # e.g. R001
    rule_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    ir_json = Column(JSON, nullable=False) # Machine readable Legal IR
    validation_status = Column(String, default="VALID") # VALID, NEEDS_REVIEW, INVALID
    review_notes = Column(Text, nullable=True)
    human_explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    contract = relationship("ContractModel", back_populates="rules")
    clause = relationship("ClauseModel", back_populates="rules")

class ExecutionModel(Base):
    __tablename__ = "executions"

    id = Column(String, primary_key=True, index=True)
    contract_id = Column(String, ForeignKey("contracts.id"), nullable=False)
    scenario_name = Column(String, default="Baseline Execution")
    input_variables = Column(JSON, nullable=False)
    financial_impact = Column(Float, default=0.0)
    summary_result = Column(JSON, nullable=False)
    executed_at = Column(DateTime, default=datetime.utcnow)

    contract = relationship("ContractModel", back_populates="executions")
    steps = relationship("ExecutionStepModel", back_populates="execution", cascade="all, delete-orphan")

class ExecutionStepModel(Base):
    __tablename__ = "execution_steps"

    id = Column(String, primary_key=True, index=True)
    execution_id = Column(String, ForeignKey("executions.id"), nullable=False)
    step_number = Column(Integer, nullable=False)
    rule_code = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    formula = Column(String, nullable=True)
    subtotal = Column(Float, default=0.0)
    source_clause_id = Column(String, nullable=True)

    execution = relationship("ExecutionModel", back_populates="steps")

class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, index=True)
    contract_id = Column(String, nullable=False)
    action = Column(String, nullable=False) # PARSE, EXTRACT_IR, VALIDATE, EXECUTE, SIMULATE
    details = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class LegalDocumentModel(Base):
    __tablename__ = "legal_documents"

    id = Column(String, primary_key=True, index=True)
    jurisdiction = Column(String, nullable=False)
    title = Column(String, nullable=False)
    statute_code = Column(String, nullable=True)
    text_content = Column(Text, nullable=False)

class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default="Senior Legal Counsel")
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==========================================
# PYDANTIC SCHEMAS (LEGAL IR & API SCHEMAS)
# ==========================================

class RuleSourceInfo(BaseModel):
    page: int
    section: Optional[str] = None
    clause_number: Optional[str] = None
    text: str

class RuleCondition(BaseModel):
    variable: str
    operator: str # >, >=, <, <=, ==, !=
    value: Any
    unit: Optional[str] = None

class RuleAction(BaseModel):
    type: str # interest, penalty, discount, escalation, sla_deduction
    rate: Optional[float] = None
    amount: Optional[float] = None
    period: Optional[str] = None # month, week, day, flat
    grace_period_days: Optional[int] = 0
    base_variable: Optional[str] = "contract_value"
    description: Optional[str] = None

class RuleCaps(BaseModel):
    max_amount: Optional[float] = None
    max_percentage: Optional[float] = None # e.g. 0.10 for 10%
    min_amount: Optional[float] = None

class LegalIR(BaseModel):
    rule_id: str
    type: str # late_payment_interest, delivery_delay_penalty, volume_discount, sla_penalty, price_escalation
    title: str
    source: RuleSourceInfo
    conditions: List[RuleCondition]
    actions: List[RuleAction]
    caps: Optional[RuleCaps] = Field(default_factory=RuleCaps)
    ambiguity_flag: bool = False
    review_reason: Optional[str] = None

# Validation Schema
class RuleValidationResult(BaseModel):
    rule_id: str
    status: str # VALID, NEEDS_REVIEW, INVALID
    issues: List[str]
    missing_variables: List[str]
    human_summary: str

# Rule Execution Request & Output
class RuleExecutionInput(BaseModel):
    contract_id: str
    variables: Dict[str, Any] # e.g. {"contract_value": 1000000, "payment_delay_days": 35, "delivery_delay_days": 24, "order_quantity": 1200, "sla_uptime_percent": 99.1}

class ExecutionStepResult(BaseModel):
    step_number: int
    rule_code: str
    title: str
    description: str
    formula: Optional[str] = None
    subtotal: float
    source_clause: RuleSourceInfo

class RuleExecutionOutput(BaseModel):
    execution_id: str
    contract_id: str
    total_financial_impact: float
    summary: Dict[str, Any]
    calculation_steps: List[ExecutionStepResult]
    applied_rules: List[str]
    human_explanation: str
    executed_at: str

# What-If Simulation Schemas
class ScenarioInput(BaseModel):
    scenario_name: str
    variable_overrides: Dict[str, Any]

class SimulationRequest(BaseModel):
    contract_id: str
    baseline_variables: Dict[str, Any]
    scenarios: List[ScenarioInput]

class ScenarioComparisonItem(BaseModel):
    scenario_name: str
    variables: Dict[str, Any]
    financial_impact: float
    difference_from_baseline: float
    percentage_change: float
    calculation_summary: str

class SimulationResponse(BaseModel):
    contract_id: str
    baseline: ScenarioComparisonItem
    scenarios: List[ScenarioComparisonItem]
    visual_data: List[Dict[str, Any]]

# ==========================================
# AUTHENTICATION SCHEMAS
# ==========================================
class UserRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    role: Optional[str] = "Senior Legal Counsel"

class UserLoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
