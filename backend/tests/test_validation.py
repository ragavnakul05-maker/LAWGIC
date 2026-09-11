from app.models.schemas import LegalIR, RuleSourceInfo, RuleCondition, RuleAction, RuleCaps
from app.services.rule_validation_engine import RuleValidationEngine

def test_valid_rule_validation():
    rule = LegalIR(
        rule_id="R001",
        type="late_payment_interest",
        title="Late Payment Interest",
        source=RuleSourceInfo(page=1, section="1.1", text="Sample clause text"),
        conditions=[RuleCondition(variable="payment_delay_days", operator=">", value=30)],
        actions=[RuleAction(type="interest", rate=0.015)],
        caps=RuleCaps(max_percentage=0.15)
    )

    res = RuleValidationEngine.validate_rule(rule)
    assert res.status == "VALID"
    assert len(res.issues) == 0

def test_unknown_variable_flagged_as_review():
    rule = LegalIR(
        rule_id="R999",
        type="custom_type",
        title="Unknown Rule",
        source=RuleSourceInfo(page=1, section="1.1", text="Sample clause"),
        conditions=[RuleCondition(variable="unknown_custom_var", operator=">", value=100)],
        actions=[RuleAction(type="penalty", rate=0.05)]
    )

    res = RuleValidationEngine.validate_rule(rule)
    assert res.status == "NEEDS_REVIEW"
    assert "unknown_custom_var" in res.missing_variables
