"""Tests motor de alarmas y evaluación (fase B)."""
from __future__ import annotations

import numpy as np
import time

from core.monitor.spectrum_params import SpectrumFrame
from core.monitor.supervision.alarm_manager import AlarmManager
from core.monitor.supervision.measurement_engine import ChannelMeasurement, measure_channel
from core.monitor.supervision.rule_evaluator import evaluate_channel_health
from core.monitor.supervision.supervision_models import (
    ResolvedSupervisionTarget,
    SupervisionRules,
    SupervisionSettings,
    SupervisionState,
)
from core.monitor.supervision.supervision_engine import SupervisionEngine


def _target(**kwargs) -> ResolvedSupervisionTarget:
    base = dict(
        channel_key="k1",
        enabled=True,
        frequency_hz=100e6,
        bandwidth_hz=200_000.0,
        label="Vocal 1",
        color="#FFAA00",
        device_type="microphone",
    )
    base.update(kwargs)
    return ResolvedSupervisionTarget(**base)


def test_evaluate_channel_health_thresholds():
    rules = SupervisionRules(warning_above_noise_db=6.0, critical_above_noise_db=3.0)
    ok = ChannelMeasurement("k1", "Vocal", 100e6, snr_above_noise_db=10.0)
    warn = ChannelMeasurement("k1", "Vocal", 100e6, snr_above_noise_db=5.0)
    crit = ChannelMeasurement("k1", "Vocal", 100e6, snr_above_noise_db=2.0)
    assert evaluate_channel_health(ok, rules) == "ok"
    assert evaluate_channel_health(warn, rules) == "aviso"
    assert evaluate_channel_health(crit, rules) == "critica"


def test_alarm_manager_debounce_and_latch():
    manager = AlarmManager()
    manager.reset({"k1": ("Vocal 1", 100e6)})
    rules = SupervisionRules(debounce_ms=0)
    settings = SupervisionSettings()
    measurement = ChannelMeasurement(
        "k1",
        "Vocal 1",
        100e6,
        carrier_dbm=-40.0,
        noise_dbm=-50.0,
        snr_above_noise_db=4.0,
    )
    t0 = time.monotonic()
    manager.update(measurement, rules, settings, now_monotonic=t0)
    raised = manager.update(measurement, rules, settings, now_monotonic=t0 + 0.01)
    assert raised
    assert raised[0].phase == "raised"
    assert manager.records["k1"].active_severity == "aviso"

    recovered = ChannelMeasurement(
        "k1",
        "Vocal 1",
        100e6,
        carrier_dbm=-30.0,
        noise_dbm=-50.0,
        snr_above_noise_db=20.0,
    )
    manager.update(recovered, rules, settings, now_monotonic=t0 + 0.05)
    latched = manager.update(recovered, rules, settings, now_monotonic=t0 + 0.06)
    assert latched
    assert latched[0].phase == "latched"
    assert manager.records["k1"].latched_severity == "aviso"
    assert manager.summary_counts().warning_latched == 1


def test_measure_channel_with_local_noise():
    freqs = np.linspace(99.9e6, 100.1e6, 512)
    power = np.full(512, -90.0)
    center_idx = 256
    power[center_idx - 5 : center_idx + 5] = -45.0
    frame = SpectrumFrame(freqs_hz=freqs, power_db=power)
    target = _target()
    measurement = measure_channel(frame, target)
    assert measurement.carrier_dbm is not None
    assert measurement.noise_dbm is not None
    assert measurement.snr_above_noise_db is not None
    assert measurement.snr_above_noise_db > 10.0


def test_alarm_manager_ack_active_critical():
    manager = AlarmManager()
    manager.reset({"k1": ("Vocal 1", 100e6)})
    rules = SupervisionRules(debounce_ms=0)
    settings = SupervisionSettings()
    measurement = ChannelMeasurement(
        "k1",
        "Vocal 1",
        100e6,
        carrier_dbm=-40.0,
        noise_dbm=-50.0,
        snr_above_noise_db=2.0,
    )
    t0 = time.monotonic()
    manager.update(measurement, rules, settings, now_monotonic=t0)
    raised = manager.update(measurement, rules, settings, now_monotonic=t0 + 0.01)
    assert raised
    assert raised[0].phase == "raised"
    assert manager.records["k1"].active_severity == "critica"
    assert manager.pending_attention_count() == 1

    acked = manager.acknowledge("k1")
    assert acked
    assert acked[0].phase == "acked"
    assert manager.records["k1"].active_acknowledged
    assert manager.pending_attention_count() == 0
    rows = manager.alarm_display_rows()
    assert len(rows) == 1
    assert rows[0].acknowledged
    assert not rows[0].can_ack


def test_supervision_engine_process_frame():
    from core.inventory_channel import channel_key

    engine = SupervisionEngine()
    state = SupervisionState()
    equipo = {
        "channel_name": "Vocal 1",
        "frequency_mhz": 100.0,
        "channel_key": "k1",
    }
    equipo["channel_key"] = channel_key(equipo)
    engine.configure(state, [equipo])
    freqs = np.linspace(99.9e6, 100.1e6, 256)
    power = np.full(256, -88.0)
    power[128] = -42.0
    frame = SpectrumFrame(freqs_hz=freqs, power_db=power)
    snapshot = engine.process_frame(frame, engine_running=True, force=True)
    assert snapshot.counts.ok >= 0
