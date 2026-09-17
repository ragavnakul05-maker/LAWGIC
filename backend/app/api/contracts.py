import os
import tempfile
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.config import MAX_UPLOAD_SIZE_MB
from app.core.security import get_current_user
from app.core.encryption import (
    encrypt_bytes,
    decrypt_bytes,
    secure_filename,
    validate_file_content,
    get_user_storage_path,
)
from app.models.schemas import ContractModel, ContractPageModel, ClauseModel, RuleModel, UserModel
from app.services.document_parser import DocumentService
from app.services.llm_service import LLMService
from app.services.rule_validation_engine import RuleValidationEngine
from app.services.decompiler_service import DecompilerService
from app.services.audit_service import AuditService

router = APIRouter(prefix="/contracts", tags=["Contracts"])

@router.post("/upload")
async def upload_contract(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Uploads contract document with enterprise security:
      - Enforces MAX_UPLOAD_SIZE_MB
      - Sanitizes filename to prevent directory traversal
      - Validates magic bytes / content signature against claimed extension
      - Encrypts file at rest with Fernet in user's private folder
      - Guarantees immediate cleanup of temporary parsing files
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    safe_filename = secure_filename(file.filename)
    file_ext = os.path.splitext(safe_filename)[1].lower()
    if file_ext not in [".pdf", ".docx", ".doc", ".txt"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload PDF, DOCX, or TXT."
        )

    # 1. Read and validate file size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Maximum allowed: {MAX_UPLOAD_SIZE_MB} MB"
        )

    # 2. Validate magic bytes signature against disguised executables / corrupt data
    validate_file_content(content, safe_filename)

    # 3. Store encrypted ciphertext in user's isolated private folder
    contract_id = f"CONTRACT-{uuid.uuid4().hex[:8].upper()}"
    user_storage_dir = get_user_storage_path(current_user.id, settings.UPLOAD_DIR)
    save_path = os.path.join(user_storage_dir, f"{contract_id}_{safe_filename}.enc")

    encrypted_bytes = encrypt_bytes(content)
    with open(save_path, "wb") as f:
        f.write(encrypted_bytes)

    # 4. Parse Document securely using temporary plaintext file with guaranteed cleanup
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
    try:
        temp_file.write(content)
        temp_file.flush()
        temp_file.close()
        parsed = DocumentService.parse_document(temp_file.name)
    finally:
        try:
            os.unlink(temp_file.name)
        except Exception:
            pass

    # 5. Save Contract Record
    title_clean = os.path.splitext(safe_filename)[0].replace("_", " ").title()
    contract_rec = ContractModel(
        id=contract_id,
        user_id=current_user.id,
        title=title_clean,
        filename=safe_filename,
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
        },
        user_id=current_user.id
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
def list_contracts(db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    contracts = db.query(ContractModel).filter(ContractModel.user_id == current_user.id).order_by(ContractModel.created_at.desc()).all()
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
def get_contract_detail(contract_id: str, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    c = db.query(ContractModel).filter(ContractModel.id == contract_id, ContractModel.user_id == current_user.id).first()
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

@router.get("/{contract_id}/download")
def download_contract_document(
    contract_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Secure document download endpoint:
      - Enforces strict user ownership (404/403)
      - Decrypts on-disk Fernet ciphertext in memory
      - Streams original file back to the authorized user
    """
    c = db.query(ContractModel).filter(
        ContractModel.id == contract_id,
        ContractModel.user_id == current_user.id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")

    if not os.path.exists(c.file_path):
        raise HTTPException(status_code=404, detail="Stored document file not found on server")

    with open(c.file_path, "rb") as f:
        encrypted_data = f.read()

    try:
        decrypted_data = decrypt_bytes(encrypted_data)
    except Exception:
        # Fallback in case a pre-existing legacy unencrypted file is being accessed
        decrypted_data = encrypted_data

    ext = os.path.splitext(c.filename)[1].lower()
    media_types = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".txt": "text/plain",
    }
    media_type = media_types.get(ext, "application/octet-stream")

    return Response(
        content=decrypted_data,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{c.filename}"',
            "X-Content-Type-Options": "nosniff",
        }
    )

