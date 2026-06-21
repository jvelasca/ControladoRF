"""Tests política de alarmas y severidades v3."""
from __future__ import annotations

from core.monitor.supervision.alarm_policy_rules import (
    AlarmPolicyRule,
    checks_from_rules,
    format_rule_summary,
    rules_from_checks,
)
from core.monitor.supervision.alarm_presets import BUILTIN_PRESETS, PRESET_ANALOG_STANDARD, AlarmPreset
from core.monitor.supervision.alarm_severity import health_from_severities
from core.monitor.supervision.threshold_checks import CHECK_SNR, ThresholdCheckConfig


def test_rules_from_checks_maps_aviso_critica():
    checks = {
        CHECK_SNR: ThresholdCheckConfig(enabled=True, warning_raise=6.0, critical_raise=3.0),
    }
    rules = rules_from_checks(checks, threshold_mode="noise_relative")
    severities = {rule.severity for rule in rules}
    assert "aviso" in severities
    assert "critica" in severities


def test_checks_from_rules_roundtrip():
    rules = [
        AlarmPolicyRule(rule_id="r1", condition_type="snr_below", threshold=6.0, severity="aviso"),
        AlarmPolicyRule(rule_id="r2", condition_type="snr_below", threshold=3.0, severity="critica"),
    ]
    checks = checks_from_rules(rules, threshold_mode="noise_relative")
    assert checks[CHECK_SNR].warning_raise == 6.0
    assert checks[CHECK_SNR].critical_raise == 3.0


def test_builtin_preset_has_policy_rules():
    from core.monitor.supervision.alarm_policy_rules import ensure_preset_rules

    preset = BUILTIN_PRESETS[PRESET_ANALOG_STANDARD]
    rules = ensure_preset_rules(preset)
    assert rules
    summary = format_rule_summary(rules, threshold_mode="noise_relative", tr=lambda k: k)
    assert summary != "—"


def test_fundamental_presets_exist():
    from core.monitor.supervision.alarm_presets import (
        FUNDAMENTAL_PRESET_ORDER,
        PRESET_ALARM_NORMAL_FM,
        PRESET_ALARM_STRICT_FM,
        PRESET_ALARM_NORMAL_DIG,
        PRESET_ALARM_STRICT_DIG,
        BUILTIN_PRESETS,
        is_fundamental_preset,
        normalize_alarm_preset_id,
    )

    assert PRESET_ALARM_NORMAL_FM in BUILTIN_PRESETS
    assert PRESET_ALARM_STRICT_FM in BUILTIN_PRESETS
    assert PRESET_ALARM_NORMAL_DIG in BUILTIN_PRESETS
    assert PRESET_ALARM_STRICT_DIG in BUILTIN_PRESETS
    assert len(FUNDAMENTAL_PRESET_ORDER) == 4
    assert is_fundamental_preset(PRESET_ALARM_NORMAL_FM)
    assert normalize_alarm_preset_id("alarm_normal") == PRESET_ALARM_NORMAL_FM


def test_list_alarm_threshold_options():
    from core.monitor.supervision.alarm_presets import (
        list_alarm_threshold_preset_options,
        PRESET_ALARM_NORMAL_FM,
    )

    ids = list_alarm_threshold_preset_options()
    assert ids[0] == PRESET_ALARM_NORMAL_FM
    assert len(ids) >= 4


def test_health_rank_prefers_critica():
    assert health_from_severities("aviso", "critica") == "critica"
    assert health_from_severities("comentario", "menor") == "menor"
