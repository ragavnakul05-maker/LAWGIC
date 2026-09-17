from typing import Dict, Any, Optional
from app.models.schemas import LegalIR

def format_inr(amount: float) -> str:
    """Format numeric currency value in Indian Rupee format (e.g., ₹50,000, ₹10,00,000)."""
    abs_amt = abs(int(round(amount)))
    s = str(abs_amt)
    if len(s) > 3:
        last3 = s[-3:]
        remaining = s[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        groups.append(last3)
        formatted = ",".join(groups)
    else:
        formatted = s
    sign = "-" if amount < 0 else ""
    return f"{sign}₹{formatted}"

class DecompilerService:
    @staticmethod
    def decompile_to_human(rule: LegalIR) -> str:
        """
        Translates machine Legal IR JSON back into plain English legal logic.
        """
        cond_str_list = []
        for c in rule.conditions:
            unit_str = f" {c.unit}" if c.unit else ""
            cond_str_list.append(f"{c.variable.replace('_', ' ')} is {c.operator} {c.value}{unit_str}")
        
        cond_text = " AND ".join(cond_str_list)

        action_str_list = []
        for a in rule.actions:
            if a.type == "interest":
                action_str_list.append(f"assess a monthly interest penalty of {(a.rate or 0) * 100:.1f}% on the invoice amount")
            elif a.type == "penalty":
                action_str_list.append(f"charge a liquidated damages penalty of {(a.rate or 0) * 100:.1f}% per week on total contract value")
            elif a.type == "discount":
                action_str_list.append(f"grant a volume price discount of {(a.rate or 0) * 100:.1f}%")
            elif a.type == "sla_deduction":
                action_str_list.append(f"deduct a fixed penalty of ${(a.amount or 0):,.2f} per SLA breach incident")
            elif a.type == "escalation":
                action_str_list.append(f"increase pricing by {(a.rate or 0) * 100:.1f}% for inflation adjustment")
            else:
                action_str_list.append(a.description or "apply contractual adjustment")

        action_text = " AND ".join(action_str_list)

        cap_text = ""
        if rule.caps:
            if rule.caps.max_percentage:
                cap_text = f", subject to a maximum overall ceiling cap of {rule.caps.max_percentage * 100:.0f}%"
            elif rule.caps.max_amount:
                cap_text = f", capped at a maximum liability limit of ${rule.caps.max_amount:,.2f}"

        return (
            f"Rule {rule.rule_id} [{rule.title}]: "
            f"IF {cond_text}, THEN {action_text}{cap_text}. "
            f"(Source: Section {rule.source.section}, Page {rule.source.page})."
        )

    @staticmethod
    def decompile_execution_step(
        rule_type: str,
        rule_code: str,
        rule_title: str,
        input_var: str,
        input_val: Any,
        subtotal: float,
        threshold: Any = None,
        rate_or_amount: Optional[str] = None,
        base_name: str = "contract value",
        base_amount: float = 1000000.0,
    ) -> str:
        """
        Deterministic, Non-LLM human-readable explanation of why the rule was applied
        and how the calculated financial result was obtained.
        """
        formatted_res = format_inr(subtotal)

        if rule_type == "delivery_delay_penalty":
            thresh_num = int(threshold) if threshold is not None else 10
            val_num = int(input_val) if input_val is not None else 0
            if val_num > thresh_num and subtotal > 0:
                rate_str = rate_or_amount or "penalty"
                return (
                    f"Delivery was delayed by {val_num} days, exceeding the allowed {thresh_num} days. "
                    f"A {rate_str} was therefore applied to the {base_name}, resulting in {formatted_res}."
                )
            else:
                return (
                    f"Delivery was completed within the allowed {thresh_num} days ({val_num} days). "
                    f"No delivery delay penalty was assessed, resulting in ₹0."
                )

        elif rule_type == "late_payment_interest":
            thresh_num = int(threshold) if threshold is not None else 30
            val_num = int(input_val) if input_val is not None else 0
            if val_num > thresh_num and subtotal > 0:
                rate_str = rate_or_amount or "monthly interest rate"
                return (
                    f"Payment was delayed by {val_num} days, exceeding the allowed {thresh_num}-day grace period. "
                    f"A {rate_str} was therefore applied to the invoice balance, resulting in {formatted_res}."
                )
            else:
                return (
                    f"Payment was received within the allowed {thresh_num} days ({val_num} days). "
                    f"No overdue interest was assessed, resulting in ₹0."
                )

        elif rule_type == "volume_discount":
            thresh_num = int(threshold) if threshold is not None else 1000
            val_num = int(input_val) if input_val is not None else 0
            if val_num >= thresh_num and subtotal != 0:
                rate_str = rate_or_amount or "volume discount"
                return (
                    f"Order quantity reached {val_num} units, exceeding the tier threshold of {thresh_num} units. "
                    f"A {rate_str} was therefore applied to the contract value, resulting in {formatted_res}."
                )
            else:
                return (
                    f"Order quantity of {val_num} units did not meet the {thresh_num}-unit volume tier threshold. "
                    f"No volume discount was applied, resulting in ₹0."
                )

        elif rule_type == "sla_penalty":
            thresh_num = float(threshold) if threshold is not None else 99.5
            val_num = float(input_val) if input_val is not None else 99.5
            if val_num < thresh_num and subtotal > 0:
                return (
                    f"System uptime dropped to {val_num}%, falling below the contractual {thresh_num}% requirement. "
                    f"An SLA breach penalty deduction was therefore applied, resulting in {formatted_res}."
                )
            else:
                return (
                    f"System uptime achieved {val_num}%, satisfying the contractual {thresh_num}% requirement. "
                    f"Zero SLA deduction was applied, resulting in ₹0."
                )

        else:
            if subtotal != 0:
                return (
                    f"Rule {rule_code} condition was met ({input_var} = {input_val}). "
                    f"Contractual adjustment was applied to the {base_name}, resulting in {formatted_res}."
                )
            else:
                return (
                    f"Rule {rule_code} parameters were within standard contractual boundaries ({input_var} = {input_val}). "
                    f"No financial adjustment was assessed, resulting in ₹0."
                )

    @staticmethod
    def get_step_flow_data(
        rule_code: str,
        rule_title: str,
        rule_type: str,
        rule_ir: Optional[Dict[str, Any]],
        subtotal: float,
        formula: Optional[str],
        input_vars: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Constructs the structured 5-step horizontal execution trace flow data:
        ① INPUT -> ② CONDITION -> ③ RULE APPLIED -> ④ CALCULATION -> ⑤ RESULT
        """
        # Determine variable, operator, threshold, unit
        cond = rule_ir.get("conditions", [{}])[0] if rule_ir and rule_ir.get("conditions") else {}
        action = rule_ir.get("actions", [{}])[0] if rule_ir and rule_ir.get("actions") else {}

        var_name = cond.get("variable", "input_param")
        operator = cond.get("operator", ">")
        threshold = cond.get("value", 0)
        unit = cond.get("unit", "")

        # Human label mapping
        LABEL_MAP = {
            "delivery_delay_days": ("Delivery Delay", "days"),
            "payment_delay_days": ("Payment Delay", "days"),
            "order_quantity": ("Order Quantity", "units"),
            "sla_uptime_percent": ("SLA Uptime", "%"),
            "contract_value": ("Contract Value", ""),
            "invoice_amount": ("Invoice Amount", ""),
        }

        param_label, default_unit = LABEL_MAP.get(var_name, (var_name.replace("_", " ").title(), unit))
        param_unit = unit or default_unit

        # Input value from execution input_vars
        input_val = input_vars.get(var_name, threshold)

        # 1. INPUT step
        unit_suffix = f" {param_unit}".strip()
        input_text = f"{param_label} = {input_val} {unit_suffix}".strip()

        # 2. CONDITION step
        is_triggered = False
        try:
            val_f = float(input_val)
            thresh_f = float(threshold)
            if operator == ">": is_triggered = val_f > thresh_f
            elif operator == ">=": is_triggered = val_f >= thresh_f
            elif operator == "<": is_triggered = val_f < thresh_f
            elif operator == "<=": is_triggered = val_f <= thresh_f
            elif operator == "==": is_triggered = val_f == thresh_f
            else: is_triggered = subtotal != 0
        except Exception:
            is_triggered = subtotal != 0

        condition_text = f"{input_val} {operator} {threshold} → {'TRUE' if is_triggered else 'FALSE'}"

        # 3. RULE APPLIED step
        rule_applied_text = f"{rule_code} – {rule_title}"

        # 4. CALCULATION step
        rate = action.get("rate")
        amount = action.get("amount")
        base_var = action.get("base_variable", "contract_value")
        base_val = input_vars.get(base_var, 1000000.0)

        rate_or_amt_str = ""
        if rate is not None:
            rate_or_amt_str = f"{rate * 100:.1f}%" if (rate * 100) % 1 != 0 else f"{int(rate * 100)}%"
            calc_text = f"{format_inr(base_val)} × {rate_or_amt_str}"
        elif amount is not None:
            rate_or_amt_str = format_inr(amount)
            calc_text = f"{format_inr(amount)} per incident"
        elif formula:
            calc_text = formula.replace("$", "₹")
        else:
            calc_text = format_inr(subtotal)

        # 5. RESULT step
        result_text = format_inr(subtotal)

        # Generate decompiled explanation
        decompiled_explanation = DecompilerService.decompile_execution_step(
            rule_type=rule_type,
            rule_code=rule_code,
            rule_title=rule_title,
            input_var=param_label,
            input_val=input_val,
            subtotal=subtotal,
            threshold=threshold,
            rate_or_amount=rate_or_amt_str,
            base_name="contract value" if base_var == "contract_value" else "invoice balance",
            base_amount=base_val
        )

        return {
            "input_text": input_text,
            "condition_text": condition_text,
            "condition_met": is_triggered,
            "rule_applied_text": rule_applied_text,
            "calculation_text": calc_text,
            "result_text": result_text,
            "decompiled_explanation": decompiled_explanation,
            "parameter_label": param_label,
            "parameter_value": input_val,
            "unit": param_unit,
            "operator": operator,
            "threshold": threshold,
            "subtotal": subtotal
        }
