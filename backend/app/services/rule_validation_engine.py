from typing import Dict, Any, List
from app.models.schemas import LegalIR, RuleValidationResult

KNOWN_VARIABLES = {
    "payment_delay_days": "Number of days invoice payment is past due",
    "delivery_delay_days": "Number of days goods/services delivery is past agreed deadline",
    "order_quantity": "Total volume/units ordered in purchase order",
    "contract_value": "Total baseline monetary value of contract",
    "invoice_amount": "Specific billing invoice amount",
    "sla_uptime_percent": "System uptime percentage achieved over SLA period",
    "inflation_rate_percent": "Economic CPI inflation rate per annum",
    "clause_active": "Boolean status indicating if clause is active"
}

VALID_OPERATORS = {">", ">=", "<", "<=", "==", "!=", "in"}

class RuleValidationEngine:
    @staticmethod
    def validate_rule(rule_ir: LegalIR) -> RuleValidationResult:
        issues: List[str] = []
        missing_vars: List[str] = []
        status = "VALID"

        # 1. Validate Rule ID & Type
        if not rule_ir.rule_id:
            issues.append("Rule ID is missing or blank.")

        if not rule_ir.type:
            issues.append("Rule type is unclassified.")

        # 2. Check Conditions
        if not rule_ir.conditions:
            issues.append("No conditions defined for rule execution.")
            status = "NEEDS_REVIEW"
        else:
            for cond in rule_ir.conditions:
                if cond.variable not in KNOWN_VARIABLES:
                    missing_vars.append(cond.variable)
                    issues.append(f"Unknown condition variable '{cond.variable}'. Needs variable mapping.")
                    status = "NEEDS_REVIEW"

                if cond.operator not in VALID_OPERATORS:
                    issues.append(f"Invalid condition operator '{cond.operator}'.")
                    status = "NEEDS_REVIEW"

                if cond.value is None:
                    issues.append(f"Condition threshold value for '{cond.variable}' is null.")
                    status = "NEEDS_REVIEW"

        # 3. Check Actions
        if not rule_ir.actions:
            issues.append("No actions defined for rule.")
            status = "NEEDS_REVIEW"
        else:
            for action in rule_ir.actions:
                if action.rate is not None:
                    if action.rate < 0 or action.rate > 1.0:
                        issues.append(f"Action rate ({action.rate}) is out of expected percentage range [0.0, 1.0].")
                        status = "NEEDS_REVIEW"

                if action.amount is not None and action.amount < 0:
                    issues.append(f"Action amount (${action.amount}) cannot be negative.")
                    status = "NEEDS_REVIEW"

        # 4. Check Ambiguity Flags & Missing Caps
        if rule_ir.ambiguity_flag:
            status = "NEEDS_REVIEW"
            if rule_ir.review_reason:
                issues.append(f"Ambiguous clause text: {rule_ir.review_reason}")
            else:
                issues.append("Clause text contains vague or subjective terms requiring manual human review.")

        if rule_ir.type in ["delivery_delay_penalty", "late_payment_interest"] and not (rule_ir.caps and (rule_ir.caps.max_percentage or rule_ir.caps.max_amount)):
            issues.append("Warning: Penalty rule has no explicit maximum liability cap specified in contract.")

        # Generate human summary
        if status == "VALID":
            human_summary = f"Rule {rule_ir.rule_id} ({rule_ir.title}) is fully validated and ready for deterministic execution."
        else:
            human_summary = f"Rule {rule_ir.rule_id} requires human review due to {len(issues)} flagged issue(s)."

        return RuleValidationResult(
            rule_id=rule_ir.rule_id,
            status=status,
            issues=issues,
            missing_variables=missing_vars,
            human_summary=human_summary
        )
