import math
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.models.schemas import LegalIR, RuleExecutionOutput, ExecutionStepResult, RuleSourceInfo

class DeterministicRuleEngine:
    @staticmethod
    def evaluate_single_rule(rule: LegalIR, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deterministically evaluates a single Legal IR rule against input variables.
        Zero LLM calls involved. Returns full calculation details, formulas,
        reasons (e.g. cap reached or threshold not exceeded), and cap status.
        """
        rule_code = rule.rule_id
        rule_type = rule.type
        source = rule.source

        # Common variables
        contract_value = float(variables.get("contract_value", 1000000.0))
        invoice_amount = float(variables.get("invoice_amount", variables.get("contract_value", 1000000.0)))
        payment_delay_days = int(variables.get("payment_delay_days", 0))
        delivery_delay_days = int(variables.get("delivery_delay_days", 0))
        order_quantity = int(variables.get("order_quantity", 0))
        sla_uptime_percent = float(variables.get("sla_uptime_percent", 100.0))
        inflation_rate_percent = float(variables.get("inflation_rate_percent", 0.0))

        cond = rule.conditions[0] if rule.conditions else None
        action = rule.actions[0] if rule.actions else None
        caps = rule.caps

        # Conditions summary for audit
        applied_conditions = []
        if rule.conditions:
            for c in rule.conditions:
                unit_str = f" {c.unit}" if c.unit else ""
                applied_conditions.append(f"{c.variable} {c.operator} {c.value}{unit_str}")

        # ----------------------------------------------------
        # 1. LATE PAYMENT INTEREST
        # ----------------------------------------------------
        if rule_type == "late_payment_interest":
            threshold_days = int(cond.value) if cond and cond.value is not None else 30
            grace_days = action.grace_period_days if action and action.grace_period_days is not None else threshold_days
            rate = float(action.rate) if action and action.rate is not None else 0.015
            period = action.period if action and action.period else "month"

            # Determine cap
            max_interest_cap = float('inf')
            cap_detail = "Not specified in this contract"
            if caps:
                if caps.max_percentage is not None:
                    max_interest_cap = invoice_amount * caps.max_percentage
                    cap_detail = f"Max {caps.max_percentage * 100:.1f}% (${max_interest_cap:,.2f}) cap"
                elif caps.max_amount is not None:
                    max_interest_cap = caps.max_amount
                    cap_detail = f"Max ${caps.max_amount:,.2f} cap"

            triggered = payment_delay_days > threshold_days
            if triggered:
                delay_past_grace = payment_delay_days - grace_days
                if period == "day":
                    periods = max(1.0, float(delay_past_grace))
                    period_unit = "day(s)"
                else:
                    periods = max(1.0, math.ceil(delay_past_grace / 30.0))
                    period_unit = "month(s)"

                raw_interest = invoice_amount * rate * periods
                final_interest = min(raw_interest, max_interest_cap)
                cap_applied = final_interest < raw_interest

                reason = (
                    f"Contractual cap reached: Maximum ${max_interest_cap:,.2f}"
                    if cap_applied
                    else f"Payment delayed by {payment_delay_days} days (exceeds {threshold_days}-day deadline)"
                )
                desc = (
                    f"Payment delayed by {payment_delay_days} days (exceeds {threshold_days}-day threshold). "
                    f"Interest charged for {periods:.0f} {period_unit} at {rate * 100:.1f}% per {period} "
                    f"on invoice amount ${invoice_amount:,.2f}."
                )
                if cap_applied:
                    desc += f" (Capped at maximum limit of ${max_interest_cap:,.2f})."

                formula_str = (
                    f"min(${invoice_amount:,.2f} × {rate} × {periods:.0f}, ${max_interest_cap:,.2f})"
                    if max_interest_cap != float('inf')
                    else f"${invoice_amount:,.2f} × {rate} × {periods:.0f}"
                )
                breakdown_str = (
                    f"Overdue by {payment_delay_days} days. Grace period ({grace_days} days) deducted -> {delay_past_grace} days overdue ({periods:.0f} {period_unit}). "
                    f"Applied rate {rate * 100:.1f}% on ${invoice_amount:,.2f} = ${raw_interest:,.2f}."
                    + (f" Capped at contractual limit of ${max_interest_cap:,.2f}." if cap_applied else "")
                )
                subtotal = round(final_interest, 2)
            else:
                cap_applied = False
                subtotal = 0.0
                reason = f"Paid within contractual deadline (<= {threshold_days} days)"
                desc = f"Payment delayed by {payment_delay_days} days (within {threshold_days}-day threshold). No interest assessed."
                formula_str = "$0.00"
                breakdown_str = f"Payment delay of {payment_delay_days} days does not exceed contractual threshold of {threshold_days} days. Zero interest penalty."

            return {
                "rule_code": rule_code,
                "rule_title": rule.title,
                "rule_type": rule_type,
                "title": "Late Payment Interest Charge",
                "triggered": triggered,
                "subtotal": subtotal,
                "formula": formula_str,
                "description": desc,
                "calculation_breakdown": breakdown_str,
                "reason": reason,
                "cap_applied": cap_applied,
                "cap_detail": cap_detail,
                "parameter_name": "payment_delay_days",
                "parameter_label": "Payment Delay (Days)",
                "parameter_value": payment_delay_days,
                "unit": "days",
                "applied_conditions": applied_conditions,
                "source_clause": source
            }

        # ----------------------------------------------------
        # 2. DELIVERY DELAY PENALTY & LIQUIDATED DAMAGES
        # ----------------------------------------------------
        elif rule_type == "delivery_delay_penalty":
            threshold_days = int(cond.value) if cond and cond.value is not None else 10
            grace_days = action.grace_period_days if action and action.grace_period_days is not None else threshold_days
            rate = float(action.rate) if action and action.rate is not None else 0.02
            amount = float(action.amount) if action and action.amount is not None else None
            period = action.period if action and action.period else "week"

            # Determine cap
            max_penalty_cap = float('inf')
            cap_detail = "Not specified in this contract"
            if caps:
                if caps.max_percentage is not None:
                    max_penalty_cap = contract_value * caps.max_percentage
                    cap_detail = f"Max {caps.max_percentage * 100:.1f}% (${max_penalty_cap:,.2f}) cap"
                elif caps.max_amount is not None:
                    max_penalty_cap = caps.max_amount
                    cap_detail = f"Max ${caps.max_amount:,.2f} cap"

            triggered = delivery_delay_days > threshold_days
            if triggered:
                applicable_delay_days = delivery_delay_days - grace_days
                if amount is not None and amount > 0:
                    if period == "day":
                        periods = max(1, applicable_delay_days)
                        period_unit = "day(s)"
                    else:
                        periods = max(1, math.ceil(applicable_delay_days / 7.0))
                        period_unit = "week(s)"
                    raw_penalty = periods * amount
                    formula_rate = f"${amount:,.2f}"
                else:
                    periods = max(1, math.ceil(applicable_delay_days / 7.0))
                    period_unit = "week(s)"
                    raw_penalty = contract_value * rate * periods
                    formula_rate = f"${contract_value:,.2f} × {rate}"

                final_penalty = min(raw_penalty, max_penalty_cap)
                cap_applied = final_penalty < raw_penalty

                reason = (
                    f"Contractual cap reached: Maximum ${max_penalty_cap:,.2f}"
                    if cap_applied
                    else f"Delivery delayed by {delivery_delay_days} days (exceeds {threshold_days}-day grace period)"
                )
                desc = (
                    f"Delivery delayed by {delivery_delay_days} days (exceeds {threshold_days}-day grace period). "
                    f"Penalty assessed for {periods} {period_unit} at {formula_rate} per {period}."
                )
                if cap_applied:
                    desc += f" (Capped at maximum contractual penalty limit of ${max_penalty_cap:,.2f})."

                formula_str = (
                    f"min({formula_rate} × {periods}, ${max_penalty_cap:,.2f})"
                    if max_penalty_cap != float('inf')
                    else f"{formula_rate} × {periods}"
                )
                breakdown_str = (
                    f"Delivery delayed by {delivery_delay_days} days. Grace period ({grace_days} days) deducted -> {applicable_delay_days} days overdue ({periods} {period_unit}). "
                    f"Calculated penalty = ${raw_penalty:,.2f}."
                    + (f" Capped at contractual limit of ${max_penalty_cap:,.2f}." if cap_applied else "")
                )
                subtotal = round(final_penalty, 2)
            else:
                cap_applied = False
                subtotal = 0.0
                reason = f"Delivered within contractual delivery timeline (<= {threshold_days} days)"
                desc = f"Delivery delayed by {delivery_delay_days} days (within {threshold_days}-day grace period). No penalty assessed."
                formula_str = "$0.00"
                breakdown_str = f"Delivery delay of {delivery_delay_days} days does not exceed contractual threshold of {threshold_days} days. Zero liquidated damages."

            return {
                "rule_code": rule_code,
                "rule_title": rule.title,
                "rule_type": rule_type,
                "title": "Delivery Delay Liquidated Damages",
                "triggered": triggered,
                "subtotal": subtotal,
                "formula": formula_str,
                "description": desc,
                "calculation_breakdown": breakdown_str,
                "reason": reason,
                "cap_applied": cap_applied,
                "cap_detail": cap_detail,
                "parameter_name": "delivery_delay_days",
                "parameter_label": "Delivery Delay (Days)",
                "parameter_value": delivery_delay_days,
                "unit": "days",
                "applied_conditions": applied_conditions,
                "source_clause": source
            }

        # ----------------------------------------------------
        # 3. VOLUME DISCOUNT
        # ----------------------------------------------------
        elif rule_type == "volume_discount":
            min_quantity = int(cond.value) if cond and cond.value is not None else 1000
            discount_rate = float(action.rate) if action and action.rate is not None else 0.05
            cap_detail = "Not specified in this contract"
            if caps and caps.max_amount:
                cap_detail = f"Max ${caps.max_amount:,.2f} cap"

            triggered = order_quantity >= min_quantity
            if triggered:
                discount_amount = contract_value * discount_rate
                subtotal = round(-discount_amount, 2)
                formula_str = f"-(${contract_value:,.2f} × {discount_rate})"
                reason = f"Volume threshold satisfied: Order quantity {order_quantity:,} >= {min_quantity:,} units"
                desc = (
                    f"Order quantity ({order_quantity:,} units) satisfies volume threshold (>= {min_quantity:,} units). "
                    f"Applied {discount_rate * 100:.1f}% volume discount on ${contract_value:,.2f}."
                )
                breakdown_str = (
                    f"Order volume of {order_quantity:,} units satisfies bulk discount tier (>= {min_quantity:,} units). "
                    f"Applied {discount_rate * 100:.1f}% discount on ${contract_value:,.2f} = -${discount_amount:,.2f}."
                )
            else:
                subtotal = 0.0
                formula_str = "$0.00"
                reason = f"Order volume below discount threshold ({order_quantity:,} < {min_quantity:,} units)"
                desc = f"Order quantity ({order_quantity:,} units) is below volume threshold ({min_quantity:,} units). Standard pricing applies."
                breakdown_str = f"Order quantity of {order_quantity:,} units does not meet the minimum volume tier of {min_quantity:,} units. Standard pricing applies."

            return {
                "rule_code": rule_code,
                "rule_title": rule.title,
                "rule_type": rule_type,
                "title": "Volume Quantity Discount",
                "triggered": triggered,
                "subtotal": subtotal,
                "formula": formula_str,
                "description": desc,
                "calculation_breakdown": breakdown_str,
                "reason": reason,
                "cap_applied": False,
                "cap_detail": cap_detail,
                "parameter_name": "order_quantity",
                "parameter_label": "Order Quantity (Units)",
                "parameter_value": order_quantity,
                "unit": "units",
                "applied_conditions": applied_conditions,
                "source_clause": source
            }

        # ----------------------------------------------------
        # 4. SLA PENALTY
        # ----------------------------------------------------
        elif rule_type == "sla_penalty":
            target_uptime = float(cond.value) if cond and cond.value is not None else 99.5
            fixed_penalty = float(action.amount) if action and action.amount is not None else 500.0

            max_cap = float('inf')
            cap_detail = "Not specified in this contract"
            if caps:
                if caps.max_amount is not None:
                    max_cap = caps.max_amount
                    cap_detail = f"Max ${caps.max_amount:,.2f} cap"
                elif caps.max_percentage is not None:
                    max_cap = contract_value * caps.max_percentage
                    cap_detail = f"Max {caps.max_percentage * 100:.1f}% cap"

            triggered = sla_uptime_percent < target_uptime
            if triggered:
                breach_delta = target_uptime - sla_uptime_percent
                incidents = max(1, math.ceil(round(breach_delta, 4) / 0.1))
                raw_sla_penalty = incidents * fixed_penalty
                final_sla_penalty = min(raw_sla_penalty, max_cap)
                cap_applied = final_sla_penalty < raw_sla_penalty

                reason = (
                    f"Contractual cap reached: Maximum ${max_cap:,.2f}"
                    if cap_applied
                    else f"SLA breach: {sla_uptime_percent:.2f}% uptime fell below target {target_uptime:.2f}% ({incidents} incident(s))"
                )
                desc = (
                    f"Achieved SLA uptime ({sla_uptime_percent:.2f}%) fell below target threshold ({target_uptime:.2f}%). "
                    f"Assessed {incidents} breach incident(s) at ${fixed_penalty:,.2f} per incident."
                )
                if cap_applied:
                    desc += f" (Capped at maximum limit of ${max_cap:,.2f})."

                formula_str = (
                    f"min({incidents} × ${fixed_penalty:,.2f}, ${max_cap:,.2f})"
                    if max_cap != float('inf')
                    else f"{incidents} × ${fixed_penalty:,.2f}"
                )
                breakdown_str = (
                    f"Achieved SLA uptime ({sla_uptime_percent:.2f}%) fell below contractual threshold ({target_uptime:.2f}%). "
                    f"Assessed {incidents} incident(s) at ${fixed_penalty:,.2f} each = ${raw_sla_penalty:,.2f}."
                    + (f" Capped at contractual limit of ${max_cap:,.2f}." if cap_applied else "")
                )
                subtotal = round(final_sla_penalty, 2)
            else:
                cap_applied = False
                subtotal = 0.0
                reason = f"SLA target satisfied: {sla_uptime_percent:.2f}% >= {target_uptime:.2f}%"
                desc = f"Achieved SLA uptime ({sla_uptime_percent:.2f}%) meets or exceeds target threshold ({target_uptime:.2f}%). No breach penalty."
                formula_str = "$0.00"
                breakdown_str = f"Achieved uptime of {sla_uptime_percent:.2f}% satisfies or exceeds required contractual target of {target_uptime:.2f}%. No penalty assessed."

            return {
                "rule_code": rule_code,
                "rule_title": rule.title,
                "rule_type": rule_type,
                "title": "SLA Performance Breach Penalty",
                "triggered": triggered,
                "subtotal": subtotal,
                "formula": formula_str,
                "description": desc,
                "calculation_breakdown": breakdown_str,
                "reason": reason,
                "cap_applied": cap_applied,
                "cap_detail": cap_detail,
                "parameter_name": "sla_uptime_percent",
                "parameter_label": "Achieved SLA Uptime (%)",
                "parameter_value": sla_uptime_percent,
                "unit": "%",
                "applied_conditions": applied_conditions,
                "source_clause": source
            }

        # ----------------------------------------------------
        # 5. PRICE ESCALATION
        # ----------------------------------------------------
        elif rule_type == "price_escalation":
            threshold = float(cond.value) if cond and cond.value is not None else 3.0
            rate = float(action.rate) if action and action.rate is not None else 0.03

            max_cap = float('inf')
            cap_detail = "Not specified in this contract"
            if caps and caps.max_percentage is not None:
                max_cap = contract_value * caps.max_percentage
                cap_detail = f"Max {caps.max_percentage * 100:.1f}% cap"

            triggered = inflation_rate_percent > threshold
            if triggered:
                raw_escalation = contract_value * rate
                final_escalation = min(raw_escalation, max_cap)
                cap_applied = final_escalation < raw_escalation

                reason = (
                    f"Contractual cap reached: Maximum ${max_cap:,.2f}"
                    if cap_applied
                    else f"Inflation index {inflation_rate_percent}% exceeded trigger {threshold}%"
                )
                desc = (
                    f"Inflation index ({inflation_rate_percent}%) exceeded baseline trigger ({threshold}%). "
                    f"Applied price escalation adjustment of {rate * 100:.1f}%."
                )
                formula_str = (
                    f"min(${contract_value:,.2f} × {rate}, ${max_cap:,.2f})"
                    if max_cap != float('inf')
                    else f"${contract_value:,.2f} × {rate}"
                )
                breakdown_str = (
                    f"Inflation rate {inflation_rate_percent}% exceeded baseline trigger ({threshold}%). "
                    f"Applied {rate * 100:.1f}% adjustment on ${contract_value:,.2f} = ${final_escalation:,.2f}."
                )
                subtotal = round(final_escalation, 2)
            else:
                cap_applied = False
                subtotal = 0.0
                reason = f"Inflation index within baseline ({inflation_rate_percent}% <= {threshold}%)"
                desc = f"Inflation index ({inflation_rate_percent}%) does not exceed trigger threshold ({threshold}%). No escalation adjustment."
                formula_str = "$0.00"
                breakdown_str = f"Annual inflation index of {inflation_rate_percent}% does not exceed contractual price escalation threshold of {threshold}%. No price adjustment."

            return {
                "rule_code": rule_code,
                "rule_title": rule.title,
                "rule_type": rule_type,
                "title": "Annual Inflation Price Escalation",
                "triggered": triggered,
                "subtotal": subtotal,
                "formula": formula_str,
                "description": desc,
                "calculation_breakdown": breakdown_str,
                "reason": reason,
                "cap_applied": cap_applied,
                "cap_detail": cap_detail,
                "parameter_name": "inflation_rate_percent",
                "parameter_label": "Annual Inflation Rate (%)",
                "parameter_value": inflation_rate_percent,
                "unit": "%",
                "applied_conditions": applied_conditions,
                "source_clause": source
            }

        # ----------------------------------------------------
        # Fallback for general / informational clauses
        # ----------------------------------------------------
        return {
            "rule_code": rule_code,
            "rule_title": rule.title,
            "rule_type": rule_type,
            "title": rule.title,
            "triggered": False,
            "subtotal": 0.0,
            "formula": "$0.00",
            "description": "Informational or standard contractual provision without computational adjustments.",
            "calculation_breakdown": "Clause defines general contractual rights and duties. No mathematical formula defined.",
            "reason": "Non-computational contractual provision",
            "cap_applied": False,
            "cap_detail": "Not specified in this contract",
            "parameter_name": "general_clause",
            "parameter_label": "General Clause",
            "parameter_value": 0,
            "unit": "",
            "applied_conditions": applied_conditions,
            "source_clause": source
        }

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

        step_counter = 1

        for rule in rules:
            eval_res = DeterministicRuleEngine.evaluate_single_rule(rule, variables)

            # Only append to execution steps if rule was triggered
            if eval_res["triggered"]:
                applied_rules.append(eval_res["rule_code"])
                total_financial_impact += eval_res["subtotal"]

                calculation_steps.append(ExecutionStepResult(
                    step_number=step_counter,
                    rule_code=eval_res["rule_code"],
                    title=eval_res["title"],
                    description=eval_res["description"],
                    formula=eval_res["formula"],
                    subtotal=eval_res["subtotal"],
                    source_clause=eval_res["source_clause"]
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
