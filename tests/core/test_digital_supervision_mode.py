"""Tests modo supervisión digital SNR vs MER."""
from __future__ import annotations

from core.monitor.supervision.digital_supervision import (
    digital_metrics_enabled_for_mode,
    digital_supervision_mode_from_rules,
    effective_digital_mode_for_equipo,
)
from core.monitor.supervision.rules_resolver import (
    resolve_effective_rules,
    set_channel_digital_metrics,
)
from core.monitor.supervision.supervision_models import SupervisionRules, SupervisionState


def test_digital_mode_helpers() -> None:
    assert digital_supervision_mode_from_rules(True) == "snr_and_mer"
    assert digital_supervision_mode_from_rules(False) == "snr_only"
    assert digital_metrics_enabled_for_mode("snr_and_mer") is True
    assert digital_metrics_enabled_for_mode("snr_only") is False


def test_effective_mode_for_analog() -> None:
    assert (
        effective_digital_mode_for_equipo(
            modulation_class="analog_fm",
            digital_metrics_enabled=True,
        )
        == "none"
    )


def test_channel_override_snr_only() -> None:
    state = SupervisionState(rules=SupervisionRules(digital_metrics_enabled=True))
    equipo = {
        "channel_key": "ch1",
        "modulation_class": "digital_qpsk",
        "manufacturer": "Shure",
    }
    set_channel_digital_metrics(state, "ch1", enabled=False, equipos=[equipo])
    rules = resolve_effective_rules(state, channel_key="ch1", equipo=equipo)
    assert rules.digital_metrics_enabled is False
    mode = effective_digital_mode_for_equipo(
        modulation_class="digital_qpsk",
        digital_metrics_enabled=rules.digital_metrics_enabled,
    )
    assert mode == "snr_only"
