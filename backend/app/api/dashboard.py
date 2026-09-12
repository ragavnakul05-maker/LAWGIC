from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.schemas import ContractModel, ClauseModel, RuleModel, ExecutionModel, AuditLogModel, UserModel

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    total_contracts = db.query(ContractModel).count()
    clauses_extracted = db.query(ClauseModel).count()
    active_rules = db.query(RuleModel).filter(RuleModel.validation_status == "VALID").count()
    pending_reviews = db.query(RuleModel).filter(RuleModel.validation_status == "NEEDS_REVIEW").count()

    recent_executions = db.query(ExecutionModel).order_by(ExecutionModel.executed_at.desc()).limit(5).all()
    potential_penalties = sum(e.financial_impact for e in recent_executions if e.financial_impact > 0)
    potential_discounts = sum(abs(e.financial_impact) for e in recent_executions if e.financial_impact < 0)

    recent_contracts = db.query(ContractModel).order_by(ContractModel.created_at.desc()).limit(5).all()
    contract_items = []
    for c in recent_contracts:
        r_count = db.query(RuleModel).filter(RuleModel.contract_id == c.id).count()
        contract_items.append({
            "id": c.id,
            "title": c.title,
            "filename": c.filename,
            "file_type": c.file_type,
            "rules_count": r_count,
            "created_at": c.created_at.isoformat()
        })

    alerts = [
        {
            "id": "ALT-001",
            "type": "WARNING",
            "title": "Rule Requires Review",
            "message": "Section 5.2 Auto-Renewal requires legal review due to vague 60-day notice period.",
            "contract_id": "DEMO-CONTRACT-001",
            "rule_code": "R005"
        },
        {
            "id": "ALT-002",
            "type": "DANGER",
            "title": "Penalty Triggered",
            "message": "Delivery delay (24 days) triggered liquidated damages penalty of $40,000.",
            "contract_id": "DEMO-CONTRACT-001",
            "rule_code": "R002"
        },
        {
            "id": "ALT-003",
            "type": "SUCCESS",
            "title": "Volume Discount Triggered",
            "message": "Order quantity (1,200 units) achieved 5% bulk discount (-$50,000).",
            "contract_id": "DEMO-CONTRACT-001",
            "rule_code": "R003"
        },
        {
            "id": "ALT-004",
            "type": "INFO",
            "title": "Upcoming Renewal Deadline",
            "message": "60-day non-renewal notice window opens in 15 days.",
            "contract_id": "DEMO-CONTRACT-001",
            "rule_code": "R005"
        }
    ]

    return {
        "metrics": {
            "total_contracts": total_contracts,
            "clauses_extracted": clauses_extracted,
            "active_rules": active_rules,
            "pending_reviews": pending_reviews,
            "potential_penalties": round(potential_penalties, 2),
            "potential_discounts": round(potential_discounts, 2)
        },
        "recent_contracts": contract_items,
        "alerts": alerts
    }

@router.get("/breakdown")
def get_penalty_breakdown(db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """
    Returns penalty and discount totals broken down per contract, with per-rule
    details (rule code, title, source clause section + text, individual impact).
    Used by the dashboard drill-down popup modal.
    """
    contracts = db.query(ContractModel).order_by(ContractModel.created_at.desc()).all()
    result = []
    for c in contracts:
        executions = db.query(ExecutionModel).filter(ExecutionModel.contract_id == c.id).all()
        total_penalties = sum(e.financial_impact for e in executions if e.financial_impact > 0)
        total_discounts = sum(abs(e.financial_impact) for e in executions if e.financial_impact < 0)

        # Build per-rule breakdown from rules attached to this contract
        rules = db.query(RuleModel).filter(RuleModel.contract_id == c.id).all()
        rule_details = []
        for r in rules:
            clause = db.query(ClauseModel).filter(ClauseModel.id == r.clause_id).first()
            # Find the most recent execution step for this rule
            latest_impact = None
            for ex in sorted(executions, key=lambda e: e.executed_at, reverse=True):
                from app.models.schemas import ExecutionStepModel
                step = db.query(ExecutionStepModel).filter(
                    ExecutionStepModel.execution_id == ex.id,
                    ExecutionStepModel.rule_code == r.rule_code
                ).first()
                if step:
                    latest_impact = step.subtotal
                    break
            rule_details.append({
                "rule_code": r.rule_code,
                "rule_type": r.rule_type,
                "title": r.title,
                "validation_status": r.validation_status,
                "human_explanation": r.human_explanation,
                "latest_impact": latest_impact,
                "source_clause": {
                    "section": clause.section_number if clause else None,
                    "page": clause.page_number if clause else None,
                    "text": (clause.original_text[:200] + "…") if clause and len(clause.original_text) > 200 else (clause.original_text if clause else None),
                },
            })

        result.append({
            "id": c.id,
            "title": c.title,
            "filename": c.filename,
            "total_penalties": round(total_penalties, 2),
            "total_discounts": round(total_discounts, 2),
            "execution_count": len(executions),
            "created_at": c.created_at.isoformat(),
            "rules": rule_details,
        })
    return {"contracts": result}
