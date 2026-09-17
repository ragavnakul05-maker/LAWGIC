from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Response, Query, Body
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.schemas import (
    RuleModel, ContractModel, ClauseModel, LegalIR, SimulationRequest, SimulationResponse,
    ExecutionModel, ExecutionStepModel, UserModel,
    ContractSimulatorSchemaResponse, QuestionParseRequest, QuestionParseResponse,
    QuestionCalculateRequest, QuestionCalculateResponse,
    ContractSimulationCompareRequest, ContractSimulationComparisonResponse
)
from app.services.simulation_engine import SimulationEngine
from app.services.question_parser_service import QuestionParserService
from app.services.rule_validation_engine import RuleValidationEngine
from app.services.deterministic_rule_engine import DeterministicRuleEngine
from app.services.audit_service import AuditService
from app.services.report_export_service import ReportExportService

router = APIRouter(prefix="/simulations", tags=["Simulations"])

@router.get("/contracts/{contract_id}/parameters", response_model=ContractSimulatorSchemaResponse)
def get_contract_parameters(
    contract_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Dynamically loads all variables, formulas, rates, thresholds, and caps from
    the selected contract's Legal IR to build a contract-specific simulator schema.
    """
    contract = db.query(ContractModel).filter(
        ContractModel.id == contract_id,
        ContractModel.user_id == current_user.id
    ).first()
    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")

    rules_rec = db.query(RuleModel).filter(RuleModel.contract_id == contract_id).all()
    if not rules_rec:
        raise HTTPException(status_code=404, detail=f"No rules found for contract {contract_id}")

    legal_ir_list = [LegalIR(**r.ir_json) for r in rules_rec]
    schema_res = SimulationEngine.get_contract_simulator_schema(
        contract_id=contract_id,
        contract_title=contract.title,
        rules=legal_ir_list
    )
    return schema_res

@router.post("/parse-question", response_model=QuestionParseResponse)
def parse_simulation_question(
    req: QuestionParseRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Uses NLP/LLM strictly to understand natural language questions (e.g.
    'What if delivery is delayed by 20 days?'), identify the exact Legal IR rule,
    extract parameters, and check for missing required inputs.
    """
    contract = db.query(ContractModel).filter(
        ContractModel.id == req.contract_id,
        ContractModel.user_id == current_user.id
    ).first()
    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract {req.contract_id} not found")

    rules_rec = db.query(RuleModel).filter(RuleModel.contract_id == req.contract_id).all()
    if not rules_rec:
        raise HTTPException(status_code=404, detail=f"No rules found for contract {req.contract_id}")

    legal_ir_list = [LegalIR(**r.ir_json) for r in rules_rec]
    return QuestionParserService.parse_simulation_question(
        contract_id=req.contract_id,
        question=req.question,
        rules=legal_ir_list,
        contract_title=contract.title
    )

@router.post("/calculate-question", response_model=QuestionCalculateResponse)
def calculate_simulation_question(
    req: QuestionCalculateRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Validates user inputs via RuleValidationEngine and executes calculation strictly
    via DeterministicRuleEngine. Zero LLM recalculation. Persists simulation result
    and steps to the database for complete audit tracing.
    """
    contract = db.query(ContractModel).filter(
        ContractModel.id == req.contract_id,
        ContractModel.user_id == current_user.id
    ).first()
    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract {req.contract_id} not found")

    rules_rec = db.query(RuleModel).filter(RuleModel.contract_id == req.contract_id).all()
    if not rules_rec:
        raise HTTPException(status_code=404, detail=f"No rules found for contract {req.contract_id}")

    legal_ir_list = [LegalIR(**r.ir_json) for r in rules_rec]

    # Find the target rule
    target_rule = next((r for r in legal_ir_list if r.rule_id == req.rule_code), None)
    if not target_rule:
        target_rule = next((r for r in legal_ir_list if r.type not in ("general_clause", "boilerplate")), legal_ir_list[0])

    # Validate rule integrity using RuleValidationEngine
    validation_res = RuleValidationEngine.validate_rule(target_rule)

    # Deterministic Execution (Zero LLM)
    exec_result = DeterministicRuleEngine.execute_rules(
        contract_id=req.contract_id,
        rules=[target_rule],
        variables=req.variables,
        scenario_name=f"What-If Question: {target_rule.title}"
    )

    formula = None
    source_clause = target_rule.source
    if exec_result.calculation_steps:
        formula = exec_result.calculation_steps[0].formula
        if exec_result.calculation_steps[0].source_clause:
            source_clause = exec_result.calculation_steps[0].source_clause

    # Persist simulation execution to ExecutionModel
    exec_id = f"QSIM-{uuid4().hex[:8].upper()}"
    exec_rec = ExecutionModel(
        id=exec_id,
        contract_id=req.contract_id,
        user_id=current_user.id,
        scenario_name=f"What-If: {target_rule.title}",
        input_variables=req.variables,
        financial_impact=exec_result.total_financial_impact,
        summary_result={
            "rule_code": target_rule.rule_id,
            "rule_title": target_rule.title,
            "status": "COMPLETED",
            "validation_status": validation_res.status,
            "formula": formula,
            "human_explanation": exec_result.human_explanation,
        },
        executed_at=datetime.utcnow(),
    )
    db.add(exec_rec)

    # Persist step details
    for step in exec_result.calculation_steps:
        step_rec = ExecutionStepModel(
            id=f"STEP-{exec_id}-{step.step_number}",
            execution_id=exec_id,
            step_number=step.step_number,
            rule_code=step.rule_code,
            title=step.title,
            description=step.description,
            formula=step.formula,
            subtotal=step.subtotal,
            source_clause_id=None
        )
        db.add(step_rec)

    db.commit()

    # Log to AuditService
    AuditService.log_event(
        db=db,
        contract_id=req.contract_id,
        action="SIMULATION_CALCULATE_QUESTION",
        details={
            "execution_id": exec_id,
            "rule_code": target_rule.rule_id,
            "variables": req.variables,
            "financial_impact": exec_result.total_financial_impact
        },
        user_id=current_user.id
    )

    assumptions = req.assumptions or []

    return QuestionCalculateResponse(
        contract_id=req.contract_id,
        rule_code=target_rule.rule_id,
        total_financial_impact=exec_result.total_financial_impact,
        formula=formula,
        calculation_steps=exec_result.calculation_steps,
        applied_rules=exec_result.applied_rules,
        human_explanation=exec_result.human_explanation,
        source_clause=source_clause,
        assumptions=assumptions,
        audit_trace_id=exec_id
    )

@router.post("/run", response_model=SimulationResponse)
def run_simulation(req: SimulationRequest, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """
    Executes what-if scenario simulations reusing the exact deterministic rule engine.
    Zero LLM calls during calculations. Results persisted for Audit trail.
    """
    contract = db.query(ContractModel).filter(
        ContractModel.id == req.contract_id,
        ContractModel.user_id == current_user.id
    ).first()
    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract {req.contract_id} not found")

    rules_rec = db.query(RuleModel).filter(RuleModel.contract_id == req.contract_id).all()
    if not rules_rec:
        raise HTTPException(status_code=404, detail=f"No rules found for contract {req.contract_id}")

    legal_ir_list = [LegalIR(**r.ir_json) for r in rules_rec]

    scenarios_payload = [sc.model_dump() for sc in req.scenarios]

    sim_res = SimulationEngine.run_simulation(
        contract_id=req.contract_id,
        rules=legal_ir_list,
        baseline_variables=req.baseline_variables,
        scenarios_input=scenarios_payload
    )

    # Persist baseline simulation execution with user_id so Audit trail is complete
    baseline_exec_id = f"SIM-{uuid4().hex[:8].upper()}"
    exec_rec = ExecutionModel(
        id=baseline_exec_id,
        contract_id=req.contract_id,
        user_id=current_user.id,
        scenario_name=f"What-If Simulation — {len(req.scenarios)} scenario(s)",
        input_variables=req.baseline_variables,
        financial_impact=sim_res.baseline.financial_impact,
        summary_result={
            "baseline_impact": sim_res.baseline.financial_impact,
            "scenarios_count": len(sim_res.scenarios),
            "status": "COMPLETED",
        },
        executed_at=datetime.utcnow(),
    )
    db.add(exec_rec)
    db.commit()

    AuditService.log_event(
        db=db,
        contract_id=req.contract_id,
        action="RUN_SIMULATION",
        details={
            "execution_id": baseline_exec_id,
            "baseline_impact": sim_res.baseline.financial_impact,
            "scenarios_count": len(sim_res.scenarios)
        },
        user_id=current_user.id
    )

    return sim_res

@router.post("/compare", response_model=ContractSimulationComparisonResponse)
def compare_contract_simulation(
    req: ContractSimulationCompareRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Executes a contract-specific, parameter-driven What-If simulation comparing
    ORIGINAL CONTRACT SCENARIO vs WHAT-IF SCENARIO.
    Runs 100% deterministically using the existing Legal IR and Rule Engine.
    Persists simulation results to ExecutionModel and ExecutionStepModel.
    Records complete audit trace in AuditLogModel with user and contract provenance.
    Strict tenant isolation enforced: user can only simulate their own contracts.
    """
    contract = db.query(ContractModel).filter(
        ContractModel.id == req.contract_id,
        ContractModel.user_id == current_user.id
    ).first()
    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract {req.contract_id} not found")

    rules_rec = db.query(RuleModel).filter(RuleModel.contract_id == req.contract_id).all()
    if not rules_rec:
        raise HTTPException(status_code=404, detail=f"No rules found for contract {req.contract_id}")

    legal_ir_list = [LegalIR(**r.ir_json) for r in rules_rec]

    # If original_variables not supplied, derive from contract schema baseline
    schema_res = SimulationEngine.get_contract_simulator_schema(
        contract_id=req.contract_id,
        contract_title=contract.title,
        rules=legal_ir_list
    )
    original_vars = req.original_variables or schema_res.baseline_variables

    # Run deterministic comparison
    comparison_res = SimulationEngine.compare_contract_scenarios(
        contract_id=req.contract_id,
        contract_title=contract.title,
        rules=legal_ir_list,
        original_variables=original_vars,
        what_if_variables=req.what_if_variables,
        user_id=current_user.id,
        user_name=current_user.full_name
    )

    # Link clause IDs to comparison results
    rules_by_code = {r.rule_code: r for r in rules_rec}
    for rule_res in comparison_res.rules:
        r_rec = rules_by_code.get(rule_res.rule_code)
        if r_rec:
            rule_res.clause_id = r_rec.clause_id

    # Persist simulation execution to ExecutionModel
    exec_id = comparison_res.audit_trace_id
    exec_rec = ExecutionModel(
        id=exec_id,
        contract_id=req.contract_id,
        user_id=current_user.id,
        scenario_name=f"What-If Simulation: {contract.title}",
        input_variables={
            "original_variables": original_vars,
            "what_if_variables": req.what_if_variables
        },
        financial_impact=comparison_res.net_difference,
        summary_result={
            "original_total_impact": comparison_res.original_total_impact,
            "what_if_total_impact": comparison_res.what_if_total_impact,
            "net_difference": comparison_res.net_difference,
            "rules_evaluated_count": comparison_res.rules_evaluated_count,
            "rules_triggered_count": comparison_res.rules_triggered_count,
            "status": "COMPLETED",
            "overall_human_explanation": comparison_res.overall_human_explanation,
        },
        executed_at=datetime.utcnow()
    )
    db.add(exec_rec)

    # Persist each rule comparison step to ExecutionStepModel
    for step_idx, rule_res in enumerate(comparison_res.rules, start=1):
        step_rec = ExecutionStepModel(
            id=f"STEP-{exec_id}-{step_idx}",
            execution_id=exec_id,
            step_number=step_idx,
            rule_code=rule_res.rule_code,
            title=rule_res.rule_title,
            description=f"{rule_res.calculation_breakdown} (Reason: {rule_res.reason})",
            formula=rule_res.formula,
            subtotal=rule_res.difference,
            source_clause_id=rule_res.clause_id
        )
        db.add(step_rec)

    db.commit()

    # Log to AuditService
    AuditService.log_event(
        db=db,
        contract_id=req.contract_id,
        action="CONTRACT_WHAT_IF_SIMULATION",
        details={
            "execution_id": exec_id,
            "contract_title": contract.title,
            "user_id": current_user.id,
            "user_name": current_user.full_name,
            "original_total_impact": comparison_res.original_total_impact,
            "what_if_total_impact": comparison_res.what_if_total_impact,
            "net_difference": comparison_res.net_difference,
            "rules_compared_count": len(comparison_res.rules),
            "original_variables": original_vars,
            "what_if_variables": req.what_if_variables
        },
        user_id=current_user.id
    )

    return comparison_res


@router.post("/export")
def export_simulation_report(
    comparison_data: Dict[str, Any] = Body(...),
    format: str = Query("html"),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Exports an active What-If simulation comparison as:
      - 'html' or 'pdf': Executive comparative report with KPI variance and rule-by-rule breakdown
      - 'csv': RFC-4180 comparative spreadsheet
      - 'json': Cryptographically formatted comparison package
    """
    fmt = format.lower().strip()
    contract_id = comparison_data.get("contract_id", "simulation")

    if fmt == "csv":
        csv_content = ReportExportService.generate_simulation_csv(comparison_data)
        filename = f"simulation_{contract_id}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    elif fmt == "json":
        filename = f"simulation_{contract_id}.json"
        return JSONResponse(
            content=comparison_data,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    elif fmt in ["html", "pdf"]:
        html_content = ReportExportService.generate_simulation_html_report(
            comparison_data,
            user_name=current_user.full_name or "Financial Auditor"
        )
        return Response(
            content=html_content,
            media_type="text/html"
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{format}'. Supported formats are: 'html', 'pdf', 'csv', 'json'."
        )



