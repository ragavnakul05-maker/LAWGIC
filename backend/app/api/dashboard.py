from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.schemas import ContractModel, ClauseModel, RuleModel, ExecutionModel, AuditLogModel

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
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
