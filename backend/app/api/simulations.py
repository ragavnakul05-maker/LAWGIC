from typing import List
from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.schemas import (
    RuleModel, ClauseModel, LegalIR, SimulationRequest, SimulationResponse,
    ExecutionModel, ExecutionStepModel, UserModel,
)
from app.services.simulation_engine import SimulationEngine
from app.services.audit_service import AuditService
from app.services.decompiler_service import DecompilerService

router = APIRouter(prefix="/simulations", tags=["Simulations"])

@router.post("/run", response_model=SimulationResponse)
def run_simulation(req: SimulationRequest, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """
    Executes what-if scenario simulations reusing the exact deterministic rule engine.
    Zero LLM calls during calculations. Results and full step traces persisted for Audit trail.
    """
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

    # 1. Persist baseline simulation execution with granular step traces & clause linking
    baseline_exec_id = f"SIM-BASE-{uuid4().hex[:8].upper()}"
    db.add(ExecutionModel(
        id=baseline_exec_id,
        contract_id=req.contract_id,
        scenario_name="What-If Simulation (Baseline)",
        input_variables=req.baseline_variables,
        financial_impact=sim_res.baseline.financial_impact,
        summary_result={
            "baseline_impact": sim_res.baseline.financial_impact,
            "scenarios_count": len(sim_res.scenarios),
            "status": "COMPLETED",
        },
        executed_at=datetime.utcnow(),
    ))

    # Lookup rules & clauses mapping for contract
    rule_clause_map = {}
    for r in rules_rec:
        rule_clause_map[r.rule_code] = r.clause_id

    # 2. Persist scenario executions & step traces
    for idx, sc_item in enumerate(sim_res.scenarios):
        sc_exec_id = f"SIM-SCEN-{uuid4().hex[:8].upper()}"
        db.add(ExecutionModel(
            id=sc_exec_id,
            contract_id=req.contract_id,
            scenario_name=f"Scenario: {sc_item.scenario_name}",
            input_variables=sc_item.variables,
            financial_impact=sc_item.financial_impact,
            summary_result={
                "difference_from_baseline": sc_item.difference_from_baseline,
                "percentage_change": sc_item.percentage_change,
                "summary": sc_item.calculation_summary
            },
            executed_at=datetime.utcnow(),
        ))

        # Re-run rule steps to save individual execution steps for audit trail
        from app.services.deterministic_rule_engine import DeterministicRuleEngine
        sc_exec_out = DeterministicRuleEngine.execute_rules(
            contract_id=req.contract_id,
            rules=legal_ir_list,
            variables=sc_item.variables,
            scenario_name=sc_item.scenario_name
        )

        for step in sc_exec_out.calculation_steps:
            db.add(ExecutionStepModel(
                id=f"STEP-{sc_exec_id}-{step.step_number}",
                execution_id=sc_exec_id,
                step_number=step.step_number,
                rule_code=step.rule_code,
                title=step.title,
                description=step.description,
                formula=step.formula,
                subtotal=step.subtotal,
                source_clause_id=rule_clause_map.get(step.rule_code),
            ))

    db.commit()

    AuditService.log_event(
        db=db,
        contract_id=req.contract_id,
        action="RUN_SIMULATION",
        details={
            "execution_id": baseline_exec_id,
            "baseline_impact": sim_res.baseline.financial_impact,
            "scenarios_count": len(sim_res.scenarios)
        }
    )

    return sim_res
