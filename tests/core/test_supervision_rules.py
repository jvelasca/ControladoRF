"""Tests resolución de umbrales de supervisión."""
from __future__ import annotations

from core.inventory_channel import channel_key
from core.monitor.supervision.rules_resolver import (
    SCOPE_CHANNEL,
    SCOPE_MANUFACTURER,
    SCOPE_MODEL,
    clear_rule_override,
    resolve_effective_rules,
    resolve_rules_for_scope,
    rule_override_key,
    set_rule_override,
    validate_rules,
)
from core.monitor.supervision.supervision_models import SupervisionRules, SupervisionState


def _equipo(**overrides):
    base = {
        "channel_name": "Vocal 1",
        "frequency_mhz": 658.175,
        "manufacturer": "Shure",
        "model": "ULXD4",
    }
    base.update(overrides)
    base["channel_key"] = channel_key(base)
    return base


def test_validate_rules_order():
    assert validate_rules(6.0, 3.0)
    assert validate_rules(6.0, 6.0)
    assert not validate_rules(3.0, 6.0)


def test_validate_mer_rules_order():
    from core.monitor.supervision.rules_resolver import validate_mer_rules

    assert validate_mer_rules(22.0, 14.0)
    assert not validate_mer_rules(14.0, 22.0)


def test_resolve_effective_rules_precedence():
    eq = _equipo()
    state = SupervisionState(rules=SupervisionRules(warning_above_noise_db=6.0, critical_above_noise_db=3.0))
    set_rule_override(
        state,
        SCOPE_MANUFACTURER,
        "Shure",
        SupervisionRules(warning_above_noise_db=8.0, critical_above_noise_db=4.0),
    )
    set_rule_override(
        state,
        SCOPE_MODEL,
        "ULXD4",
        SupervisionRules(warning_above_noise_db=7.0, critical_above_noise_db=3.5),
    )
    set_rule_override(
        state,
        SCOPE_CHANNEL,
        eq["channel_key"],
        SupervisionRules(warning_above_noise_db=5.0, critical_above_noise_db=2.0),
    )

    effective = resolve_effective_rules(state, channel_key=eq["channel_key"], equipo=eq)
    assert effective.warning_above_noise_db == 5.0
    assert effective.critical_above_noise_db == 2.0

    clear_rule_override(state, SCOPE_CHANNEL, eq["channel_key"])
    effective = resolve_effective_rules(state, channel_key=eq["channel_key"], equipo=eq)
    assert effective.warning_above_noise_db == 7.0
    assert effective.critical_above_noise_db == 3.5


def test_rule_overrides_persist_in_state_dict():
    state = SupervisionState()
    set_rule_override(
        state,
        SCOPE_MODEL,
        "ULXD4",
        SupervisionRules(warning_above_noise_db=9.0, critical_above_noise_db=4.0, debounce_ms=250),
    )
    restored = SupervisionState.from_dict(state.to_dict())
    key = rule_override_key(SCOPE_MODEL, "ULXD4")
    assert key in restored.rule_overrides
    rules = resolve_rules_for_scope(restored, SCOPE_MODEL, "ULXD4")
    assert rules.warning_above_noise_db == 9.0
    assert rules.debounce_ms == 250


def test_zone_and_device_type_precedence():
    from core.monitor.supervision.rules_resolver import SCOPE_DEVICE_TYPE, SCOPE_ZONE

    eq = _equipo(zone="Escenario", device_type="microphone")
    state = SupervisionState(rules=SupervisionRules(warning_above_noise_db=6.0, critical_above_noise_db=3.0))
    set_rule_override(
        state,
        SCOPE_ZONE,
        "Escenario",
        SupervisionRules(warning_above_noise_db=8.0, critical_above_noise_db=4.0),
    )
    set_rule_override(
        state,
        SCOPE_DEVICE_TYPE,
        "microphone",
        SupervisionRules(warning_above_noise_db=7.0, critical_above_noise_db=3.5),
    )
    effective = resolve_effective_rules(state, channel_key=eq["channel_key"], equipo=eq)
    assert effective.warning_above_noise_db == 7.0
    assert effective.critical_above_noise_db == 3.5
