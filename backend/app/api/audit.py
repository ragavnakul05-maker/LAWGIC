from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.schemas import ExecutionModel, ExecutionStepModel, AuditLogModel, ContractModel, ClauseModel, RuleModel, UserModel

router = APIRouter(prefix="/audit", tags=["Audit"])

@router.get("/logs")
def get_audit_logs(contract_id: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    query = db.query(AuditLogModel)
    if contract_id:
        query = query.filter(AuditLogModel.contract_id == contract_id)
    
    logs = query.order_by(AuditLogModel.created_at.desc()).limit(limit).all()
    res = []
    for l in logs:
        contract = db.query(ContractModel).filter(ContractModel.id == l.contract_id).first()
        res.append({
            "id": l.id,
            "contract_id": l.contract_id,
            "contract_title": contract.title if contract else l.contract_id,
            "action": l.action,
            "details": l.details,
            "created_at": l.created_at.isoformat()
        })
    return res

@router.get("/executions/{execution_id}")
def get_execution_audit_trail(execution_id: str, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """
    Returns full audit trail for an execution:
    Contract -> Clause -> Rule -> Input -> Execution Steps -> Financial Result -> Source Evidence.
    Includes plain English legal decompilation for backtracking.
    """
    from app.services.decompiler_service import DecompilerService
    from app.models.schemas import LegalIR

    ex = db.query(ExecutionModel).filter(ExecutionModel.id == execution_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Execution record not found")

    steps = db.query(ExecutionStepModel).filter(ExecutionStepModel.execution_id == execution_id).order_by(ExecutionStepModel.step_number.asc()).all()
    contract = db.query(ContractModel).filter(ContractModel.id == ex.contract_id).first()

    step_payloads = []
    for s in steps:
        rule = db.query(RuleModel).filter(RuleModel.rule_code == s.rule_code, RuleModel.contract_id == ex.contract_id).first()
        clause = None
        if s.source_clause_id:
            clause = db.query(ClauseModel).filter(ClauseModel.id == s.source_clause_id).first()
        elif rule and rule.clause_id:
            clause = db.query(ClauseModel).filter(ClauseModel.id == rule.clause_id).first()

        decompiled_text = None
        if rule and rule.ir_json:
            try:
                decompiled_text = DecompilerService.decompile_to_human(LegalIR(**rule.ir_json))
            except Exception:
                decompiled_text = rule.human_explanation

        step_payloads.append({
            "step_number": s.step_number,
            "rule_code": s.rule_code,
            "rule_title": s.title,
            "description": s.description,
            "formula": s.formula,
            "subtotal": s.subtotal,
            "source_clause": {
                "id": clause.id if clause else None,
                "page": clause.page_number if clause else 1,
                "section": clause.section_number if clause else "1.0",
                "title": clause.title if clause else "Clause",
                "original_text": clause.original_text if clause else ""
            } if clause else None,
            "rule_ir": rule.ir_json if rule else None,
            "human_explanation": rule.human_explanation if rule else None,
            "decompiled_text": decompiled_text,
        })

    return {
        "execution_id": ex.id,
        "contract_id": ex.contract_id,
        "contract_title": contract.title if contract else ex.contract_id,
        "scenario_name": ex.scenario_name,
        "input_variables": ex.input_variables,
        "financial_impact": ex.financial_impact,
        "summary": ex.summary_result,
        "executed_at": ex.executed_at.isoformat(),
        "steps": step_payloads
    }
