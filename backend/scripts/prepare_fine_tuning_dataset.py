# -*- coding: utf-8 -*-
"""
prepare_fine_tuning_dataset.py - LAWGIC Legal IR Fine-Tuning Dataset Generator

Generates a structured dataset for fine-tuning Phi-4-mini to extract exact
Legal IR JSON from raw legal contract clauses.

Usage:
    python scripts/prepare_fine_tuning_dataset.py
"""

import json
from pathlib import Path

DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "legal_ir_finetune_dataset.jsonl"
MODELFILE_PATH = Path(__file__).resolve().parent.parent / "data" / "Modelfile.phi4-lawgic"

SYSTEM_PROMPT = (
    "You are LAWGIC Legal IR Extractor, a specialized AI that parses contract clause text "
    "and converts legal terms into deterministic Legal IR JSON specifications strictly adhering to schema."
)

DATASET_SAMPLES = [
    {
        "clause_text": "Late payments beyond thirty (30) days from invoice date shall accrue interest at the rate of 1.5% per month, capped at a maximum of 15% of total invoice value.",
        "legal_ir": {
            "rule_id": "R-INTEREST-001",
            "type": "late_payment_interest",
            "title": "Late Payment Interest",
            "source": {"page": 1, "section": "3.1", "text": "Late payments beyond thirty (30) days..."},
            "conditions": [{"variable": "payment_delay_days", "operator": ">", "value": 30, "unit": "days"}],
            "actions": [{"type": "interest", "rate": 0.015, "period": "month", "grace_period_days": 30, "base_variable": "invoice_amount"}],
            "caps": {"max_percentage": 0.15, "max_amount": None}
        }
    },
    {
        "clause_text": "If delivery is delayed past the agreed milestone date by more than 10 calendar days, Seller shall pay liquidated damages of 2% of contract value per week of delay, up to a maximum penalty of 10%.",
        "legal_ir": {
            "rule_id": "R-PENALTY-002",
            "type": "delivery_delay_penalty",
            "title": "Delivery Delay Liquidated Damages",
            "source": {"page": 2, "section": "5.2", "text": "If delivery is delayed past the agreed milestone date..."},
            "conditions": [{"variable": "delivery_delay_days", "operator": ">", "value": 10, "unit": "days"}],
            "actions": [{"type": "penalty", "rate": 0.02, "period": "week", "grace_period_days": 10, "base_variable": "contract_value"}],
            "caps": {"max_percentage": 0.10, "max_amount": None}
        }
    },
    {
        "clause_text": "Buyer shall be entitled to a 5% volume discount on total contract value when order quantity reaches or exceeds 1,000 units.",
        "legal_ir": {
            "rule_id": "R-DISCOUNT-003",
            "type": "volume_discount",
            "title": "Volume Price Discount",
            "source": {"page": 2, "section": "4.1", "text": "Buyer shall be entitled to a 5% volume discount..."},
            "conditions": [{"variable": "order_quantity", "operator": ">=", "value": 1000, "unit": "units"}],
            "actions": [{"type": "discount", "rate": 0.05, "base_variable": "contract_value"}],
            "caps": {"max_percentage": None, "max_amount": None}
        }
    },
    {
        "clause_text": "Should monthly service availability fall below 99.5%, Service Provider shall credit ,000 per incident against the next monthly invoice, subject to a maximum credit limit of ,000 per billing cycle.",
        "legal_ir": {
            "rule_id": "R-SLA-004",
            "type": "sla_penalty",
            "title": "SLA Availability Breach Penalty",
            "source": {"page": 4, "section": "8.3", "text": "Should monthly service availability fall below 99.5%..."},
            "conditions": [{"variable": "sla_uptime_percent", "operator": "<", "value": 99.5, "unit": "%"}],
            "actions": [{"type": "sla_deduction", "amount": 5000.0, "base_variable": "monthly_invoice"}],
            "caps": {"max_percentage": None, "max_amount": 50000.0}
        }
    },
    {
        "clause_text": "Unit pricing shall increase by 3.5% annually if the national Consumer Price Index (CPI) inflation rate exceeds 2.0% over the preceding 12-month period.",
        "legal_ir": {
            "rule_id": "R-ESCALATION-005",
            "type": "price_escalation",
            "title": "Inflation Price Escalation",
            "source": {"page": 6, "section": "12.1", "text": "Unit pricing shall increase by 3.5% annually..."},
            "conditions": [{"variable": "inflation_rate_percent", "operator": ">", "value": 2.0, "unit": "%"}],
            "actions": [{"type": "escalation", "rate": 0.035, "base_variable": "contract_value"}],
            "caps": {"max_percentage": None, "max_amount": None}
        }
    }
]

def generate_dataset():
    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        for item in DATASET_SAMPLES:
            entry = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Extract Legal IR JSON for the following clause:\n\n\"{item['clause_text']}\""},
                    {"role": "assistant", "content": json.dumps(item["legal_ir"], indent=2)}
                ]
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"Dataset generated at: {DATASET_PATH}")

def generate_ollama_modelfile():
    modelfile_content = f"""FROM phi4-mini

SYSTEM "{SYSTEM_PROMPT}"

PARAMETER temperature 0.1
PARAMETER top_p 0.9
"""
    with open(MODELFILE_PATH, "w", encoding="utf-8") as f:
        f.write(modelfile_content)
    print(f"Ollama Modelfile created at: {MODELFILE_PATH}")

if __name__ == "__main__":
    generate_dataset()
    generate_ollama_modelfile()
