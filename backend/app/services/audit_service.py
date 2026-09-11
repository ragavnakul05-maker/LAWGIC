import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.schemas import AuditLogModel

class AuditService:
    @staticmethod
    def log_event(db: Session, contract_id: str, action: str, details: Dict[str, Any]):
        log_entry = AuditLogModel(
            id=f"AUDIT-{uuid.uuid4().hex[:8].upper()}",
            contract_id=contract_id,
            action=action,
            details=details,
            created_at=datetime.utcnow()
        )
        db.add(log_entry)
        db.commit()
        return log_entry
