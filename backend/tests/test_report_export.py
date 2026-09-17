"""
test_report_export.py — Automated test suite for Executive Report & Audit Dossier Export Engine.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app
from app.core.database import SessionLocal, Base, engine
from app.core.security import create_access_token, hash_password
from app.models.schemas import UserModel, ContractModel, ClauseModel, RuleModel, ExecutionModel, ExecutionStepModel
from app.services.report_export_service import ReportExportService

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_export_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Create primary user
    u1 = db.query(UserModel).filter(UserModel.email == "export_user1@lawgic.ai").first()
    if not u1:
        u1 = UserModel(
            id="EXP-USER-001",
            email="export_user1@lawgic.ai",
            hashed_password=hash_password("Pass123!"),
            full_name="Alex Mercer, CLO",
            role="Chief Legal Officer",
            is_active=True
        )
        db.add(u1)

    # Create secondary user for isolation tests
    u2 = db.query(UserModel).filter(UserModel.email == "export_user2@lawgic.ai").first()
    if not u2:
        u2 = UserModel(
            id="EXP-USER-002",
            email="export_user2@lawgic.ai",
            hashed_password=hash_password("Pass123!"),
            full_name="Bob Martinez",
            role="Auditor",
            is_active=True
        )
        db.add(u2)

    # Create contract for user 1
    c1 = db.query(ContractModel).filter(ContractModel.id == "EXP-CONTRACT-001").first()
    if not c1:
        c1 = ContractModel(
            id="EXP-CONTRACT-001",
            user_id="EXP-USER-001",
            title="SaaS Master Agreement 2026",
            filename="saas_contract.pdf",
            file_type="pdf",
            file_path="/tmp/saas_contract.pdf",
            page_count=10,
            status="ANALYZED",
            created_at=datetime.utcnow()
        )
        db.add(c1)

    # Create clause
    cl1 = db.query(ClauseModel).filter(ClauseModel.id == "EXP-CLAUSE-001").first()
    if not cl1:
        cl1 = ClauseModel(
            id="EXP-CLAUSE-001",
            contract_id="EXP-CONTRACT-001",
            section_number="8.2",
            title="Service Level Credits",
            original_text="Supplier guarantees 99.9% uptime. Below 99.0%, a penalty of 5% applies.",
            clause_type="sla_penalty",
            page_number=4
        )
        db.add(cl1)

    # Create rule
    r1 = db.query(RuleModel).filter(RuleModel.id == "RULE-EXP-001").first()
    if not r1:
        r1 = RuleModel(
            id="RULE-EXP-001",
            contract_id="EXP-CONTRACT-001",
            clause_id="EXP-CLAUSE-001",
            rule_code="SLA-001",
            rule_type="sla_penalty",
            title="Service Level Agreement",
            validation_status="VALID",
            ir_json={
                "rule_code": "SLA-001",
                "contract_id": "EXP-CONTRACT-001",
                "clause_reference": {"section": "8.2", "page": 4},
                "parameters": {"penalty_rate": 0.05, "sla_threshold": 99.0},
                "calculation": {
                    "formula": "base_fee * 0.05",
                    "conditions": ["uptime < 99.0"]
                },
                "explanation": "5% SLA deduction"
            },
            human_explanation="5% credit deducted for uptime below 99.0%"
        )
        db.add(r1)

    # Create execution record
    ex1 = db.query(ExecutionModel).filter(ExecutionModel.id == "EXEC-EXP-001").first()
    if not ex1:
        ex1 = ExecutionModel(
            id="EXEC-EXP-001",
            contract_id="EXP-CONTRACT-001",
            user_id="EXP-USER-001",
            scenario_name="SLA Breach Scenario",
            input_variables={"uptime": 98.5, "base_fee": 100000},
            financial_impact=-5000.0,
            summary_result={"penalty": 5000.0, "status": "COMPLETED"},
            executed_at=datetime.utcnow()
        )
        db.add(ex1)

    # Create execution step
    step1 = db.query(ExecutionStepModel).filter(ExecutionStepModel.id == "STEP-EXP-001").first()
    if not step1:
        step1 = ExecutionStepModel(
            id="STEP-EXP-001",
            execution_id="EXEC-EXP-001",
            step_number=1,
            rule_code="SLA-001",
            title="Uptime SLA Deduction",
            description="5% credit deducted for uptime below 99.0%",
            formula="base_fee * 0.05",
            subtotal=-5000.0,
            source_clause_id="EXP-CLAUSE-001"
        )
        db.add(step1)

    db.commit()
    db.close()
    yield


def test_generate_audit_csv():
    sample_trail = {
        "execution_id": "TEST-EXEC-999",
        "contract_title": "Enterprise Cloud Agreement",
        "contract_id": "CONTRACT-999",
        "scenario_name": "Test Run",
        "financial_impact": -15000.0,
        "executed_at": "2026-09-16T12:00:00",
        "steps": [
            {
                "step_number": 1,
                "rule_code": "PENALTY-01",
                "rule_title": "Late Delivery Penalty",
                "rule_type": "penalty",
                "formula": "delay_days * 500",
                "description": "500 per day of delay",
                "subtotal": -5000.0,
                "validation_status": "VALID",
                "source_clause": {
                    "section": "4.1",
                    "page": 2,
                    "original_text": "Late delivery shall be penalized at 500 INR/day."
                }
            }
        ]
    }
    csv_str = ReportExportService.generate_audit_csv(sample_trail)
    assert "LAWGIC DETERMINISTIC AUDIT LEDGER" in csv_str
    assert "TEST-EXEC-999" in csv_str
    assert "Enterprise Cloud Agreement" in csv_str
    assert "PENALTY-01" in csv_str
    assert "Late Delivery Penalty" in csv_str
    assert "delay_days * 500" in csv_str
    assert "₹5,000" in csv_str or "-₹5,000" in csv_str


def test_generate_audit_json():
    sample_trail = {
        "execution_id": "TEST-EXEC-888",
        "contract_title": "Master Supplier Contract",
        "contract_id": "CONTRACT-888",
        "scenario_name": "Default Baseline",
        "financial_impact": 25000.0,
        "executed_at": "2026-09-16T15:00:00",
        "steps": [
            {
                "step_number": 1,
                "rule_code": "DISCOUNT-01",
                "formula": "units * 10",
                "subtotal": 25000.0,
            }
        ]
    }
    dossier = ReportExportService.generate_audit_json(sample_trail, user_id="USER-123")
    assert dossier["dossier_version"] == "1.0-lawgic-audit"
    assert dossier["integrity_signature"]["zero_hallucination_guarantee"] is True
    assert "calculation_hash" in dossier["integrity_signature"]
    assert dossier["contract"]["id"] == "CONTRACT-888"
    assert dossier["execution"]["financial_impact"] == 25000.0


def test_generate_audit_html_report():
    sample_trail = {
        "execution_id": "TEST-EXEC-777",
        "contract_title": "Logistics SOW",
        "contract_id": "CONTRACT-777",
        "scenario_name": "Audit Trail",
        "financial_impact": -8000.0,
        "executed_at": "2026-09-16T16:00:00",
        "input_variables": {"transit_days": 12},
        "steps": [
            {
                "step_number": 1,
                "rule_code": "LOG-01",
                "rule_title": "Transit Overrun",
                "formula": "transit_days * 1000",
                "description": "Overrun fee applied",
                "subtotal": -8000.0,
                "validation_status": "VALID",
                "source_clause": {
                    "section": "3.3",
                    "page": 7,
                    "original_text": "Transit time shall not exceed 5 days."
                }
            }
        ]
    }
    html = ReportExportService.generate_audit_html_report(sample_trail, user_name="Jane Doe")
    assert "<!DOCTYPE html>" in html
    assert "LAWGIC" in html
    assert "DETERMINISTIC AUDIT DOSSIER" in html
    assert "Logistics SOW" in html
    assert "Jane Doe" in html
    assert "Transit Overrun" in html
    assert "Transit time shall not exceed 5 days." in html


def test_export_audit_endpoint_html(setup_export_db):
    token = create_access_token(data={"sub": "EXP-USER-001"})
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/audit/executions/EXEC-EXP-001/export?format=html", headers=headers)
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "LAWGIC" in res.text
    assert "SaaS Master Agreement 2026" in res.text


def test_export_audit_endpoint_csv(setup_export_db):
    token = create_access_token(data={"sub": "EXP-USER-001"})
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/audit/executions/EXEC-EXP-001/export?format=csv", headers=headers)
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "attachment; filename=\"audit_ledger_EXEC-EXP-001.csv\"" in res.headers["content-disposition"]
    assert "SLA-001" in res.text


def test_export_audit_endpoint_json(setup_export_db):
    token = create_access_token(data={"sub": "EXP-USER-001"})
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/audit/executions/EXEC-EXP-001/export?format=json", headers=headers)
    assert res.status_code == 200
    assert "application/json" in res.headers["content-type"]
    data = res.json()
    assert data["dossier_version"] == "1.0-lawgic-audit"
    assert data["contract"]["title"] == "SaaS Master Agreement 2026"


def test_export_audit_tenant_isolation(setup_export_db):
    # User 2 tries to export User 1's execution record
    token_user2 = create_access_token(data={"sub": "EXP-USER-002"})
    headers = {"Authorization": f"Bearer {token_user2}"}

    res = client.get("/api/audit/executions/EXEC-EXP-001/export?format=html", headers=headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "Execution record not found"


def test_export_simulation_endpoint(setup_export_db):
    token = create_access_token(data={"sub": "EXP-USER-001"})
    headers = {"Authorization": f"Bearer {token}"}

    comparison_payload = {
        "contract_id": "EXP-CONTRACT-001",
        "contract_title": "SaaS Master Agreement 2026",
        "audit_trace_id": "SIM-TRACE-12345",
        "original_total_impact": 0,
        "what_if_total_impact": -5000,
        "net_difference": -5000,
        "rules_evaluated_count": 1,
        "rules_triggered_count": 1,
        "overall_human_explanation": "SLA penalty applied due to downtime.",
        "rules": [
            {
                "rule_code": "SLA-001",
                "rule_title": "Uptime SLA Deduction",
                "rule_type": "sla_penalty",
                "formula": "base_fee * 0.05",
                "original_subtotal": 0,
                "what_if_subtotal": -5000,
                "difference": -5000,
                "triggered": True,
                "reason": "Uptime fell below minimum threshold"
            }
        ]
    }

    # Test CSV
    res_csv = client.post("/api/simulations/export?format=csv", json=comparison_payload, headers=headers)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "SIM-TRACE-12345" in res_csv.text

    # Test HTML
    res_html = client.post("/api/simulations/export?format=html", json=comparison_payload, headers=headers)
    assert res_html.status_code == 200
    assert "text/html" in res_html.headers["content-type"]
    assert "WHAT-IF SCENARIO REPORT" in res_html.text
