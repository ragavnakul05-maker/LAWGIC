from app.models.schemas import LegalIR, RuleSourceInfo, RuleCondition, RuleAction, RuleCaps
from app.services.simulation_engine import SimulationEngine

def test_what_if_scenario_simulation():
    rule = LegalIR(
        rule_id="R002",
        type="delivery_delay_penalty",
        title="Delivery Penalty",
        source=RuleSourceInfo(page=2, section="2.2", text="2% per week delay after 10 days"),
        conditions=[RuleCondition(variable="delivery_delay_days", operator=">", value=10)],
        actions=[RuleAction(type="penalty", rate=0.02, period="week", grace_period_days=10)],
        caps=RuleCaps(max_percentage=0.10)
    )

    baseline_vars = {"contract_value": 1000000.0, "delivery_delay_days": 10} # 0 penalty
    scenarios = [
        {"scenario_name": "Scenario 20 Days Delay", "variable_overrides": {"delivery_delay_days": 20}}, # 2 weeks delay = $40k
        {"scenario_name": "Scenario 40 Days Delay", "variable_overrides": {"delivery_delay_days": 40}}  # 5 weeks delay = $100k (capped)
    ]

    res = SimulationEngine.run_simulation("TEST-SIM", [rule], baseline_vars, scenarios)

    assert res.baseline.financial_impact == 0.0
    assert len(res.scenarios) == 2
    assert res.scenarios[0].financial_impact == 40000.0
    assert res.scenarios[0].difference_from_baseline == 40000.0
    assert res.scenarios[1].financial_impact == 100000.0
    assert res.scenarios[1].difference_from_baseline == 100000.0
