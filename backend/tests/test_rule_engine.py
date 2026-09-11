from app.models.schemas import LegalIR, RuleSourceInfo, RuleCondition, RuleAction, RuleCaps
from app.services.deterministic_rule_engine import DeterministicRuleEngine

def test_late_payment_interest_execution():
    rule = LegalIR(
        rule_id="R001",
        type="late_payment_interest",
        title="Late Interest",
        source=RuleSourceInfo(page=3, section="3.2", text="1.5% interest per month after 30 days"),
        conditions=[RuleCondition(variable="payment_delay_days", operator=">", value=30, unit="days")],
        actions=[RuleAction(type="interest", rate=0.015, period="month", grace_period_days=30, base_variable="invoice_amount")],
        caps=RuleCaps(max_percentage=0.15)
    )

    # 35 days delay (5 days past grace period -> 1 month)
    variables = {"invoice_amount": 100000.0, "payment_delay_days": 35}
    res = DeterministicRuleEngine.execute_rules("TEST-01", [rule], variables)

    assert len(res.applied_rules) == 1
    assert "R001" in res.applied_rules
    # $100,000 * 0.015 * 1 month = $1,500
    assert res.total_financial_impact == 1500.0
    assert len(res.calculation_steps) == 1
    assert res.calculation_steps[0].subtotal == 1500.0

def test_delivery_delay_penalty_with_cap():
    rule = LegalIR(
        rule_id="R002",
        type="delivery_delay_penalty",
        title="Delivery Penalty",
        source=RuleSourceInfo(page=2, section="2.2", text="2% per week delay, max 10%"),
        conditions=[RuleCondition(variable="delivery_delay_days", operator=">", value=10, unit="days")],
        actions=[RuleAction(type="penalty", rate=0.02, period="week", grace_period_days=10, base_variable="contract_value")],
        caps=RuleCaps(max_percentage=0.10)
    )

    # 80 days delay -> 70 days past grace = 10 weeks delay.
    # Raw penalty = $1,000,000 * 0.02 * 10 weeks = $200,000.
    # Capped at 10% = $100,000.
    variables = {"contract_value": 1000000.0, "delivery_delay_days": 80}
    res = DeterministicRuleEngine.execute_rules("TEST-02", [rule], variables)

    assert res.total_financial_impact == 100000.0 # Exactly capped at $100k
    assert "Capped at maximum contractual penalty limit" in res.calculation_steps[0].description

def test_volume_discount():
    rule = LegalIR(
        rule_id="R003",
        type="volume_discount",
        title="Volume Discount",
        source=RuleSourceInfo(page=1, section="1.2", text="5% discount for >= 1000 units"),
        conditions=[RuleCondition(variable="order_quantity", operator=">=", value=1000, unit="units")],
        actions=[RuleAction(type="discount", rate=0.05, base_variable="contract_value")],
        caps=RuleCaps()
    )

    variables = {"contract_value": 500000.0, "order_quantity": 1500}
    res = DeterministicRuleEngine.execute_rules("TEST-03", [rule], variables)

    # $500,000 * 0.05 = -$25,000 (discount reduces cost)
    assert res.total_financial_impact == -25000.0
