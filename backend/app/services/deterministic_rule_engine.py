import math
import uuid
from datetime import datetime
from typing import List, Dict, Any
from app.models.schemas import LegalIR, RuleExecutionOutput, ExecutionStepResult, RuleSourceInfo

class DeterministicRuleEngine:
    @staticmethod
    def execute_rules(contract_id: str, rules: List[LegalIR], variables: Dict[str, Any], scenario_name: str = "Baseline Execution") -> RuleExecutionOutput:
        """
        Executes Legal IR rules deterministically against input variables.
        Zero LLM calls are involved in the calculations.
        Returns total financial impact, granular calculation steps, and human readable explanation.
        """
        execution_id = f"EXEC-{uuid.uuid4().hex[:8].upper()}"
        calculation_steps: List[ExecutionStepResult] = []
        applied_rules: List[str] = []
        total_financial_impact = 0.0
        
        # Extracted variables with sensible defaults
        contract_value = float(variables.get("contract_value", 1000000.0))
        invoice_amount = float(variables.get("invoice_amount", variables.get("contract_value", 1000000.0)))
        payment_delay_days = int(variables.get("payment_delay_days", 0))
        delivery_delay_days = int(variables.get("delivery_delay_days", 0))
        order_quantity = int(variables.get("order_quantity", 0))
        sla_uptime_percent = float(variables.get("sla_uptime_percent", 100.0))
        inflation_rate_percent = float(variables.get("inflation_rate_percent", 0.0))

        step_counter = 1

        for rule in rules:
            rule_code = rule.rule_id
            rule_type = rule.type
            source = rule.source

            # ----------------------------------------------------
            # 1. LATE PAYMENT INTEREST
            # ----------------------------------------------------
            if rule_type == "late_payment_interest":
                cond = rule.conditions[0] if rule.conditions else None
                threshold_days = int(cond.value) if cond and cond.value else 30
                action = rule.actions[0] if rule.actions else None
                rate = float(action.rate) if action and action.rate else 0.015
                
                if payment_delay_days > threshold_days:
                    applied_rules.append(rule_code)
                    grace_days = action.grace_period_days if action and action.grace_period_days else threshold_days
                    delay_past_grace = payment_delay_days - grace_days
                    months_delayed = max(1.0, math.ceil(delay_past_grace / 30.0))
                    
                    raw_interest = invoice_amount * rate * months_delayed
                    max_cap_pct = rule.caps.max_percentage if rule.caps and rule.caps.max_percentage else 0.15
                    max_interest_cap = invoice_amount * max_cap_pct
                    final_interest = min(raw_interest, max_interest_cap)
                    
                    total_financial_impact += final_interest
                    
                    desc = (
                        f"Payment delayed by {payment_delay_days} days (exceeds {threshold_days}-day threshold). "
                        f"Interest charged for {months_delayed:.0f} month(s) at {rate*100}% per month "
                        f"on invoice amount ${invoice_amount:,.2f}."
                    )
                    if final_interest < raw_interest:
                        desc += f" (Capped at maximum limit of {max_cap_pct*100}% = ${max_interest_cap:,.2f})."

                    calculation_steps.append(ExecutionStepResult(
                        step_number=step_counter,
                        rule_code=rule_code,
                        title="Late Payment Interest Charge",
                        description=desc,
                        formula=f"min(${invoice_amount:,.2f} × {rate} × {months_delayed:.0f}, ${max_interest_cap:,.2f})",
                        subtotal=round(final_interest, 2),
                        source_clause=source
                    ))
                    step_counter += 1

            # ----------------------------------------------------
            # 2. DELIVERY DELAY PENALTY & LIQUIDATED DAMAGES
            # ----------------------------------------------------
            elif rule_type == "delivery_delay_penalty":
                cond = rule.conditions[0] if rule.conditions else None
                threshold_days = int(cond.value) if cond and cond.value else 10
                action = rule.actions[0] if rule.actions else None
                rate = float(action.rate) if action and action.rate else 0.02

                if delivery_delay_days > threshold_days:
                    applied_rules.append(rule_code)
                    grace_days = action.grace_period_days if action and action.grace_period_days else threshold_days
                    applicable_delay_days = delivery_delay_days - grace_days
                    weeks_delayed = math.ceil(applicable_delay_days / 7.0)

                    raw_penalty = contract_value * rate * weeks_delayed
                    max_cap_pct = rule.caps.max_percentage if rule.caps and rule.caps.max_percentage else 0.10
                    max_penalty_cap = contract_value * max_cap_pct
                    final_penalty = min(raw_penalty, max_penalty_cap)

                    total_financial_impact += final_penalty

                    desc = (
                        f"Delivery delayed by {delivery_delay_days} days (exceeds {threshold_days}-day grace period). "
                        f"Penalty assessed for {weeks_delayed} week(s) at {rate*100}% per week "
                        f"on contract value ${contract_value:,.2f}."
                    )
                    if final_penalty < raw_penalty:
                        desc += f" (Capped at maximum contractual penalty limit of {max_cap_pct*100}% = ${max_penalty_cap:,.2f})."

                    calculation_steps.append(ExecutionStepResult(
                        step_number=step_counter,
                        rule_code=rule_code,
                        title="Delivery Delay Liquidated Damages",
                        description=desc,
                        formula=f"min(${contract_value:,.2f} × {rate} × {weeks_delayed}, ${max_penalty_cap:,.2f})",
                        subtotal=round(final_penalty, 2),
                        source_clause=source
                    ))
                    step_counter += 1

            # ----------------------------------------------------
            # 3. VOLUME DISCOUNT
            # ----------------------------------------------------
            elif rule_type == "volume_discount":
                cond = rule.conditions[0] if rule.conditions else None
                min_quantity = int(cond.value) if cond and cond.value else 1000
                action = rule.actions[0] if rule.actions else None
                discount_rate = float(action.rate) if action and action.rate else 0.05

                if order_quantity >= min_quantity:
                    applied_rules.append(rule_code)
                    discount_amount = contract_value * discount_rate
                    # Discount reduces financial impact / cost
                    total_financial_impact -= discount_amount

                    desc = (
                        f"Order quantity ({order_quantity:,} units) satisfies volume threshold (>= {min_quantity:,} units). "
                        f"Applied {discount_rate*100}% volume discount on ${contract_value:,.2f}."
                    )

                    calculation_steps.append(ExecutionStepResult(
                        step_number=step_counter,
                        rule_code=rule_code,
                        title="Volume Quantity Discount",
                        description=desc,
                        formula=f"-(${contract_value:,.2f} × {discount_rate})",
                        subtotal=round(-discount_amount, 2),
                        source_clause=source
                    ))
                    step_counter += 1

            # ----------------------------------------------------
            # 4. SLA PENALTY
            # ----------------------------------------------------
            elif rule_type == "sla_penalty":
                cond = rule.conditions[0] if rule.conditions else None
                target_uptime = float(cond.value) if cond and cond.value else 99.5
                action = rule.actions[0] if rule.actions else None
                fixed_penalty = float(action.amount) if action and action.amount else 500.0

                if sla_uptime_percent < target_uptime:
                    applied_rules.append(rule_code)
                    breach_delta = target_uptime - sla_uptime_percent
                    incidents = math.ceil(breach_delta / 0.1) # 1 incident per 0.1% drop
                    raw_sla_penalty = incidents * fixed_penalty
                    max_cap = rule.caps.max_amount if rule.caps and rule.caps.max_amount else 5000.0
                    final_sla_penalty = min(raw_sla_penalty, max_cap)

                    total_financial_impact += final_sla_penalty

                    desc = (
                        f"Achieved SLA uptime ({sla_uptime_percent:.2f}%) fell below target threshold ({target_uptime:.2f}%). "
                        f"Assessed {incidents} breach incident(s) at ${fixed_penalty:,.2f} per incident."
                    )

                    calculation_steps.append(ExecutionStepResult(
                        step_number=step_counter,
                        rule_code=rule_code,
                        title="SLA Performance Breach Penalty",
                        description=desc,
                        formula=f"min({incidents} × ${fixed_penalty:,.2f}, ${max_cap:,.2f})",
                        subtotal=round(final_sla_penalty, 2),
                        source_clause=source
                    ))
                    step_counter += 1

            # ----------------------------------------------------
            # 5. PRICE ESCALATION
            # ----------------------------------------------------
            elif rule_type == "price_escalation":
                cond = rule.conditions[0] if rule.conditions else None
                threshold = float(cond.value) if cond and cond.value else 3.0
                action = rule.actions[0] if rule.actions else None
                rate = float(action.rate) if action and action.rate else 0.03

                if inflation_rate_percent > threshold:
                    applied_rules.append(rule_code)
                    escalation_amount = contract_value * rate
                    total_financial_impact += escalation_amount

                    desc = (
                        f"Inflation index ({inflation_rate_percent}%) exceeded baseline trigger ({threshold}%). "
                        f"Applied price escalation adjustment of {rate*100}%."
                    )

                    calculation_steps.append(ExecutionStepResult(
                        step_number=step_counter,
                        rule_code=rule_code,
                        title="Annual Inflation Price Escalation",
                        description=desc,
                        formula=f"${contract_value:,.2f} × {rate}",
                        subtotal=round(escalation_amount, 2),
                        source_clause=source
                    ))
                    step_counter += 1

        summary = {
            "applied_rules_count": len(applied_rules),
            "net_financial_adjustment": round(total_financial_impact, 2),
            "status": "COMPLETED",
            "scenario_name": scenario_name
        }

        # Build decompiled natural language explanation
        explanation = DeterministicRuleEngine._generate_decompiled_explanation(
            applied_rules, calculation_steps, total_financial_impact
        )

        return RuleExecutionOutput(
            execution_id=execution_id,
            contract_id=contract_id,
            total_financial_impact=round(total_financial_impact, 2),
            summary=summary,
            calculation_steps=calculation_steps,
            applied_rules=applied_rules,
            human_explanation=explanation,
            executed_at=datetime.utcnow().isoformat()
        )

    @staticmethod
    def _generate_decompiled_explanation(applied_rules: List[str], steps: List[ExecutionStepResult], net_impact: float) -> str:
        if not steps:
            return "All operational variables satisfy standard contractual terms. No penalties, interest charges, or discounts were triggered."

        lines = [f"Deterministic Rule Execution Result Summary: Net Financial Impact of ${net_impact:+,.2f} across {len(applied_rules)} rule(s).\n"]
        for step in steps:
            clause_ref = f"Section {step.source_clause.section} (Page {step.source_clause.page})" if step.source_clause else "Contract Clause"
            lines.append(f"• Rule {step.rule_code} [{step.title}]: {step.description} Impact: ${step.subtotal:+,.2f}. Source: {clause_ref}.")

        return "\n".join(lines)
