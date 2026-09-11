import os
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.models.schemas import ContractModel, ContractPageModel, ClauseModel, RuleModel
from app.services.document_parser import DocumentService
from app.services.llm_service import LLMService
from app.services.rule_validation_engine import RuleValidationEngine
from app.services.decompiler_service import DecompilerService
from app.services.audit_service import AuditService

router = APIRouter(prefix="/contracts", tags=["Contracts"])

@router.post("/upload")
async def upload_contract(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Uploads contract document (PDF, DOCX, TXT), parses text, segments clauses, and extracts Legal IR.
    """
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in [".pdf", ".docx", ".doc", ".txt"]:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF, DOCX, or TXT.")

    contract_id = f"CONTRACT-{uuid.uuid4().hex[:8].upper()}"
    save_path = os.path.join(settings.UPLOAD_DIR, f"{contract_id}_{file.filename}")

    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 1. Parse Document
    parsed = DocumentService.parse_document(save_path)

    # 2. Save Contract Record
    title_clean = os.path.splitext(file.filename)[0].replace("_", " ").title()
    contract_rec = ContractModel(
        id=contract_id,
        title=title_clean,
        filename=file.filename,
        file_type=file_ext.replace(".", "").upper(),
        file_path=save_path,
        page_count=parsed["page_count"],
        status="PARSED",
        created_at=datetime.utcnow()
    )
    db.add(contract_rec)

    # 3. Save Pages
    for p in parsed["pages"]:
        page_rec = ContractPageModel(
            id=f"PAGE-{contract_id}-{p['page_number']}",
            contract_id=contract_id,
            page_number=p["page_number"],
            text_content=p["text"]
        )
        db.add(page_rec)

    # 4. Extract Clauses & Generate Structured Legal IR
    clause_index = 1
    extracted_rules_count = 0

    for c_data in parsed["clauses"]:
        clause_id = f"CLAUSE-{contract_id}-{clause_index:03d}"
        clause_rec = ClauseModel(
            id=clause_id,
            contract_id=contract_id,
            page_number=c_data["page_number"],
            section_number=c_data["section_number"],
            clause_number=c_data["section_number"],
            title=c_data["title"],
            original_text=c_data["clause_text"],
            clause_type=c_data["clause_type"]
        )
        db.add(clause_rec)

        # Generate Legal IR JSON
        ir = LLMService.extract_legal_ir(
            clause_text=c_data["clause_text"],
            page_number=c_data["page_number"],
            section_number=c_data["section_number"],
            clause_type=c_data["clause_type"],
            rule_index=clause_index
        )

        # Validate Rule
        val_res = RuleValidationEngine.validate_rule(ir)

        # Decompile to natural language
        human_exp = DecompilerService.decompile_to_human(ir)

        rule_rec = RuleModel(
            id=f"RULE-{contract_id}-{ir.rule_id}",
            contract_id=contract_id,
            clause_id=clause_id,
            rule_code=ir.rule_id,
            rule_type=ir.type,
            title=ir.title,
            ir_json=ir.dict(),
            validation_status=val_res.status,
            review_notes="; ".join(val_res.issues) if val_res.issues else "Validated successfully.",
            human_explanation=human_exp,
            created_at=datetime.utcnow()
        )
        db.add(rule_rec)
        clause_index += 1
        extracted_rules_count += 1

    contract_rec.status = "ANALYZED"
    db.commit()

    # Log Audit
    AuditService.log_event(
        db=db,
        contract_id=contract_id,
        action="UPLOAD_AND_ANALYZE",
        details={
            "filename": file.filename,
            "pages": parsed["page_count"],
            "clauses_extracted": len(parsed["clauses"]),
            "rules_generated": extracted_rules_count
        }
    )

    return {
        "message": "Contract successfully uploaded, parsed, and converted to Legal IR.",
        "contract_id": contract_id,
        "title": title_clean,
        "pages": parsed["page_count"],
        "clauses_count": len(parsed["clauses"]),
        "rules_count": extracted_rules_count
    }

@router.get("")
def list_contracts(db: Session = Depends(get_db)):
    contracts = db.query(ContractModel).order_by(ContractModel.created_at.desc()).all()
    res = []
    for c in contracts:
        rules_count = db.query(RuleModel).filter(RuleModel.contract_id == c.id).count()
        clauses_count = db.query(ClauseModel).filter(ClauseModel.contract_id == c.id).count()
        res.append({
            "id": c.id,
            "title": c.title,
            "filename": c.filename,
            "file_type": c.file_type,
            "page_count": c.page_count,
            "clauses_count": clauses_count,
            "rules_count": rules_count,
            "status": c.status,
            "created_at": c.created_at.isoformat()
        })
    return res

@router.get("/{contract_id}")
def get_contract_detail(contract_id: str, db: Session = Depends(get_db)):
    c = db.query(ContractModel).filter(ContractModel.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")

    pages = db.query(ContractPageModel).filter(ContractPageModel.contract_id == contract_id).order_by(ContractPageModel.page_number.asc()).all()
    clauses = db.query(ClauseModel).filter(ClauseModel.contract_id == contract_id).all()
    rules = db.query(RuleModel).filter(RuleModel.contract_id == contract_id).all()

    rules_by_clause = {r.clause_id: r for r in rules}

    clause_payloads = []
    for cl in clauses:
        rule_rec = rules_by_clause.get(cl.id)
        clause_payloads.append({
            "id": cl.id,
            "page_number": cl.page_number,
            "section_number": cl.section_number,
            "title": cl.title,
            "original_text": cl.original_text,
            "clause_type": cl.clause_type,
            "rule": {
                "id": rule_rec.id,
                "rule_code": rule_rec.rule_code,
                "title": rule_rec.title,
                "ir_json": rule_rec.ir_json,
                "validation_status": rule_rec.validation_status,
                "review_notes": rule_rec.review_notes,
                "human_explanation": rule_rec.human_explanation
            } if rule_rec else None
        })

    return {
        "id": c.id,
        "title": c.title,
        "filename": c.filename,
        "file_type": c.file_type,
        "page_count": c.page_count,
        "status": c.status,
        "created_at": c.created_at.isoformat(),
        "pages": [{"page_number": p.page_number, "text_content": p.text_content} for p in pages],
        "clauses": clause_payloads
    }
