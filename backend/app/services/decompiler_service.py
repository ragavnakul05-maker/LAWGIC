from app.models.schemas import LegalIR

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
                action_str_list.append(f"assess a monthly interest penalty of {a.rate * 100:.1f}% on the invoice amount")
            elif a.type == "penalty":
                action_str_list.append(f"charge a liquidated damages penalty of {a.rate * 100:.1f}% per week on total contract value")
            elif a.type == "discount":
                action_str_list.append(f"grant a volume price discount of {a.rate * 100:.1f}%")
            elif a.type == "sla_deduction":
                action_str_list.append(f"deduct a fixed penalty of ${a.amount:,.2f} per SLA breach incident")
            elif a.type == "escalation":
                action_str_list.append(f"increase pricing by {a.rate * 100:.1f}% for inflation adjustment")
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
