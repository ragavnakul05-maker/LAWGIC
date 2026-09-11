from typing import List, Dict, Any
from app.models.schemas import (
    LegalIR, SimulationRequest, SimulationResponse, ScenarioComparisonItem
)
from app.services.deterministic_rule_engine import DeterministicRuleEngine

class SimulationEngine:
    @staticmethod
    def run_simulation(
        contract_id: str,
        rules: List[LegalIR],
        baseline_variables: Dict[str, Any],
        scenarios_input: List[Dict[str, Any]]
    ) -> SimulationResponse:
        """
        Runs deterministic what-if scenario simulations.
        Reuses DeterministicRuleEngine for zero-hallucination, 100% reproducible scenario testing.
        """
        # 1. Execute Baseline
        baseline_exec = DeterministicRuleEngine.execute_rules(
            contract_id=contract_id,
            rules=rules,
            variables=baseline_variables,
            scenario_name="Baseline Execution"
        )
        baseline_val = baseline_exec.total_financial_impact

        baseline_item = ScenarioComparisonItem(
            scenario_name="Baseline",
            variables=baseline_variables,
            financial_impact=baseline_val,
            difference_from_baseline=0.0,
            percentage_change=0.0,
            calculation_summary=baseline_exec.human_explanation
        )

        scenario_items: List[ScenarioComparisonItem] = []
        visual_data: List[Dict[str, Any]] = [
            {
                "name": "Baseline",
                "impact": baseline_val,
                "applied_rules": len(baseline_exec.applied_rules)
            }
        ]

        # 2. Execute Each Scenario Override
        for sc in scenarios_input:
            name = sc.get("scenario_name", "Scenario")
            overrides = sc.get("variable_overrides", {})
            
            # Merge baseline with scenario overrides
            merged_vars = {**baseline_variables, **overrides}

            sc_exec = DeterministicRuleEngine.execute_rules(
                contract_id=contract_id,
                rules=rules,
                variables=merged_vars,
                scenario_name=name
            )

            sc_val = sc_exec.total_financial_impact
            diff = sc_val - baseline_val
            pct_change = (diff / abs(baseline_val) * 100.0) if baseline_val != 0 else (100.0 if diff > 0 else 0.0)

            item = ScenarioComparisonItem(
                scenario_name=name,
                variables=merged_vars,
                financial_impact=sc_val,
                difference_from_baseline=round(diff, 2),
                percentage_change=round(pct_change, 2),
                calculation_summary=sc_exec.human_explanation
            )
            scenario_items.append(item)

            visual_data.append({
                "name": name,
                "impact": sc_val,
                "difference": round(diff, 2),
                "applied_rules": len(sc_exec.applied_rules)
            })

        return SimulationResponse(
            contract_id=contract_id,
            baseline=baseline_item,
            scenarios=scenario_items,
            visual_data=visual_data
        )
