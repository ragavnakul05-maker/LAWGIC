from app.models.schemas import LegalIR, RuleSourceInfo, RuleCondition, RuleAction, RuleCaps
from app.services.decompiler_service import DecompilerService
from app.services.deterministic_rule_engine import DeterministicRuleEngine


def test_decompiler_sla_rule_no_crash():
    rule = LegalIR(
        rule_id='R004',
        type='sla_penalty',
        title='SLA Breach',
        source=RuleSourceInfo(page=4, section='4.1', text='five k per breach'),
        conditions=[RuleCondition(variable='sla_uptime_percent', operator='<', value=99.5, unit='%')],
        actions=[RuleAction(type='sla_deduction', amount=5000.0)],
        caps=RuleCaps(max_amount=50000.0),
    )
    result = DecompilerService.decompile_to_human(rule)
    assert isinstance(result, str)
    assert '5,000.00' in result


def test_decompiler_interest_rule_no_crash():
    rule = LegalIR(
        rule_id='R001',
        type='late_payment_interest',
        title='Late Payment',
        source=RuleSourceInfo(page=1, section='1.1', text='1.5 pct per month'),
        conditions=[RuleCondition(variable='payment_delay_days', operator='>', value=30)],
        actions=[RuleAction(type='interest', rate=0.015, period='month', grace_period_days=30, base_variable='invoice_amount')],
        caps=RuleCaps(max_percentage=0.15),
    )
    result = DecompilerService.decompile_to_human(rule)
    assert isinstance(result, str)
    assert '1.5%' in result


def test_decompiler_zero_rate_no_crash():
    rule = LegalIR(
        rule_id='R006',
        type='late_payment_interest',
        title='Zero Rate',
        source=RuleSourceInfo(page=1, section='1.1', text='0 pct interest'),
        conditions=[RuleCondition(variable='payment_delay_days', operator='>', value=30)],
        actions=[RuleAction(type='interest', rate=0.0, period='month', grace_period_days=30, base_variable='invoice_amount')],
        caps=RuleCaps(),
    )
    result = DecompilerService.decompile_to_human(rule)
    assert isinstance(result, str)
    assert '0.0%' in result


def test_decompiler_all_rule_types_no_crash():
    types_and_actions = [
        ('late_payment_interest', RuleAction(type='interest', rate=0.015, period='month', grace_period_days=30, base_variable='invoice_amount')),
        ('delivery_delay_penalty', RuleAction(type='penalty', rate=0.02, period='week', grace_period_days=10, base_variable='contract_value')),
        ('volume_discount', RuleAction(type='discount', rate=0.05, base_variable='contract_value')),
        ('sla_penalty', RuleAction(type='sla_deduction', amount=5000.0)),
        ('price_escalation', RuleAction(type='escalation', rate=0.03, base_variable='contract_value')),
    ]
    for rule_type, action in types_and_actions:
        rule = LegalIR(
            rule_id='R001',
            type=rule_type,
            title=f'Test {rule_type}',
            source=RuleSourceInfo(page=1, section='1.1', text='test'),
            conditions=[RuleCondition(variable='payment_delay_days', operator='>', value=30)],
            actions=[action],
            caps=RuleCaps(),
        )
        result = DecompilerService.decompile_to_human(rule)
        assert isinstance(result, str), f'{rule_type} decompiler returned non-string'


def test_execution_output_persistence_fields():
    rule = LegalIR(
        rule_id='R001',
        type='late_payment_interest',
        title='Late Payment',
        source=RuleSourceInfo(page=1, section='1.1', text='1.5 pct per month after 30 days'),
        conditions=[RuleCondition(variable='payment_delay_days', operator='>', value=30)],
        actions=[RuleAction(type='interest', rate=0.015, period='month', grace_period_days=30, base_variable='invoice_amount')],
        caps=RuleCaps(max_percentage=0.15),
    )
    result = DeterministicRuleEngine.execute_rules('PERSIST-TEST', [rule], {'invoice_amount': 100000.0, 'payment_delay_days': 35})
    assert result.execution_id and len(result.execution_id) > 0
    assert result.total_financial_impact == 1500.0
    assert result.summary is not None
    assert len(result.calculation_steps) == 1
    step = result.calculation_steps[0]
    assert step.step_number >= 1
    assert step.rule_code == 'R001'
    assert isinstance(step.title, str) and len(step.title) > 0
    assert isinstance(step.description, str) and len(step.description) > 0
    assert step.subtotal == 1500.0
