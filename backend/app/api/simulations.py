from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.schemas import (
    RuleModel, LegalIR, SimulationRequest, SimulationResponse,
    ExecutionModel, ExecutionStepModel, UserModel,
)
from app.services.simulation_engine import SimulationEngine
from app.services.audit_service import AuditService

router = APIRouter(prefix="/simulations", tags=["Simulations"])

@router.post("/run", response_model=SimulationResponse)
def run_simulation(req: SimulationRequest, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """
    Executes what-if scenario simulations reusing the exact deterministic rule engine.
    Zero LLM calls during calculations. Results persisted for Audit trail.
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

    # Fix 5b: Persist baseline simulation execution so Audit trail is complete
    from uuid import uuid4
    baseline_exec_id = f"SIM-{uuid4().hex[:8].upper()}"
    exec_rec = ExecutionModel(
        id=baseline_exec_id,
        contract_id=req.contract_id,
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
        }
    )

    return sim_res
