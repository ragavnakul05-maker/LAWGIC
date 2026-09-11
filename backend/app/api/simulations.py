from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.schemas import RuleModel, LegalIR, SimulationRequest, SimulationResponse
from app.services.simulation_engine import SimulationEngine
from app.services.audit_service import AuditService

router = APIRouter(prefix="/simulations", tags=["Simulations"])

@router.post("/run", response_model=SimulationResponse)
def run_simulation(req: SimulationRequest, db: Session = Depends(get_db)):
    """
    Executes what-if scenario simulations reusing the exact deterministic rule engine.
    Zero LLM calls during calculations.
    """
    rules_rec = db.query(RuleModel).filter(RuleModel.contract_id == req.contract_id).all()
    if not rules_rec:
        raise HTTPException(status_code=404, detail=f"No rules found for contract {req.contract_id}")

    legal_ir_list = [LegalIR(**r.ir_json) for r in rules_rec]

    scenarios_payload = [sc.dict() for sc in req.scenarios]

    sim_res = SimulationEngine.run_simulation(
        contract_id=req.contract_id,
        rules=legal_ir_list,
        baseline_variables=req.baseline_variables,
        scenarios_input=scenarios_payload
    )

    AuditService.log_event(
        db=db,
        contract_id=req.contract_id,
        action="RUN_SIMULATION",
        details={
            "baseline_impact": sim_res.baseline.financial_impact,
            "scenarios_count": len(sim_res.scenarios)
        }
    )

    return sim_res
