"""Tests planificador dwell IQ supervisión."""
from __future__ import annotations

from core.monitor.supervision.measurement_engine import ChannelMeasurement
from core.monitor.supervision.supervision_dwell_scheduler import SupervisionDwellScheduler
from core.monitor.supervision.supervision_models import SupervisionRules, SupervisionState


def _equipo_shure(**overrides):
    base = {
        "channel_key": "ch1",
        "channel_name": "Vocal Shure",
        "manufacturer": "Shure",
        "model": "ULXD4",
        "modulation_class": "digital_qpsk",
    }
    base.update(overrides)
    return base


def test_scheduler_pending_on_periodic_digital_channel() -> None:
    scheduler = SupervisionDwellScheduler(periodic_interval_s=0.0, min_global_gap_s=0.0)
    state = SupervisionRules(digital_metrics_enabled=True)
    sup_state = SupervisionState(rules=state)
    target = type(
        "T",
        (),
        {
            "channel_key": "ch1",
            "enabled": True,
            "label": "Vocal",
            "frequency_hz": 500_000_000.0,
            "bandwidth_hz": 200_000.0,
            "half_bandwidth_hz": 100_000.0,
        },
    )()
    scheduler.consider(
        [],
        resolved=[target],
        equipo_by_key={"ch1": _equipo_shure()},
        state=sup_state,
        capture_mode="sweep",
        supervision_enabled=True,
        dwell_busy=False,
        now=100.0,
    )
    req = scheduler.take_pending()
    assert req is not None
    assert req.channel_key == "ch1"
    assert req.reason == "periodic"


def test_scheduler_snr_degraded_priority() -> None:
    scheduler = SupervisionDwellScheduler(
        periodic_interval_s=999.0,
        min_global_gap_s=0.0,
        snr_recheck_interval_s=0.0,
    )
    sup_state = SupervisionState(rules=SupervisionRules(digital_metrics_enabled=True))
    target = type(
        "T",
        (),
        {
            "channel_key": "ch1",
            "enabled": True,
            "label": "Vocal",
            "frequency_hz": 500_000_000.0,
            "bandwidth_hz": 200_000.0,
            "half_bandwidth_hz": 100_000.0,
        },
    )()
    measurement = ChannelMeasurement(
        channel_key="ch1",
        label="Vocal",
        frequency_hz=500_000_000.0,
        carrier_dbm=-50.0,
        noise_dbm=-60.0,
        snr_above_noise_db=2.0,
    )
    scheduler.consider(
        [measurement],
        resolved=[target],
        equipo_by_key={"ch1": _equipo_shure()},
        state=sup_state,
        capture_mode="sweep",
        supervision_enabled=True,
        dwell_busy=False,
        now=200.0,
    )
    req = scheduler.take_pending()
    assert req is not None
    assert req.reason == "snr_degraded"
