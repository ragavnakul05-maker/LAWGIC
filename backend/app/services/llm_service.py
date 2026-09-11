import json
import re
import requests
from typing import Dict, Any, List
from app.core.config import settings
from app.models.schemas import LegalIR, RuleSourceInfo, RuleCondition, RuleAction, RuleCaps

class LLMService:
    @staticmethod
    def extract_legal_ir(clause_text: str, page_number: int, section_number: str, clause_type: str, rule_index: int = 1) -> LegalIR:
        """
        Translates natural language clause text into structured Legal IR JSON.
        Uses external LLM provider if configured, or deterministic structured parser fallback.
        """
        if settings.LLM_PROVIDER in ["openai", "gemini"] and settings.LLM_API_KEY:
            try:
                return LLMService._call_external_llm(clause_text, page_number, section_number, clause_type, rule_index)
            except Exception as e:
                print(f"[LLMService] External LLM call failed ({e}), falling back to structured IR extractor.")
        
        return LLMService._structured_fallback_extractor(clause_text, page_number, section_number, clause_type, rule_index)

    @staticmethod
    def _call_external_llm(clause_text: str, page: int, section: str, clause_type: str, idx: int) -> LegalIR:
        prompt = f"""
You are a legal AI architecture parser. Your job is to convert natural language contractual clauses into machine-readable JSON Legal IR.

CLAUSE TEXT: "{clause_text}"
PAGE: {page}
SECTION: {section}
TYPE: {clause_type}

Return ONLY valid JSON matching this schema:
{{
  "rule_id": "R{idx:03d}",
  "type": "{clause_type}",
  "title": "Short Descriptive Title",
  "source": {{
    "page": {page},
    "section": "{section}",
    "clause_number": "{section}",
    "text": "{clause_text}"
  }},
  "conditions": [
    {{
      "variable": "payment_delay_days | delivery_delay_days | order_quantity | sla_uptime_percent",
      "operator": "> | >= | < | <= | ==",
      "value": 30,
      "unit": "days | percent | units"
    }}
  ],
  "actions": [
    {{
      "type": "interest | penalty | discount | sla_deduction | escalation",
      "rate": 0.015,
      "amount": null,
      "period": "month | week | day | flat",
      "grace_period_days": 10,
      "base_variable": "invoice_amount | contract_value | base_rate"
    }}
  ],
  "caps": {{
    "max_amount": null,
    "max_percentage": 0.10,
    "min_amount": null
  }},
  "ambiguity_flag": false,
  "review_reason": null
}}
"""
        if settings.LLM_PROVIDER == "openai":
            headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": settings.LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            res_json = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(res_json)
            return LegalIR(**data)
            
        elif settings.LLM_PROVIDER == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.LLM_MODEL}:generateContent?key={settings.LLM_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"response_mime_type": "application/json"}
            }
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            res_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(res_text)
            return LegalIR(**data)

        raise ValueError("Unsupported provider")

    @staticmethod
    def _structured_fallback_extractor(text: str, page: int, section: str, clause_type: str, idx: int) -> LegalIR:
        """
        High-precision regex/keyword structured extractor that generates clean JSON Legal IR.
        """
        text_lower = text.lower()
        rule_code = f"R{idx:03d}"
        source = RuleSourceInfo(page=page, section=section, clause_number=section, text=text)

        # 1. Late Payment Interest Clause
        if "interest" in text_lower or "late payment" in text_lower:
            days = 30
            match_days = re.search(r'(\d+)\s*days', text_lower)
            if match_days:
                days = int(match_days.group(1))

            rate = 0.015 # default 1.5%
            match_rate = re.search(r'(\d+(?:\.\d+)?)\s*%', text_lower)
            if match_rate:
                rate = float(match_rate.group(1)) / 100.0

            return LegalIR(
                rule_id=rule_code,
                type="late_payment_interest",
                title="Late Payment Interest Charge",
                source=source,
                conditions=[
                    RuleCondition(variable="payment_delay_days", operator=">", value=days, unit="days")
                ],
                actions=[
                    RuleAction(
                        type="interest",
                        rate=rate,
                        period="month" if "month" in text_lower else "day",
                        grace_period_days=days,
                        base_variable="invoice_amount",
                        description=f"{rate*100}% interest per month on delayed payment beyond {days} days"
                    )
                ],
                caps=RuleCaps(max_percentage=0.15),
                ambiguity_flag=False
            )

        # 2. Delivery Delay Penalty Clause
        elif "delay" in text_lower or "liquidated damages" in text_lower or "delivery" in text_lower:
            threshold_days = 10
            match_threshold = re.search(r'(\d+)\s*days', text_lower)
            if match_threshold:
                threshold_days = int(match_threshold.group(1))

            rate = 0.02 # default 2%
            rates = re.findall(r'(\d+(?:\.\d+)?)\s*%', text_lower)
            if rates:
                rate = float(rates[0]) / 100.0

            cap_pct = 0.10
            if len(rates) > 1:
                cap_pct = float(rates[1]) / 100.0

            return LegalIR(
                rule_id=rule_code,
                type="delivery_delay_penalty",
                title="Delivery Delay Penalty & Liquidated Damages",
                source=source,
                conditions=[
                    RuleCondition(variable="delivery_delay_days", operator=">", value=threshold_days, unit="days")
                ],
                actions=[
                    RuleAction(
                        type="penalty",
                        rate=rate,
                        period="week",
                        grace_period_days=threshold_days,
                        base_variable="contract_value",
                        description=f"{rate*100}% penalty of contract value per week of delay after {threshold_days} days"
                    )
                ],
                caps=RuleCaps(max_percentage=cap_pct),
                ambiguity_flag=False
            )

        # 3. Volume Discount Clause
        elif "discount" in text_lower or "volume" in text_lower or "quantity" in text_lower:
            units = 1000
            match_units = re.search(r'(\d+(?:,\d+)?)\s*(?:units|items|order)', text_lower)
            if match_units:
                units = int(match_units.group(1).replace(",", ""))

            discount_rate = 0.05
            match_rate = re.search(r'(\d+(?:\.\d+)?)\s*%', text_lower)
            if match_rate:
                discount_rate = float(match_rate.group(1)) / 100.0

            return LegalIR(
                rule_id=rule_code,
                type="volume_discount",
                title="Tiered Volume Discount",
                source=source,
                conditions=[
                    RuleCondition(variable="order_quantity", operator=">=", value=units, unit="units")
                ],
                actions=[
                    RuleAction(
                        type="discount",
                        rate=discount_rate,
                        base_variable="contract_value",
                        description=f"{discount_rate*100}% discount applied to order quantity >= {units} units"
                    )
                ],
                caps=RuleCaps(),
                ambiguity_flag=False
            )

        # 4. SLA Violation Penalty Clause
        elif "sla" in text_lower or "uptime" in text_lower or "service level" in text_lower:
            uptime = 99.5
            match_uptime = re.search(r'(\d+(?:\.\d+)?)\s*%', text_lower)
            if match_uptime:
                uptime = float(match_uptime.group(1))

            penalty_amount = 500.0
            match_amt = re.search(r'\$(\d+(?:,\d+)?)|\b(\d+)\s*(?:usd|dollars)', text_lower)
            if match_amt:
                raw_amt = match_amt.group(1) or match_amt.group(2)
                penalty_amount = float(raw_amt.replace(",", ""))

            return LegalIR(
                rule_id=rule_code,
                type="sla_penalty",
                title="SLA Uptime Penalty",
                source=source,
                conditions=[
                    RuleCondition(variable="sla_uptime_percent", operator="<", value=uptime, unit="percent")
                ],
                actions=[
                    RuleAction(
                        type="sla_deduction",
                        amount=penalty_amount,
                        period="incident",
                        description=f"${penalty_amount} fixed deduction per 0.1% breach below {uptime}% uptime"
                    )
                ],
                caps=RuleCaps(max_amount=5000.0),
                ambiguity_flag=False
            )

        # 5. Price Escalation / Inflation Adjustment Clause
        elif "escalation" in text_lower or "price increase" in text_lower or "inflation" in text_lower:
            return LegalIR(
                rule_id=rule_code,
                type="price_escalation",
                title="Annual Price Index Escalation",
                source=source,
                conditions=[
                    RuleCondition(variable="inflation_rate_percent", operator=">", value=3.0, unit="percent")
                ],
                actions=[
                    RuleAction(
                        type="escalation",
                        rate=0.03,
                        base_variable="contract_value",
                        description="Price escalation capped at 3% per annum tied to CPI index"
                    )
                ],
                caps=RuleCaps(max_percentage=0.05),
                ambiguity_flag=False
            )

        # Fallback for ambiguous or standard clauses
        return LegalIR(
            rule_id=rule_code,
            type="general_clause",
            title="General Contractual Provision",
            source=source,
            conditions=[RuleCondition(variable="clause_active", operator="==", value=True)],
            actions=[RuleAction(type="info", description="Informational contractual requirement")],
            ambiguity_flag=True if "reasonable" in text_lower or "discretion" in text_lower else False,
            review_reason="Vague or subjective terminology requiring legal review" if "reasonable" in text_lower else None
        )
