"""Tests de supervisión Monitor M2 (fase A)."""
from __future__ import annotations

from core.inventory_channel import channel_key
from core.monitor.supervision import (
    default_supervision_state,
    load_supervision,
    resolve_supervision_targets,
    save_supervision,
    sync_supervision_targets,
    supervision_target_rows,
)
from core.monitor.supervision.device_bandwidth_defaults import default_bandwidth_hz_for_equipo
from core.monitor.supervision.supervision_models import SupervisionState, SupervisionTarget
from core.project_model import Project


def _sample_equipo(**overrides):
    base = {
        "channel_name": "Vocal 1",
        "device_name": "TX-A",
        "channel_number": "1",
        "frequency_mhz": 658.175,
        "model": "ULXD4",
        "series": "ULX-D",
        "band": "K51",
        "color": "#FFAA00",
    }
    base.update(overrides)
    base["channel_key"] = channel_key(base)
    return base


def test_default_bandwidth_from_device_type():
    mic = default_bandwidth_hz_for_equipo(_sample_equipo(model="ULXD4"))
    iem = default_bandwidth_hz_for_equipo(_sample_equipo(model="PSM1000", channel_name="IEM 1"))
    assert mic == 200_000.0
    assert iem == 200_000.0


def test_sync_adds_all_inventory_channels_enabled():
    project = Project.create_new("Test")
    eq = _sample_equipo()
    project.modules["inventario_rf"]["equipos"] = [eq]
    state = default_supervision_state()
    sync_supervision_targets(project, state)
    assert len(state.targets) == 1
    assert state.targets[0].enabled is True
    assert state.targets[0].channel_key == eq["channel_key"]


def test_sync_preserves_manual_bandwidth():
    project = Project.create_new("Test")
    eq = _sample_equipo()
    project.modules["inventario_rf"]["equipos"] = [eq]
    state = SupervisionState(
        targets=[
            SupervisionTarget(
                channel_key=eq["channel_key"],
                enabled=False,
                bandwidth_hz=350_000.0,
                bandwidth_source="manual",
            )
        ]
    )
    sync_supervision_targets(project, state)
    assert state.targets[0].enabled is False
    assert state.targets[0].bandwidth_hz == 350_000.0


def test_sync_drops_removed_channels():
    project = Project.create_new("Test")
    eq = _sample_equipo()
    project.modules["inventario_rf"]["equipos"] = [eq]
    state = SupervisionState(
        targets=[
            SupervisionTarget(channel_key="stale-key", enabled=True),
            SupervisionTarget(channel_key=eq["channel_key"], enabled=True),
        ]
    )
    sync_supervision_targets(project, state)
    assert len(state.targets) == 1
    assert state.targets[0].channel_key == eq["channel_key"]


def test_supervision_persist_roundtrip():
    project = Project.create_new("Test")
    state = default_supervision_state()
    state.settings.log_trigger = "auto"
    state.rules.warning_above_noise_db = 8.0
    state.targets = [SupervisionTarget(channel_key="abc", enabled=True, bandwidth_hz=180_000.0)]
    save_supervision(project, state)
    restored = load_supervision(project)
    assert restored.settings.log_trigger == "auto"
    assert restored.rules.warning_above_noise_db == 8.0
    assert restored.targets[0].channel_key == "abc"


def test_resolve_targets_skips_disabled_and_missing_freq():
    eq_ok = _sample_equipo()
    eq_no_freq = _sample_equipo(frequency_mhz=None, channel_name="Sin freq")
    eq_no_freq["channel_key"] = channel_key(eq_no_freq)
    state = SupervisionState(
        targets=[
            SupervisionTarget(channel_key=eq_ok["channel_key"], enabled=True, bandwidth_hz=200_000.0),
            SupervisionTarget(channel_key=eq_no_freq["channel_key"], enabled=True),
        ]
    )
    resolved = resolve_supervision_targets(state, [eq_ok, eq_no_freq])
    assert len(resolved) == 1
    assert resolved[0].label == "Vocal 1"
    assert abs(resolved[0].frequency_hz - 658.175e6) < 1.0


def test_supervision_target_rows_for_table():
    eq = _sample_equipo()
    state = SupervisionState(
        targets=[SupervisionTarget(channel_key=eq["channel_key"], enabled=True, bandwidth_hz=200_000.0)]
    )
    rows = supervision_target_rows(state, [eq])
    assert len(rows) == 1
    assert rows[0]["label"] == "Vocal 1"
    assert rows[0]["enabled"] is True


def test_supervision_alarm_window_layout_persistence():
    state = SupervisionState()
    state.settings.alarm_window_geometry_b64 = "dGVzdA=="
    state.settings.alarm_window_expanded_groups = ["Main", "Back"]
    state.settings.alarm_window_scroll = 42
    state.settings.alarm_window_visible = True
    restored = SupervisionState.from_dict(state.to_dict())
    assert restored.settings.alarm_window_geometry_b64 == "dGVzdA=="
    assert restored.settings.alarm_window_expanded_groups == ["Main", "Back"]
    assert restored.settings.alarm_window_scroll == 42
    assert restored.settings.alarm_window_visible is True
