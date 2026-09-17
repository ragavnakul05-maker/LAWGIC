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
    UserModel, ContractModel, ClauseModel, RuleModel, LegalIR,
    RuleSourceInfo, RuleCondition, RuleAction, RuleCaps,
    ExecutionModel, ExecutionStepModel, AuditLogModel
)
from app.services.simulation_engine import SimulationEngine
from app.services.deterministic_rule_engine import DeterministicRuleEngine

TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    migrate_db(bind_engine=test_engine)
    db = TestingSessionLocal()

    # User A
    user_a = UserModel(
        id="USER-A",
        email="user_a@lawgic.ai",
        full_name="Alice Legal Counsel",
        role="Senior Counsel",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db.add(user_a)

    # User B
    user_b = UserModel(
        id="USER-B",
        email="user_b@lawgic.ai",
        full_name="Bob Legal Partner",
        role="Partner",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db.add(user_b)

    # ------------------------------------------------------------------------
    # Contract A (owned by User A): Logistics & Supply Agreement
    # Rules: Delivery Delay Penalty + Volume Discount (NO Late Payment, NO SLA)
    # ------------------------------------------------------------------------
    contract_a = ContractModel(
        id="CONTRACT-A",
        user_id="USER-A",
        title="Logistics & Component Supply Agreement",
        filename="Logistics_Agreement.pdf",
        file_type="PDF",
        file_path="uploads/USER-A/logistics.pdf.enc",
        page_count=4,
        status="ANALYZED"
    )
    db.add(contract_a)

    clause_a1 = ClauseModel(
        id="CLAUSE-A1",
        contract_id="CONTRACT-A",
        page_number=2,
        section_number="2.2",
        clause_number="2.2",
        title="Delivery Delay Liquidated Damages",
        original_text="If delivery is delayed beyond 10 days, 2% per week penalty applies, max 10% cap.",
        clause_type="delivery_delay_penalty"
    )
    db.add(clause_a1)

    rule_a1_ir = LegalIR(
        rule_id="R-DELIV-01",
        type="delivery_delay_penalty",
        title="Delivery Delay Penalty",
        source=RuleSourceInfo(page=2, section="2.2", text="2% per week penalty after 10 days"),
        conditions=[RuleCondition(variable="delivery_delay_days", operator=">", value=10, unit="days")],
        actions=[RuleAction(type="penalty", rate=0.02, period="week", grace_period_days=10, base_variable="contract_value")],
        caps=RuleCaps(max_percentage=0.10)
    )
    db.add(RuleModel(
        id="RULE-A1",
        contract_id="CONTRACT-A",
        clause_id="CLAUSE-A1",
        rule_code="R-DELIV-01",
        rule_type="delivery_delay_penalty",
        title="Delivery Delay Penalty",
        ir_json=rule_a1_ir.model_dump(),
        validation_status="VALID"
    ))

    clause_a2 = ClauseModel(
        id="CLAUSE-A2",
        contract_id="CONTRACT-A",
        page_number=1,
        section_number="1.3",
        clause_number="1.3",
        title="Volume Tier Discount",
        original_text="Orders exceeding 1,000 units receive a 5% volume discount on total contract value.",
        clause_type="volume_discount"
    )
    db.add(clause_a2)

    rule_a2_ir = LegalIR(
        rule_id="R-VOL-02",
        type="volume_discount",
        title="Volume Tier Discount",
        source=RuleSourceInfo(page=1, section="1.3", text="5% discount on >= 1000 units"),
        conditions=[RuleCondition(variable="order_quantity", operator=">=", value=1000, unit="units")],
        actions=[RuleAction(type="discount", rate=0.05, base_variable="contract_value")],
        caps=RuleCaps() # No cap specified
    )
    db.add(RuleModel(
        id="RULE-A2",
        contract_id="CONTRACT-A",
        clause_id="CLAUSE-A2",
        rule_code="R-VOL-02",
        rule_type="volume_discount",
        title="Volume Tier Discount",
        ir_json=rule_a2_ir.model_dump(),
        validation_status="VALID"
    ))

    # ------------------------------------------------------------------------
    # Contract B (owned by User A): SaaS Telemetry & SLA Agreement
    # Rules: Late Payment Interest + SLA Penalty (NO Delivery Delay, NO Volume Discount)
    # ------------------------------------------------------------------------
    contract_b = ContractModel(
        id="CONTRACT-B",
        user_id="USER-A",
        title="Cloud Telemetry & SLA Agreement",
        filename="Telemetry_SLA.pdf",
        file_type="PDF",
        file_path="uploads/USER-A/telemetry_sla.pdf.enc",
        page_count=3,
        status="ANALYZED"
    )
    db.add(contract_b)

    clause_b1 = ClauseModel(
        id="CLAUSE-B1",
        contract_id="CONTRACT-B",
        page_number=2,
        section_number="3.1",
        clause_number="3.1",
        title="Overdue Invoice Interest",
        original_text="1.5% interest per month for invoice payment delayed beyond 30 days, maximum 15% cap.",
        clause_type="late_payment_interest"
    )
    db.add(clause_b1)

    rule_b1_ir = LegalIR(
        rule_id="R-INT-01",
        type="late_payment_interest",
        title="Late Payment Interest Charge",
        source=RuleSourceInfo(page=2, section="3.1", text="1.5% per month after 30 days"),
        conditions=[RuleCondition(variable="payment_delay_days", operator=">", value=30, unit="days")],
        actions=[RuleAction(type="interest", rate=0.015, period="month", grace_period_days=30, base_variable="invoice_amount")],
        caps=RuleCaps(max_percentage=0.15)
    )
    db.add(RuleModel(
        id="RULE-B1",
        contract_id="CONTRACT-B",
        clause_id="CLAUSE-B1",
        rule_code="R-INT-01",
        rule_type="late_payment_interest",
        title="Late Payment Interest Charge",
        ir_json=rule_b1_ir.model_dump(),
        validation_status="VALID"
    ))

    clause_b2 = ClauseModel(
        id="CLAUSE-B2",
        contract_id="CONTRACT-B",
        page_number=3,
        section_number="4.2",
        clause_number="4.2",
        title="SLA Breach Penalty",
        original_text="If uptime drops below 99.5%, deduct $500 per 0.1% breach up to a maximum of $5,000.",
        clause_type="sla_penalty"
    )
    db.add(clause_b2)

    rule_b2_ir = LegalIR(
        rule_id="R-SLA-02",
        type="sla_penalty",
        title="SLA Uptime Penalty",
        source=RuleSourceInfo(page=3, section="4.2", text="$500 per 0.1% breach below 99.5%"),
        conditions=[RuleCondition(variable="sla_uptime_percent", operator="<", value=99.5, unit="percent")],
        actions=[RuleAction(type="sla_deduction", amount=500.0, period="incident")],
        caps=RuleCaps(max_amount=5000.0)
    )
    db.add(RuleModel(
        id="RULE-B2",
        contract_id="CONTRACT-B",
        clause_id="CLAUSE-B2",
        rule_code="R-SLA-02",
        rule_type="sla_penalty",
        title="SLA Uptime Penalty",
        ir_json=rule_b2_ir.model_dump(),
        validation_status="VALID"
    ))

    # ------------------------------------------------------------------------
    # Contract C (owned by User B): Private Master Agreement
    # Rules: $10,000 per day delay, maximum $150,000
    # ------------------------------------------------------------------------
    contract_c = ContractModel(
        id="CONTRACT-C",
        user_id="USER-B",
        title="User B Exclusive Commercial Contract",
        filename="UserB_Agreement.pdf",
        file_type="PDF",
        file_path="uploads/USER-B/agreement.pdf.enc",
        page_count=2,
        status="ANALYZED"
    )
    db.add(contract_c)

    rule_c1_ir = LegalIR(
        rule_id="R-DAILY-01",
        type="delivery_delay_penalty",
        title="Fixed Daily Delay Penalty",
        source=RuleSourceInfo(page=2, section="5.1", text="$10,000 per day after 14 days, max $150,000"),
        conditions=[RuleCondition(variable="delivery_delay_days", operator=">", value=14, unit="days")],
        actions=[RuleAction(type="penalty", amount=10000.0, period="day", grace_period_days=14, base_variable="contract_value")],
        caps=RuleCaps(max_amount=150000.0)
    )
    db.add(RuleModel(
        id="RULE-C1",
        contract_id="CONTRACT-C",
        clause_id="CLAUSE-C1",
        rule_code="R-DAILY-01",
        rule_type="delivery_delay_penalty",
        title="Fixed Daily Delay Penalty",
        ir_json=rule_c1_ir.model_dump(),
        validation_status="VALID"
    ))

    db.commit()
    db.close()


def get_client_for_user(email: str, password: str = "password123") -> TestClient:
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    login_res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login_res.status_code == 200, f"Login failed for {email}: {login_res.text}"
    token = login_res.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    return client


# ============================================================================
# REQUIREMENT 1 & 2: Dynamic Parameters & Isolation Between Contracts
# ============================================================================

def test_contract_a_shows_only_contract_a_parameters():
    """Verify Contract A returns ONLY delivery_delay_days, order_quantity, and contract_value."""
    client = get_client_for_user("user_a@lawgic.ai")
    resp = client.get("/api/simulations/contracts/CONTRACT-A/parameters")
    assert resp.status_code == 200
    data = resp.json()

    assert data["contract_id"] == "CONTRACT-A"
    assert data["rules_count"] == 2

    var_names = [p["variable_name"] for p in data["parameters"]]
    assert "delivery_delay_days" in var_names
    assert "order_quantity" in var_names
    assert "contract_value" in var_names

    # MUST NOT contain variables from Contract B
    assert "payment_delay_days" not in var_names
    assert "invoice_amount" not in var_names
    assert "sla_uptime_percent" not in var_names
    assert "inflation_rate_percent" not in var_names

    # Verify cap display
    deliv_param = next(p for p in data["parameters"] if p["variable_name"] == "delivery_delay_days")
    assert deliv_param["threshold"] == 10.0
    assert "10.0%" in deliv_param["cap"]

    vol_param = next(p for p in data["parameters"] if p["variable_name"] == "order_quantity")
    assert vol_param["threshold"] == 1000.0
    assert vol_param["cap"] == "Not specified in this contract"


def test_contract_b_shows_only_contract_b_parameters():
    """Verify Contract B returns ONLY payment_delay_days, sla_uptime_percent, and invoice_amount."""
    client = get_client_for_user("user_a@lawgic.ai")
    resp = client.get("/api/simulations/contracts/CONTRACT-B/parameters")
    assert resp.status_code == 200
    data = resp.json()

    assert data["contract_id"] == "CONTRACT-B"
    assert data["rules_count"] == 2

    var_names = [p["variable_name"] for p in data["parameters"]]
    assert "payment_delay_days" in var_names
    assert "invoice_amount" in var_names
    assert "sla_uptime_percent" in var_names

    # MUST NOT contain variables from Contract A
    assert "delivery_delay_days" not in var_names
    assert "order_quantity" not in var_names
    assert "inflation_rate_percent" not in var_names

    # Check SLA param caps
    sla_param = next(p for p in data["parameters"] if p["variable_name"] == "sla_uptime_percent")
    assert sla_param["threshold"] == 99.5
    assert "$5,000.00" in sla_param["cap"]


# ============================================================================
# REQUIREMENT 3, 4, 5: Deterministic Comparative Simulation & Granular Breakdown
# ============================================================================

def test_compare_simulation_contract_a_changing_parameters():
    """
    Test comparing Original Contract Scenario vs What-If Scenario on Contract A.
    Baseline: delivery_delay_days=10 (within threshold), order_quantity=1000, contract_value=1,000,000.
    What-If: delivery_delay_days=24 (14 days overdue = 2 weeks).
    """
    client = get_client_for_user("user_a@lawgic.ai")
    resp = client.post("/api/simulations/compare", json={
        "contract_id": "CONTRACT-A",
        "original_variables": {
            "delivery_delay_days": 10,
            "order_quantity": 1000,
            "contract_value": 1000000.0
        },
        "what_if_variables": {
            "delivery_delay_days": 24,
            "order_quantity": 1000,
            "contract_value": 1000000.0
        }
    })
    assert resp.status_code == 200
    data = resp.json()

    assert data["contract_id"] == "CONTRACT-A"
    assert data["rules_evaluated_count"] == 2

    # Original Total: Delay=0, Volume discount 5% on 1,000,000 = -50,000. Total = -50,000
    assert data["original_total_impact"] == -50000.0

    # What-If Total: Delay 2 weeks * 2% * 1,000,000 = +40,000; Volume discount = -50,000. Total = -10,000
    assert data["what_if_total_impact"] == -10000.0

    # Net difference: +40,000
    assert data["net_difference"] == 40000.0

    # Inspect delivery delay rule breakdown
    deliv_rule = next(r for r in data["rules"] if r["rule_code"] == "R-DELIV-01")
    assert deliv_rule["original_result"] == 0.0
    assert deliv_rule["what_if_result"] == 40000.0
    assert deliv_rule["difference"] == 40000.0
    assert deliv_rule["original_parameter_value"] == 10
    assert deliv_rule["what_if_parameter_value"] == 24
    assert deliv_rule["unit"] == "days"
    assert "min(" in deliv_rule["formula"]
    assert "2 week(s)" in deliv_rule["calculation_breakdown"]
    assert deliv_rule["cap_applied"] is False  # $40,000 < $100,000 cap
    assert "Max 10.0% ($100,000.00) cap" in deliv_rule["cap_detail"]
    assert len(deliv_rule["decompiled_explanation"]) > 0

    # Inspect volume discount rule breakdown
    vol_rule = next(r for r in data["rules"] if r["rule_code"] == "R-VOL-02")
    assert vol_rule["original_result"] == -50000.0
    assert vol_rule["what_if_result"] == -50000.0
    assert vol_rule["difference"] == 0.0
    assert vol_rule["cap_detail"] == "Not specified in this contract"


def test_contractual_cap_enforcement_contract_a():
    """Verify that exceeding liability limit enforces the cap and notes 'Contractual cap reached'."""
    client = get_client_for_user("user_a@lawgic.ai")
    resp = client.post("/api/simulations/compare", json={
        "contract_id": "CONTRACT-A",
        "original_variables": {
            "delivery_delay_days": 10,
            "order_quantity": 1000,
            "contract_value": 1000000.0
        },
        "what_if_variables": {
            "delivery_delay_days": 90,  # 80 days past grace = 12 weeks * 2% = 24% ($240,000), capped at 10% ($100,000)
            "order_quantity": 1000,
            "contract_value": 1000000.0
        }
    })
    assert resp.status_code == 200
    data = resp.json()

    deliv_rule = next(r for r in data["rules"] if r["rule_code"] == "R-DELIV-01")
    assert deliv_rule["what_if_result"] == 100000.0  # Capped at $100,000
    assert deliv_rule["cap_applied"] is True
    assert "Contractual cap reached" in deliv_rule["reason"]
    assert "Capped at contractual limit" in deliv_rule["calculation_breakdown"]


def test_fixed_daily_rate_with_cap_contract_c_example():
    """
    Test user prompt's exact example:
    Contract rule: $10,000 per day, maximum $150,000 (Contract C)
    Original delay: 14 days (threshold 14 -> 0 overdue days = $0.00)
    What-if delay: 34 days (20 overdue days -> 20 * $10,000 = $200,000 raw, capped at $150,000)
    Impact = +$150,000
    Reason = Contractual cap reached
    """
    client = get_client_for_user("user_b@lawgic.ai")
    resp = client.post("/api/simulations/compare", json={
        "contract_id": "CONTRACT-C",
        "original_variables": {
            "delivery_delay_days": 14,
            "contract_value": 1000000.0
        },
        "what_if_variables": {
            "delivery_delay_days": 34,
            "contract_value": 1000000.0
        }
    })
    assert resp.status_code == 200
    data = resp.json()

    assert data["contract_id"] == "CONTRACT-C"
    rule_res = data["rules"][0]
    assert rule_res["original_result"] == 0.0
    assert rule_res["what_if_result"] == 150000.0
    assert rule_res["difference"] == 150000.0
    assert rule_res["cap_applied"] is True
    assert "Contractual cap reached: Maximum $150,000.00" in rule_res["reason"]


# ============================================================================
# REQUIREMENT 6 & 8: Audit & Trace Persistence and Deterministic Provenance
# ============================================================================

def test_simulation_persistence_and_audit_log():
    """Verify simulation is persisted to ExecutionModel, ExecutionStepModel, and AuditLogModel."""
    client = get_client_for_user("user_a@lawgic.ai")
    resp = client.post("/api/simulations/compare", json={
        "contract_id": "CONTRACT-B",
        "what_if_variables": {
            "payment_delay_days": 45,  # 15 days overdue -> 1 month * 1.5% * $1,000,000 = $15,000
            "sla_uptime_percent": 98.5,  # 1.0% drop -> 10 incidents * $500 = $5,000 (cap is $5,000)
            "invoice_amount": 1000000.0
        }
    })
    assert resp.status_code == 200
    data = resp.json()
    trace_id = data["audit_trace_id"]
    assert trace_id.startswith("SIM-")

    # Verify execution record in DB
    db = TestingSessionLocal()
    exec_rec = db.query(ExecutionModel).filter(ExecutionModel.id == trace_id).first()
    assert exec_rec is not None
    assert exec_rec.contract_id == "CONTRACT-B"
    assert exec_rec.user_id == "USER-A"
    assert exec_rec.financial_impact == data["net_difference"]

    # Verify steps in DB
    steps = db.query(ExecutionStepModel).filter(ExecutionStepModel.execution_id == trace_id).all()
    assert len(steps) == 2

    # Verify audit log in DB
    audit_rec = db.query(AuditLogModel).filter(
        AuditLogModel.contract_id == "CONTRACT-B",
        AuditLogModel.action == "CONTRACT_WHAT_IF_SIMULATION"
    ).order_by(AuditLogModel.created_at.desc()).first()
    assert audit_rec is not None
    assert audit_rec.user_id == "USER-A"
    assert audit_rec.details["execution_id"] == trace_id
    db.close()


# ============================================================================
# REQUIREMENT 7: Data Isolation Between Users
# ============================================================================

def test_cross_tenant_simulation_blocked():
    """
    Verify User A CANNOT view parameters or simulate Contract C (owned by User B).
    Verify User B CANNOT view parameters or simulate Contract A (owned by User A).
    """
    client_a = get_client_for_user("user_a@lawgic.ai")
    client_b = get_client_for_user("user_b@lawgic.ai")

    # User A tries to get parameters for User B's contract -> 404
    resp1 = client_a.get("/api/simulations/contracts/CONTRACT-C/parameters")
    assert resp1.status_code == 404

    # User A tries to run simulation on User B's contract -> 404
    resp2 = client_a.post("/api/simulations/compare", json={
        "contract_id": "CONTRACT-C",
        "what_if_variables": {"delivery_delay_days": 20}
    })
    assert resp2.status_code == 404

    # User B tries to get parameters for User A's contract -> 404
    resp3 = client_b.get("/api/simulations/contracts/CONTRACT-A/parameters")
    assert resp3.status_code == 404

    # User B tries to run simulation on User A's contract -> 404
    resp4 = client_b.post("/api/simulations/compare", json={
        "contract_id": "CONTRACT-A",
        "what_if_variables": {"delivery_delay_days": 20}
    })
    assert resp4.status_code == 404
