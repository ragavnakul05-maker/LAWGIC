import re
import json
import logging
from typing import Dict, Any, List, Optional
from app.models.schemas import (
    LegalIR, MatchedRuleInfo, QuestionParseResponse, RuleSourceInfo
)
from app.core.config import settings

logger = logging.getLogger(__name__)

class QuestionParserService:
    @classmethod
    def parse_simulation_question(
        cls,
        contract_id: str,
        question: str,
        rules: List[LegalIR],
        contract_title: str = "Contract"
    ) -> QuestionParseResponse:
        """
        Parses a natural language what-if question, maps it to a specific Legal IR rule,
        extracts parameters, identifies missing required inputs, and prepares human-in-the-loop confirmation.
        """
        # Filter for operational rules (rules that have mathematical actions or conditions)
        operational_rules = [
            r for r in rules
            if r.type not in ("general_clause", "boilerplate") and (r.actions or r.conditions)
        ]
        if not operational_rules:
            operational_rules = rules

        # Attempt NLP parsing via external LLM/Ollama if configured, otherwise use semantic fallback
        parsed_data = None
        if settings.LLM_PROVIDER in ["openai", "gemini"] and settings.LLM_API_KEY:
            try:
                parsed_data = cls._call_llm_parser(question, operational_rules)
            except Exception as e:
                logger.warning(f"[QuestionParser] LLM call failed ({e}), falling back to pattern matching.")

        if not parsed_data:
            parsed_data = cls._pattern_match_parser(question, operational_rules)

        matched_rule = parsed_data["matched_rule"]
        extracted_params = parsed_data["extracted_parameters"]

        # Determine missing parameters based on the matched rule requirements
        missing_params = []
        suggested_values: Dict[str, Any] = {**extracted_params}
        assumptions: List[str] = []

        rule_type = matched_rule.type
        rule_actions = matched_rule.actions or []
        rule_action = rule_actions[0] if rule_actions else None
        rule_caps = matched_rule.caps

        # Check required base monetary variables
        if rule_type in ("delivery_delay_penalty", "volume_discount", "price_escalation"):
            if "contract_value" not in extracted_params:
                missing_params.append("contract_value")
                suggested_values["contract_value"] = 1000000.0
                assumptions.append("Assumed baseline contract value is $1,000,000.00.")

        elif rule_type == "late_payment_interest":
            if "invoice_amount" not in extracted_params and "contract_value" not in extracted_params:
                missing_params.append("invoice_amount")
                suggested_values["invoice_amount"] = 1000000.0
                assumptions.append("Assumed invoice billing amount is $1,000,000.00.")

        # Add rule-specific assumptions based on the matched Legal IR
        if rule_action and rule_action.grace_period_days:
            assumptions.append(
                f"Contractual grace period of {rule_action.grace_period_days} days applied per Section {matched_rule.source.section}."
            )

        if rule_caps:
            if rule_caps.max_percentage:
                assumptions.append(
                    f"Contractual liability maximum cap of {rule_caps.max_percentage * 100:.1f}% enforced per Section {matched_rule.source.section}."
                )
            elif rule_caps.max_amount:
                assumptions.append(
                    f"Contractual maximum penalty cap of ${rule_caps.max_amount:,.2f} enforced per Section {matched_rule.source.section}."
                )

        # Build confirmation message
        section_ref = f"Section {matched_rule.source.section}" if matched_rule.source.section else "contract terms"
        page_ref = f" (Page {matched_rule.source.page})" if matched_rule.source.page else ""
        rule_title = matched_rule.title

        if missing_params:
            missing_labels = ", ".join([p.replace("_", " ").title() for p in missing_params])
            confirmation_prompt = (
                f"Identified {rule_title} under {section_ref}{page_ref}. "
                f"Extracted parameters: {cls._format_params(extracted_params)}. "
                f"Please confirm or adjust {missing_labels} before calculating."
            )
            status = "NEEDS_CONFIRMATION"
        else:
            confirmation_prompt = (
                f"Identified {rule_title} under {section_ref}{page_ref}. "
                f"Extracted parameters: {cls._format_params(extracted_params)}. "
                f"Ready for deterministic execution."
            )
            status = "READY"

        matched_info = MatchedRuleInfo(
            rule_code=matched_rule.rule_id,
            title=matched_rule.title,
            rule_type=matched_rule.type,
            source=matched_rule.source,
            description=rule_action.description if rule_action else None
        )

        return QuestionParseResponse(
            contract_id=contract_id,
            question=question,
            status=status,
            matched_rule=matched_info,
            extracted_parameters=extracted_params,
            missing_parameters=missing_params,
            suggested_values=suggested_values,
            assumptions=assumptions,
            confirmation_prompt=confirmation_prompt
        )

    @classmethod
    def _pattern_match_parser(cls, question: str, rules: List[LegalIR]) -> Dict[str, Any]:
        """
        Deterministic NLP pattern matcher for legal scenario queries.
        Maps keywords and regular expressions directly to Legal IR rules.
        """
        q_lower = question.lower()
        extracted_params: Dict[str, Any] = {}
        matched_rule = rules[0]  # default fallback

        # 1. Delivery Delay Rules
        if any(k in q_lower for k in ["delivery", "delayed", "shipment", "late delivery", "dispatch", "deliver"]):
            target_rules = [r for r in rules if r.type == "delivery_delay_penalty"]
            if target_rules:
                matched_rule = target_rules[0]

            # Extract days
            days_match = re.search(r"(\d+)\s*(?:days?|d\b)", q_lower)
            weeks_match = re.search(r"(\d+)\s*(?:weeks?|w\b)", q_lower)
            if days_match:
                extracted_params["delivery_delay_days"] = int(days_match.group(1))
            elif weeks_match:
                extracted_params["delivery_delay_days"] = int(weeks_match.group(1)) * 7
            else:
                num_match = re.search(r"\b(\d+)\b", q_lower)
                if num_match:
                    extracted_params["delivery_delay_days"] = int(num_match.group(1))

        # 2. Payment Delay / Late Payment Interest Rules
        elif any(k in q_lower for k in ["payment", "invoice", "pay", "overdue", "interest", "paid late"]):
            target_rules = [r for r in rules if r.type == "late_payment_interest"]
            if target_rules:
                matched_rule = target_rules[0]

            days_match = re.search(r"(\d+)\s*(?:days?|d\b)", q_lower)
            months_match = re.search(r"(\d+)\s*(?:months?|m\b)", q_lower)
            if days_match:
                extracted_params["payment_delay_days"] = int(days_match.group(1))
            elif months_match:
                extracted_params["payment_delay_days"] = int(months_match.group(1)) * 30
            else:
                num_match = re.search(r"\b(\d+)\b", q_lower)
                if num_match:
                    extracted_params["payment_delay_days"] = int(num_match.group(1))

        # 3. Volume Discount / Order Quantity Rules
        elif any(k in q_lower for k in ["volume", "quantity", "units", "order", "bulk", "discount"]):
            target_rules = [r for r in rules if r.type == "volume_discount"]
            if target_rules:
                matched_rule = target_rules[0]

            qty_match = re.search(r"([\d,]+)\s*(?:units?|items?|orders?|volume)", q_lower)
            if qty_match:
                extracted_params["order_quantity"] = int(qty_match.group(1).replace(",", ""))
            else:
                num_match = re.search(r"\b([\d,]+)\b", q_lower)
                if num_match:
                    extracted_params["order_quantity"] = int(num_match.group(1).replace(",", ""))

        # 4. SLA Uptime / Performance Penalty Rules
        elif any(k in q_lower for k in ["sla", "uptime", "downtime", "availability", "performance", "breach"]):
            target_rules = [r for r in rules if r.type == "sla_penalty"]
            if target_rules:
                matched_rule = target_rules[0]

            pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", q_lower)
            if pct_match:
                extracted_params["sla_uptime_percent"] = float(pct_match.group(1))
            else:
                drop_match = re.search(r"(?:drops?|falls?|down to)\s*(\d+(?:\.\d+)?)", q_lower)
                if drop_match:
                    extracted_params["sla_uptime_percent"] = float(drop_match.group(1))

        # 5. Price Escalation / Inflation Rules
        elif any(k in q_lower for k in ["inflation", "cpi", "escalation", "price increase"]):
            target_rules = [r for r in rules if r.type == "price_escalation"]
            if target_rules:
                matched_rule = target_rules[0]

            pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", q_lower)
            if pct_match:
                extracted_params["inflation_rate_percent"] = float(pct_match.group(1))

        # Also extract contract value or invoice amount if mentioned in question
        money_match = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", q_lower)
        if money_match:
            val = float(money_match.group(1).replace(",", ""))
            if "invoice" in q_lower:
                extracted_params["invoice_amount"] = val
            else:
                extracted_params["contract_value"] = val

        return {
            "matched_rule": matched_rule,
            "extracted_parameters": extracted_params
        }

    @classmethod
    def _call_llm_parser(cls, question: str, rules: List[LegalIR]) -> Optional[Dict[str, Any]]:
        """Optional LLM-based parsing when external API or Ollama is available."""
        rules_desc = [
            f"- Rule ID: {r.rule_id}, Type: {r.type}, Title: {r.title}, Section: {r.source.section}"
            for r in rules
        ]
        prompt = f"""You are an expert legal contract NLP parser. Match the user's simulation question to exactly ONE contract rule and extract parameters.

CONTRACT RULES:
{chr(10).join(rules_desc)}

USER QUESTION: "{question}"

Return ONLY JSON:
{{
  "rule_code": "<Rule ID>",
  "extracted_parameters": {{
    "delivery_delay_days": <number or null>,
    "payment_delay_days": <number or null>,
    "order_quantity": <number or null>,
    "sla_uptime_percent": <number or null>,
    "contract_value": <number or null>
  }}
}}"""
        import requests
        if settings.LLM_PROVIDER == "openai":
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                json={"model": settings.LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}},
                timeout=10
            )
            data = json.loads(resp.json()["choices"][0]["message"]["content"])
            code = data.get("rule_code")
            target = next((r for r in rules if r.rule_id == code), rules[0])
            params = {k: v for k, v in data.get("extracted_parameters", {}).items() if v is not None}
            return {"matched_rule": target, "extracted_parameters": params}
        return None

    @staticmethod
    def _format_params(params: Dict[str, Any]) -> str:
        if not params:
            return "none"
        parts = []
        for k, v in params.items():
            label = k.replace("_", " ").title()
            if "percent" in k:
                parts.append(f"{label}: {v}%")
            elif "days" in k:
                parts.append(f"{label}: {v} days")
            elif "value" in k or "amount" in k:
                parts.append(f"{label}: ${v:,.2f}")
            else:
                parts.append(f"{label}: {v}")
        return ", ".join(parts)
