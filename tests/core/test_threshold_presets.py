"""Tests presets y resolución de matriz de umbrales."""
from __future__ import annotations

from core.inventory_channel import channel_key
from core.monitor.supervision.alarm_presets import (
    PRESET_ANALOG_STANDARD,
    PRESET_DIGITAL_QPSK,
    PRESET_UNSUPERVISED,
    infer_preset_for_equipo,
)
from core.monitor.supervision.supervision_models import SupervisionState, SupervisionTarget
from core.monitor.supervision.threshold_checks import CHECK_MER, CHECK_SNR
from core.monitor.supervision.threshold_resolver import (
    apply_preset_to_channels,
    resolve_effective_thresholds,
    resolve_preset_id,
    set_channel_mer_thresholds,
    set_channel_snr_thresholds,
)


def _equipo(**overrides):
    base = {
        "channel_name": "Vocal 1",
        "frequency_mhz": 658.175,
        "manufacturer": "Shure",
        "model": "ULXD4",
        "device_type": "microphone",
        "modulation_class": "digital_qpsk",
    }
    base.update(overrides)
    base["channel_key"] = channel_key(base)
    return base


def test_infer_preset_digital_qpsk():
    eq = _equipo()
    assert infer_preset_for_equipo(eq) == PRESET_DIGITAL_QPSK


def test_infer_preset_analog_microphone():
    eq = _equipo(modulation_class="analog_fm", model="SM58")
    assert infer_preset_for_equipo(eq) == PRESET_ANALOG_STANDARD


def test_resolve_preset_from_target():
    eq = _equipo()
    target = SupervisionTarget(channel_key=eq["channel_key"], preset_id=PRESET_ANALOG_STANDARD)
    state = SupervisionState(targets=[target])
    assert resolve_preset_id(state, channel_key=eq["channel_key"], equipo=eq, target=target) == PRESET_ANALOG_STANDARD


def test_resolve_preset_uses_active_alarm_preset():
    from core.monitor.supervision.alarm_presets import PRESET_ALARM_STRICT

    eq = _equipo()
    target = SupervisionTarget(channel_key=eq["channel_key"])
    state = SupervisionState(
        targets=[target],
        active_alarm_preset_id=PRESET_ALARM_STRICT,
    )
    assert (
        resolve_preset_id(state, channel_key=eq["channel_key"], equipo=eq, target=target)
        == PRESET_ALARM_STRICT
    )


def test_channel_snr_override():
    eq = _equipo()
    target = SupervisionTarget(channel_key=eq["channel_key"], preset_id=PRESET_DIGITAL_QPSK)
    state = SupervisionState(targets=[target])
    set_channel_snr_thresholds(state, eq["channel_key"], warning_db=9.0, critical_db=4.5)
    resolved = resolve_effective_thresholds(state, channel_key=eq["channel_key"], equipo=eq, target=target)
    snr = resolved.checks[CHECK_SNR]
    assert snr.warning_raise == 9.0
    assert snr.critical_raise == 4.5
    assert resolved.has_channel_overrides


def test_channel_mer_override_enables_digital():
    eq = _equipo()
    target = SupervisionTarget(channel_key=eq["channel_key"], preset_id=PRESET_ANALOG_STANDARD)
    state = SupervisionState(targets=[target])
    set_channel_mer_thresholds(state, eq["channel_key"], warning_db=20.0, critical_db=12.0)
    resolved = resolve_effective_thresholds(state, channel_key=eq["channel_key"], equipo=eq, target=target)
    rules = resolved.to_supervision_rules()
    assert rules.digital_metrics_enabled
    assert resolved.checks[CHECK_MER].warning_raise == 20.0


def test_unsupervised_preset_disables_checks():
    eq = _equipo()
    target = SupervisionTarget(channel_key=eq["channel_key"], preset_id=PRESET_UNSUPERVISED)
    state = SupervisionState(targets=[target])
    resolved = resolve_effective_thresholds(state, channel_key=eq["channel_key"], equipo=eq, target=target)
    assert not resolved.checks[CHECK_SNR].enabled
    assert not resolved.checks[CHECK_MER].enabled


def test_supervision_state_persists_preset_fields():
    eq = _equipo()
    target = SupervisionTarget(
        channel_key=eq["channel_key"],
        preset_id=PRESET_DIGITAL_QPSK,
        check_overrides={CHECK_SNR: {"warning_raise": 7.0, "critical_raise": 3.5}},
    )
    state = SupervisionState(targets=[target], default_preset_id=PRESET_ANALOG_STANDARD)
    restored = SupervisionState.from_dict(state.to_dict())
    assert restored.version >= 2
    assert restored.default_preset_id == PRESET_ANALOG_STANDARD
    assert restored.active_alarm_preset_id == "alarm_normal_fm"
    assert restored.targets[0].preset_id == PRESET_DIGITAL_QPSK
    assert restored.targets[0].check_overrides[CHECK_SNR]["warning_raise"] == 7.0


def test_apply_preset_to_channels_bulk() -> None:
    eq1 = {"channel_name": "A", "frequency_mhz": 500.0}
    eq2 = {"channel_name": "B", "frequency_mhz": 510.0}
    eq1["channel_key"] = channel_key(eq1)
    eq2["channel_key"] = channel_key(eq2)
    state = SupervisionState(
        targets=[
            SupervisionTarget(channel_key=eq1["channel_key"]),
            SupervisionTarget(channel_key=eq2["channel_key"]),
        ]
    )
    count = apply_preset_to_channels(
        state,
        [eq1["channel_key"], eq2["channel_key"]],
        PRESET_DIGITAL_QPSK,
    )
    assert count == 2
    assert state.targets[0].preset_id == PRESET_DIGITAL_QPSK
    assert state.targets[1].preset_id == PRESET_DIGITAL_QPSK
