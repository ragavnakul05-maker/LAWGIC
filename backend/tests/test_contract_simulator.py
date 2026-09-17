import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db, migrate_db
from app.core.security import hash_password
from app.main import app
from app.models.schemas import (
    UserModel, ContractModel, RuleModel, LegalIR,
    RuleSourceInfo, RuleCondition, RuleAction, RuleCaps,
    ExecutionModel, ExecutionStepModel, AuditLogModel
)
from app.services.simulation_engine import SimulationEngine
from app.services.question_parser_service import QuestionParserService
from app.services.deterministic_rule_engine import DeterministicRuleEngine

# In-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    migrate_db(bind_engine=test_engine)
    db = TestingSessionLocal()

    user = UserModel(
        id="USER-SIM-TEST",
        email="sim_test@lawgic.ai",
        full_name="Sim Test Lawyer",
        role="Counsel",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db.add(user)

    contract = ContractModel(
        id="CONTRACT-SIM-001",
        user_id="USER-SIM-TEST",
        title="Dynamic Logistics Agreement",
        filename="Logistics_Agreement.pdf",
        file_type="PDF",
        file_path="uploads/contracts/logistics.pdf",
        page_count=5,
        status="PROCESSED",
    )
    db.add(contract)

    # 1. Delivery delay penalty rule
    delivery_rule = LegalIR(
        rule_id="RULE-DELIV-01",
        type="delivery_delay_penalty",
        title="Delivery Delay Liquidated Damages",
        source=RuleSourceInfo(page=3, section="8.2", clause_number="8.2.1", text="0.5% per day delay after 15 days"),
        conditions=[RuleCondition(variable="delivery_delay_days", operator=">", value=15)],
        actions=[RuleAction(type="penalty", rate=0.005, period="day", grace_period_days=15, base_variable="contract_value")],
        caps=RuleCaps(max_percentage=0.10)
    )
    db.add(RuleModel(
        id="R-DB-01",
        contract_id="CONTRACT-SIM-001",
        clause_id="C-DB-01",
        rule_code="RULE-DELIV-01",
        rule_type="delivery_delay_penalty",
        title="Delivery Delay Liquidated Damages",
        ir_json=delivery_rule.model_dump(),
        validation_status="VALID"
    ))

    # 2. Late payment interest rule
    interest_rule = LegalIR(
        rule_id="RULE-INT-02",
        type="late_payment_interest",
        title="Overdue Invoice Interest",
        source=RuleSourceInfo(page=4, section="10.1", clause_number="10.1", text="1.5% per month after 30 days"),
        conditions=[RuleCondition(variable="payment_delay_days", operator=">", value=30)],
        actions=[RuleAction(type="interest", rate=0.015, period="month", grace_period_days=30, base_variable="invoice_amount")],
        caps=RuleCaps(max_percentage=0.15)
    )
    db.add(RuleModel(
        id="R-DB-02",
        contract_id="CONTRACT-SIM-001",
        clause_id="C-DB-02",
        rule_code="RULE-INT-02",
        rule_type="late_payment_interest",
        title="Overdue Invoice Interest",
        ir_json=interest_rule.model_dump(),
        validation_status="VALID"
    ))

    # 3. Volume discount rule
    discount_rule = LegalIR(
        rule_id="RULE-VOL-03",
        type="volume_discount",
        title="Tier 2 Bulk Purchase Rebate",
        source=RuleSourceInfo(page=2, section="4.3", clause_number="4.3", text="5% discount on orders exceeding 2000 units"),
        conditions=[RuleCondition(variable="order_quantity", operator=">", value=2000)],
        actions=[RuleAction(type="discount", rate=0.05, base_variable="contract_value")],
        caps=RuleCaps()
    )
    db.add(RuleModel(
        id="R-DB-03",
        contract_id="CONTRACT-SIM-001",
        clause_id="C-DB-03",
        rule_code="RULE-VOL-03",
        rule_type="volume_discount",
        title="Tier 2 Bulk Purchase Rebate",
        ir_json=discount_rule.model_dump(),
        validation_status="VALID"
    ))

    db.commit()
    db.close()


def get_auth_client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    login_resp = client.post("/api/auth/login", json={
        "email": "sim_test@lawgic.ai",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    return client


# ============================================================================
# 1. Parameter Discovery Unit Tests
# ============================================================================

def test_get_contract_simulator_schema_dynamic_parameters():
    """Verify parameters are discovered dynamically from Legal IR without hardcoding."""
    rules = [
        LegalIR(
            rule_id="RULE-DELIV-01",
            type="delivery_delay_penalty",
            title="Delivery Delay Liquidated Damages",
            source=RuleSourceInfo(page=3, section="8.2", text="0.5% per day after 15 days"),
            conditions=[RuleCondition(variable="delivery_delay_days", operator=">", value=15)],
            actions=[RuleAction(type="penalty", rate=0.005, period="day", grace_period_days=15, base_variable="contract_value")],
            caps=RuleCaps(max_percentage=0.10)
        )
    ]

    schema = SimulationEngine.get_contract_simulator_schema(
        contract_id="TEST-001",
        contract_title="Logistics Agreement",
        rules=rules
    )

    assert schema.contract_id == "TEST-001"
    assert schema.contract_title == "Logistics Agreement"
    assert schema.rules_count == 1

    var_names = [p.variable_name for p in schema.parameters]
    assert "delivery_delay_days" in var_names
    assert "contract_value" in var_names

    # Check delivery delay parameter details
    delivery_param = next(p for p in schema.parameters if p.variable_name == "delivery_delay_days")
    assert delivery_param.threshold == 15.0
    assert "0.5%" in delivery_param.rate_or_amount
    assert "10.0%" in delivery_param.cap
    assert delivery_param.source_clause.section == "8.2"
    assert delivery_param.source_clause.page == 3

    # Check presets
    assert len(schema.suggested_presets) > 0


# ============================================================================
# 2. Question Parser Service Unit Tests
# ============================================================================

def test_question_parser_delivery_delay():
    """Verify question parser extracts delivery delay and flags missing contract value."""
    rules = [
        LegalIR(
            rule_id="RULE-DELIV-01",
            type="delivery_delay_penalty",
            title="Delivery Delay",
            source=RuleSourceInfo(page=3, section="8.2", text="0.5% per day delay"),
            conditions=[RuleCondition(variable="delivery_delay_days", operator=">", value=15)],
            actions=[RuleAction(type="penalty", rate=0.005, grace_period_days=15, base_variable="contract_value")],
            caps=RuleCaps(max_percentage=0.10)
        )
    ]

    res = QuestionParserService.parse_simulation_question(
        contract_id="CONTRACT-001",
        question="What if delivery is delayed by 20 days?",
        rules=rules
    )

    assert res.matched_rule.rule_code == "RULE-DELIV-01"
    assert res.extracted_parameters.get("delivery_delay_days") == 20
    assert "contract_value" in res.missing_parameters
    assert res.suggested_values.get("contract_value") == 1000000.0
    assert res.status == "NEEDS_CONFIRMATION"
    assert "Section 8.2" in res.confirmation_prompt
    assert "Page 3" in res.confirmation_prompt


def test_question_parser_payment_delay_with_amount():
    """Verify question parser extracts invoice amount and payment delay together."""
    rules = [
        LegalIR(
            rule_id="RULE-INT-02",
            type="late_payment_interest",
            title="Late Payment Interest",
            source=RuleSourceInfo(page=4, section="10.1", text="1.5% per month"),
            conditions=[RuleCondition(variable="payment_delay_days", operator=">", value=30)],
            actions=[RuleAction(type="interest", rate=0.015, grace_period_days=30, base_variable="invoice_amount")],
            caps=RuleCaps(max_percentage=0.15)
        )
    ]

    res = QuestionParserService.parse_simulation_question(
        contract_id="CONTRACT-001",
        question="Calculate the penalty for 45 days of payment delay on a $500,000 invoice.",
        rules=rules
    )

    assert res.matched_rule.rule_code == "RULE-INT-02"
    assert res.extracted_parameters.get("payment_delay_days") == 45
    assert res.extracted_parameters.get("invoice_amount") == 500000.0
    assert res.status == "READY"


def test_question_parser_volume_discount():
    """Verify volume discount rule extraction."""
    rules = [
        LegalIR(
            rule_id="RULE-VOL-03",
            type="volume_discount",
            title="Volume Discount",
            source=RuleSourceInfo(page=2, section="4.3", text="5% discount"),
            conditions=[RuleCondition(variable="order_quantity", operator=">", value=2000)],
            actions=[RuleAction(type="discount", rate=0.05, base_variable="contract_value")],
            caps=RuleCaps()
        )
    ]

    res = QuestionParserService.parse_simulation_question(
        contract_id="CONTRACT-001",
        question="What if order quantity reaches 2,500 units?",
        rules=rules
    )

    assert res.matched_rule.rule_code == "RULE-VOL-03"
    assert res.extracted_parameters.get("order_quantity") == 2500


# ============================================================================
# 3. Deterministic Question Calculation Unit Tests
# ============================================================================

def test_deterministic_calculation_accuracy_and_caps():
    """Verify calculation uses pure math and enforces liability caps."""
    rule = LegalIR(
        rule_id="RULE-DELIV-01",
        type="delivery_delay_penalty",
        title="Delivery Delay Liquidated Damages",
        source=RuleSourceInfo(page=3, section="8.2", text="0.5% per day delay"),
        conditions=[RuleCondition(variable="delivery_delay_days", operator=">", value=15)],
        actions=[RuleAction(type="penalty", rate=0.005, period="day", grace_period_days=15, base_variable="contract_value")],
        caps=RuleCaps(max_percentage=0.10)
    )

    # 25 days delay (10 days past grace) on $1,000,000:
    # ceil(10 / 7) = 2 weeks * 0.5% * $1,000,000 = $10,000.0 (cap is $100,000)
    res = DeterministicRuleEngine.execute_rules(
        contract_id="TEST-001",
        rules=[rule],
        variables={"contract_value": 1000000.0, "delivery_delay_days": 25}
    )

    assert res.total_financial_impact == 10000.0
    assert len(res.calculation_steps) == 1
    assert res.calculation_steps[0].subtotal == 10000.0
    assert "2 week(s)" in res.calculation_steps[0].description
    assert res.calculation_steps[0].source_clause.section == "8.2"

    # 170 days delay (155 days past grace):
    # ceil(155 / 7) = 23 weeks * 0.5% = 11.5% ($115,000), capped at 10% ($100,000)
    capped_res = DeterministicRuleEngine.execute_rules(
        contract_id="TEST-001",
        rules=[rule],
        variables={"contract_value": 1000000.0, "delivery_delay_days": 170}
    )
    assert capped_res.total_financial_impact == 100000.0
    assert "capped" in capped_res.calculation_steps[0].description.lower()


# ============================================================================
# 4. End-to-End API Tests
# ============================================================================

def test_api_get_contract_parameters():
    """Test GET /api/simulations/contracts/{contract_id}/parameters."""
    client = get_auth_client()
    resp = client.get("/api/simulations/contracts/CONTRACT-SIM-001/parameters")
    assert resp.status_code == 200
    data = resp.json()

    assert data["contract_id"] == "CONTRACT-SIM-001"
    assert data["rules_count"] == 3
    assert len(data["parameters"]) >= 3
    var_names = [p["variable_name"] for p in data["parameters"]]
    assert "delivery_delay_days" in var_names
    assert "payment_delay_days" in var_names
    assert "order_quantity" in var_names


def test_api_parse_question():
    """Test POST /api/simulations/parse-question."""
    client = get_auth_client()
    resp = client.post("/api/simulations/parse-question", json={
        "contract_id": "CONTRACT-SIM-001",
        "question": "What if delivery is delayed by 20 days?"
    })
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "NEEDS_CONFIRMATION"
    assert data["matched_rule"]["rule_code"] == "RULE-DELIV-01"
    assert data["extracted_parameters"]["delivery_delay_days"] == 20
    assert "contract_value" in data["missing_parameters"]
    assert "Section 8.2" in data["confirmation_prompt"]


def test_api_calculate_question_persistence():
    """Test POST /api/simulations/calculate-question and verify DB persistence."""
    client = get_auth_client()
    resp = client.post("/api/simulations/calculate-question", json={
        "contract_id": "CONTRACT-SIM-001",
        "rule_code": "RULE-DELIV-01",
        "variables": {
            "contract_value": 1000000.0,
            "delivery_delay_days": 20
        },
        "assumptions": ["Assumed baseline contract value is $1,000,000.00."]
    })
    assert resp.status_code == 200
    data = resp.json()

    assert data["rule_code"] == "RULE-DELIV-01"
    # 20 days - 15 grace days = 5 days -> ceil(5/7) = 1 week * 0.5% * $1,000,000 = $5,000.0
    assert data["total_financial_impact"] == 5000.0
    assert data["source_clause"]["section"] == "8.2"
    assert data["audit_trace_id"].startswith("QSIM-")

    # Verify saved in SQLite database
    db = TestingSessionLocal()
    exec_record = db.query(ExecutionModel).filter(ExecutionModel.id == data["audit_trace_id"]).first()
    assert exec_record is not None
    assert exec_record.financial_impact == 5000.0
    assert exec_record.contract_id == "CONTRACT-SIM-001"

    # Verify execution steps saved
    step_records = db.query(ExecutionStepModel).filter(ExecutionStepModel.execution_id == data["audit_trace_id"]).all()
    assert len(step_records) >= 1
    assert step_records[0].subtotal == 5000.0

    # Verify audit log recorded
    audit_record = db.query(AuditLogModel).filter(
        AuditLogModel.contract_id == "CONTRACT-SIM-001",
        AuditLogModel.action == "SIMULATION_CALCULATE_QUESTION"
    ).first()
    assert audit_record is not None
    db.close()
