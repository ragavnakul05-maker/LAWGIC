import os
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, Base, engine
from app.models.schemas import (
    ContractModel, ContractPageModel, ClauseModel, RuleModel, ExecutionModel, ExecutionStepModel, AuditLogModel, UserModel
)
from app.core.security import hash_password
from app.sample_data.sample_contract import SAMPLE_CONTRACT_TEXT
from app.services.document_parser import DocumentService
from app.services.llm_service import LLMService
from app.services.rule_validation_engine import RuleValidationEngine
from app.services.decompiler_service import DecompilerService
from app.services.deterministic_rule_engine import DeterministicRuleEngine

def seed_database():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # Seed demo users if not present
        demo_users = [
            {
                "id": "USER-DEMO-001",
                "email": "admin@lawgic.ai",
                "full_name": "Dr. Eleanor Vance",
                "role": "Chief Legal Officer & General Counsel",
                "password": "password123",
            },
            {
                "id": "USER-DEMO-002",
                "email": "counsel@lawgic.ai",
                "full_name": "Marcus Sterling",
                "role": "Senior Commercial Legal Counsel",
                "password": "password123",
            },
        ]
        for u in demo_users:
            if not db.query(UserModel).filter(UserModel.email == u["email"]).first():
                db.add(UserModel(
                    id=u["id"],
                    email=u["email"],
                    full_name=u["full_name"],
                    role=u["role"],
                    hashed_password=hash_password(u["password"]),
                    is_active=True,
                ))
        db.commit()

        # Check if already seeded
        existing = db.query(ContractModel).filter(ContractModel.id == "DEMO-CONTRACT-001").first()
        if existing:
            print("[Seed] Database already seeded with DEMO-CONTRACT-001.")
            return

        print("[Seed] Seeding sample contract and rules into database...")

        # 1. Save Contract Record
        contract = ContractModel(
            id="DEMO-CONTRACT-001",
            title="ABC Tech Master Supplier Agreement",
            filename="ABC_Tech_Supplier_Agreement.pdf",
            file_type="PDF",
            file_path="uploads/ABC_Tech_Supplier_Agreement.pdf",
            page_count=5,
            status="ANALYZED",
            created_at=datetime.utcnow()
        )
        db.add(contract)

        # 2. Parse sample text into pages
        parsed = DocumentService._parse_txt(
            # Save temporary file for reference
            _write_temp_contract()
        )

        for p in parsed["pages"]:
            page_rec = ContractPageModel(
                id=f"PAGE-{contract.id}-{p['page_number']}",
                contract_id=contract.id,
                page_number=p["page_number"],
                text_content=p["text"]
            )
            db.add(page_rec)

        # 3. Create Clauses & Legal IR Rules
        rules_for_exec = []
        clause_index = 1

        for c_data in parsed["clauses"]:
            clause_id = f"CLAUSE-{contract.id}-{clause_index:03d}"
            clause_rec = ClauseModel(
                id=clause_id,
                contract_id=contract.id,
                page_number=c_data["page_number"],
                section_number=c_data["section_number"],
                clause_number=c_data["section_number"],
                title=c_data["title"],
                original_text=c_data["clause_text"],
                clause_type=c_data["clause_type"]
            )
            db.add(clause_rec)

            # Generate Legal IR
            ir = LLMService.extract_legal_ir(
                clause_text=c_data["clause_text"],
                page_number=c_data["page_number"],
                section_number=c_data["section_number"],
                clause_type=c_data["clause_type"],
                rule_index=clause_index
            )
            rules_for_exec.append(ir)

            # Validate rule
            val_res = RuleValidationEngine.validate_rule(ir)

            # Decompile rule
            human_exp = DecompilerService.decompile_to_human(ir)

            rule_rec = RuleModel(
                id=f"RULE-{contract.id}-{ir.rule_id}",
                contract_id=contract.id,
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

        db.commit()

        # 4. Seed Initial Sample Execution
        sample_input = {
            "contract_value": 1000000.0,
            "invoice_amount": 1000000.0,
            "payment_delay_days": 35,
            "delivery_delay_days": 24,
            "order_quantity": 1200,
            "sla_uptime_percent": 99.1,
            "inflation_rate_percent": 2.5
        }

        exec_res = DeterministicRuleEngine.execute_rules(
            contract_id=contract.id,
            rules=rules_for_exec,
            variables=sample_input,
            scenario_name="Baseline Production Run"
        )

        exec_rec = ExecutionModel(
            id=exec_res.execution_id,
            contract_id=contract.id,
            scenario_name="Baseline Production Run",
            input_variables=sample_input,
            financial_impact=exec_res.total_financial_impact,
            summary_result=exec_res.summary,
            executed_at=datetime.utcnow()
        )
        db.add(exec_rec)

        for step in exec_res.calculation_steps:
            step_rec = ExecutionStepModel(
                id=f"STEP-{exec_rec.id}-{step.step_number}",
                execution_id=exec_rec.id,
                step_number=step.step_number,
                rule_code=step.rule_code,
                title=step.title,
                description=step.description,
                formula=step.formula,
                subtotal=step.subtotal,
                source_clause_id=f"CLAUSE-{contract.id}-{step.step_number:03d}"
            )
            db.add(step_rec)

        # 5. Log Seed Audit
        audit = AuditLogModel(
            id=f"AUDIT-SEED-001",
            contract_id=contract.id,
            action="INITIAL_SEED",
            details={
                "message": "Sample contract, Legal IR rules, and initial execution successfully seeded.",
                "total_clauses": len(parsed["clauses"]),
                "total_rules": len(rules_for_exec)
            },
            created_at=datetime.utcnow()
        )
        db.add(audit)

        db.commit()
        print("[Seed] Seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"[Seed] Error during seeding: {e}")
    finally:
        db.close()

def _write_temp_contract() -> str:
    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    filepath = os.path.join(uploads_dir, "ABC_Tech_Supplier_Agreement.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(SAMPLE_CONTRACT_TEXT)
    return filepath

if __name__ == "__main__":
    seed_database()
