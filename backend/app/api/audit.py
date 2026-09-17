from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.schemas import ExecutionModel, ExecutionStepModel, AuditLogModel, ContractModel, ClauseModel, RuleModel, UserModel
from app.services.decompiler_service import DecompilerService
from app.services.report_export_service import ReportExportService

router = APIRouter(prefix="/audit", tags=["Audit"])

@router.get("/logs")
def get_audit_logs(contract_id: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    user_contracts = db.query(ContractModel.id).filter(ContractModel.user_id == current_user.id).all()
    user_contract_ids = [c[0] for c in user_contracts]
    if not user_contract_ids:
        return []

    if contract_id:
        if contract_id not in user_contract_ids:
            raise HTTPException(status_code=404, detail="Contract not found")
        query = db.query(AuditLogModel).filter(AuditLogModel.contract_id == contract_id)
    else:
        query = db.query(AuditLogModel).filter(AuditLogModel.contract_id.in_(user_contract_ids))
    
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
    """
    ex = db.query(ExecutionModel).filter(ExecutionModel.id == execution_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Execution record not found")

    contract = db.query(ContractModel).filter(
        ContractModel.id == ex.contract_id,
        ContractModel.user_id == current_user.id
    ).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Execution record not found")

    steps = db.query(ExecutionStepModel).filter(ExecutionStepModel.execution_id == execution_id).order_by(ExecutionStepModel.step_number.asc()).all()

    step_payloads = []
    for s in steps:
        clause = db.query(ClauseModel).filter(ClauseModel.id == s.source_clause_id).first() if s.source_clause_id else None
        rule = db.query(RuleModel).filter(RuleModel.rule_code == s.rule_code, RuleModel.contract_id == ex.contract_id).first()
        rule_ir = rule.ir_json if rule else None
        rule_type = rule.rule_type if rule else "general_clause"

        flow_data = DecompilerService.get_step_flow_data(
            rule_code=s.rule_code,
            rule_title=s.title,
            rule_type=rule_type,
            rule_ir=rule_ir,
            subtotal=s.subtotal,
            formula=s.formula,
            input_vars=ex.input_variables or {}
        )

        step_payloads.append({
            "step_number": s.step_number,
            "rule_code": s.rule_code,
            "rule_title": s.title,
            "rule_type": rule_type,
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
            "rule_ir": rule_ir,
            "human_explanation": rule.human_explanation if rule else None,
            "decompiled_explanation": flow_data.get("decompiled_explanation"),
            "flow_data": flow_data,
            "validation_status": rule.validation_status if rule else "VALID"
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


@router.get("/executions/{execution_id}/export")
def export_execution_audit(
    execution_id: str,
    format: str = "html",
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Exports the complete deterministic audit trail as:
      - 'html' or 'pdf': Executive, print-optimized report with clause citations & KPI cards
      - 'csv': RFC-4180 calculation ledger with math breakdowns and clause references
      - 'json': Cryptographically verified audit package with SHA-256 integrity hash
    """
    trail = get_execution_audit_trail(execution_id=execution_id, db=db, current_user=current_user)
    fmt = format.lower().strip()

    if fmt == "csv":
        csv_content = ReportExportService.generate_audit_csv(trail)
        filename = f"audit_ledger_{execution_id}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    elif fmt == "json":
        json_content = ReportExportService.generate_audit_json(trail, user_id=current_user.id)
        filename = f"audit_dossier_{execution_id}.json"
        return JSONResponse(
            content=json_content,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    elif fmt in ["html", "pdf"]:
        html_content = ReportExportService.generate_audit_html_report(
            trail,
            user_name=current_user.full_name or "Legal Counsel"
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

