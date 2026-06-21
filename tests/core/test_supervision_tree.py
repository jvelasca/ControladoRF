"""Tests árbol de supervisión."""
from __future__ import annotations

from core.monitor.supervision.supervision_models import ResolvedSupervisionTarget
from core.monitor.supervision.supervision_tree import (
    build_supervision_tree,
    merge_rollups,
    resolve_tree_icon_tone,
    rollup_from_alarm_state,
    tree_icon_tone_blinks,
)


def _target(**kwargs) -> ResolvedSupervisionTarget:
    base = dict(
        channel_key="k1",
        enabled=True,
        frequency_hz=100e6,
        bandwidth_hz=200_000.0,
        label="Vocal 1",
        color="#FFAA00",
        device_type="microphone",
        zone="Main",
    )
    base.update(kwargs)
    return ResolvedSupervisionTarget(**base)


def test_rollup_priority():
    assert rollup_from_alarm_state("ok") == "ok"
    assert rollup_from_alarm_state("warning_latched") == "warning_latched"
    assert rollup_from_alarm_state("warning") == "warning"
    assert rollup_from_alarm_state("critical") == "critical"
    assert merge_rollups("ok", "warning") == "warning"
    assert merge_rollups("warning_latched", "critical") == "critical"


def test_build_supervision_tree_by_zone():
    targets = [
        _target(channel_key="k1", label="A", zone="Main"),
        _target(channel_key="k2", label="B", zone="Back"),
    ]
    equipos = [
        {"channel_key": "k1", "zone": "Main", "frequency_mhz": 100.0},
        {"channel_key": "k2", "zone": "Back", "frequency_mhz": 200.0},
    ]
    groups = build_supervision_tree(
        targets,
        equipos,
        {"k1": "ok", "k2": "critical"},
        group_mode="zone",
        tr=lambda key: key,
    )
    assert len(groups) == 2
    critical_group = next(group for group in groups if group.rollup == "critical")
    assert critical_group.channel_count == 1


def test_build_supervision_tree_flat():
    targets = [_target(channel_key="k1")]
    equipos = [{"channel_key": "k1", "frequency_mhz": 100.0}]
    groups = build_supervision_tree(
        targets,
        equipos,
        {"k1": "warning_latched"},
        group_mode="none",
        tr=lambda key: key,
    )
    assert len(groups) == 1
    assert groups[0].rollup == "warning_latched"
    assert groups[0].channel_count == 1


def test_build_supervision_tree_shows_metrics_for_digital() -> None:
    from core.monitor.supervision.supervision_models import SupervisionChannelMetrics

    targets = [_target(channel_key="k1", label="Shure A")]
    equipos = [{"channel_key": "k1", "modulation_class": "digital_qpsk", "frequency_mhz": 500.0}]
    metrics = {
        "k1": SupervisionChannelMetrics(
            channel_key="k1",
            snr_db=12.5,
            mer_db=24.0,
            sync_ok=True,
            digital_mode="snr_and_mer",
        )
    }
    groups = build_supervision_tree(
        targets,
        equipos,
        {"k1": "ok"},
        group_mode="none",
        channel_metrics=metrics,
        tr=lambda key: key,
    )
    channel = groups[0].channels[0]
    assert channel.is_digital is True
    assert channel.snr_db == 12.5
    assert channel.mer_db == 24.0
    assert channel.digital_mode == "snr_and_mer"


def test_build_supervision_tree_includes_disabled():
    targets = [
        _target(channel_key="k1", enabled=True),
        _target(channel_key="k2", enabled=False, label="Off"),
    ]
    equipos = [
        {"channel_key": "k1", "frequency_mhz": 100.0},
        {"channel_key": "k2", "frequency_mhz": 200.0},
    ]
    groups = build_supervision_tree(
        targets,
        equipos,
        {"k1": "critical", "k2": "critical"},
        group_mode="none",
        tr=lambda key: key,
    )
    assert len(groups) == 1
    assert groups[0].channel_count == 2
    assert groups[0].rollup == "critical"
    disabled = next(channel for channel in groups[0].channels if channel.channel_key == "k2")
    assert disabled.enabled is False
    assert disabled.rollup == "ok"


def test_resolve_tree_icon_tone_acknowledged():
    from core.monitor.supervision.supervision_models import AlarmDisplayRow

    row = AlarmDisplayRow(
        channel_key="k1",
        label="A",
        frequency_mhz=100.0,
        severity="critica",
        phase="active",
        acknowledged=True,
        can_ack=False,
    )
    assert resolve_tree_icon_tone("critical", alarm_row=row) == "acknowledged"
    assert tree_icon_tone_blinks("acknowledged") is False


def test_resolve_tree_icon_tone_comentario():
    from core.monitor.supervision.supervision_models import AlarmDisplayRow

    row = AlarmDisplayRow(
        channel_key="k1",
        label="A",
        frequency_mhz=100.0,
        severity="comentario",
        phase="active",
    )
    assert resolve_tree_icon_tone("comentario", alarm_row=row) == "comentario"
    assert tree_icon_tone_blinks("comentario") is False


def test_build_supervision_tree_comentario_tone():
    targets = [_target(channel_key="k1")]
    equipos = [{"channel_key": "k1", "frequency_mhz": 100.0}]
    groups = build_supervision_tree(
        targets,
        equipos,
        {"k1": "comentario"},
        group_mode="none",
        tr=lambda key: key,
    )
    assert groups[0].channels[0].icon_tone == "comentario"
