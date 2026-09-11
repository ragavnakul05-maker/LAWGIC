from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.schemas import RuleModel, ClauseModel, LegalIR, RuleExecutionInput, RuleExecutionOutput
from app.services.rule_validation_engine import RuleValidationEngine
from app.services.deterministic_rule_engine import DeterministicRuleEngine
from app.services.decompiler_service import DecompilerService
from app.services.audit_service import AuditService

router = APIRouter(prefix="/rules", tags=["Rules"])

@router.get("")
def list_all_rules(rule_type: Optional[str] = None, validation_status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(RuleModel)
    if rule_type:
        query = query.filter(RuleModel.rule_type == rule_type)
    if validation_status:
        query = query.filter(RuleModel.validation_status == validation_status)
    
    rules = query.order_by(RuleModel.rule_code.asc()).all()
    res = []
    for r in rules:
        clause = db.query(ClauseModel).filter(ClauseModel.id == r.clause_id).first()
        res.append({
            "id": r.id,
            "contract_id": r.contract_id,
            "clause_id": r.clause_id,
            "rule_code": r.rule_code,
            "rule_type": r.rule_type,
            "title": r.title,
            "ir_json": r.ir_json,
            "validation_status": r.validation_status,
            "review_notes": r.review_notes,
            "human_explanation": r.human_explanation,
            "created_at": r.created_at.isoformat(),
            "source": {
                "page": clause.page_number if clause else 1,
                "section": clause.section_number if clause else "1.0",
                "clause_text": clause.original_text if clause else ""
            }
        })
    return res

@router.get("/{rule_id}")
def get_rule_detail(rule_id: str, db: Session = Depends(get_db)):
    r = db.query(RuleModel).filter(RuleModel.id == rule_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Rule not found")
    clause = db.query(ClauseModel).filter(ClauseModel.id == r.clause_id).first()

    return {
        "id": r.id,
        "contract_id": r.contract_id,
        "clause_id": r.clause_id,
        "rule_code": r.rule_code,
        "rule_type": r.rule_type,
        "title": r.title,
        "ir_json": r.ir_json,
        "validation_status": r.validation_status,
        "review_notes": r.review_notes,
        "human_explanation": r.human_explanation,
        "created_at": r.created_at.isoformat(),
        "source_clause": {
            "page": clause.page_number if clause else 1,
            "section": clause.section_number if clause else "1.0",
            "original_text": clause.original_text if clause else ""
        }
    }

@router.post("/{rule_id}/validate")
def validate_rule(rule_id: str, db: Session = Depends(get_db)):
    r = db.query(RuleModel).filter(RuleModel.id == rule_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Rule not found")

    ir_obj = LegalIR(**r.ir_json)
    val_res = RuleValidationEngine.validate_rule(ir_obj)

    r.validation_status = val_res.status
    r.review_notes = "; ".join(val_res.issues) if val_res.issues else "Validated successfully."
    db.commit()

    AuditService.log_event(
        db=db,
        contract_id=r.contract_id,
        action="VALIDATE_RULE",
        details={"rule_id": r.id, "rule_code": r.rule_code, "status": val_res.status, "issues": val_res.issues}
    )

    return val_res

@router.post("/execute", response_model=RuleExecutionOutput)
def execute_contract_rules(input_data: RuleExecutionInput, db: Session = Depends(get_db)):
    """
    Executes rules deterministically against input variables using pure Python calculations.
    """
    rules_rec = db.query(RuleModel).filter(RuleModel.contract_id == input_data.contract_id).all()
    if not rules_rec:
        raise HTTPException(status_code=404, detail=f"No rules found for contract {input_data.contract_id}")

    legal_ir_list = [LegalIR(**r.ir_json) for r in rules_rec]
    
    exec_output = DeterministicRuleEngine.execute_rules(
        contract_id=input_data.contract_id,
        rules=legal_ir_list,
        variables=input_data.variables
    )

    AuditService.log_event(
        db=db,
        contract_id=input_data.contract_id,
        action="EXECUTE_RULES",
        details={
            "execution_id": exec_output.execution_id,
            "financial_impact": exec_output.total_financial_impact,
            "applied_rules": exec_output.applied_rules
        }
    )

    return exec_output
