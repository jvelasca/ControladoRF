"""Tests evaluación MER digital para supervisión."""
from core.monitor.supervision.digital_rule_evaluator import evaluate_digital_mer_health
from core.monitor.supervision.supervision_models import SupervisionRules


def test_mer_warning_threshold() -> None:
    rules = SupervisionRules(digital_metrics_enabled=True, mer_warning_db=22.0, mer_critical_db=14.0)
    assert evaluate_digital_mer_health(mer_db=25.0, sync_ok=True, rules=rules) == "ok"
    assert evaluate_digital_mer_health(mer_db=18.0, sync_ok=True, rules=rules) == "aviso"
    assert evaluate_digital_mer_health(mer_db=10.0, sync_ok=True, rules=rules) == "critica"


def test_sync_lost_is_critical() -> None:
    rules = SupervisionRules(digital_metrics_enabled=True)
    assert evaluate_digital_mer_health(mer_db=30.0, sync_ok=False, rules=rules) == "critica"
