"""Dwell IQ no se programa si el canal digital está en modo solo SNR."""
from __future__ import annotations

from core.monitor.supervision.rules_resolver import set_channel_digital_metrics
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


def test_scheduler_skips_snr_only_digital_channel() -> None:
    scheduler = SupervisionDwellScheduler(periodic_interval_s=0.0, min_global_gap_s=0.0)
    state = SupervisionState(rules=SupervisionRules(digital_metrics_enabled=True))
    set_channel_digital_metrics(state, "ch1", enabled=False, equipos=[_equipo_shure()])
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
        state=state,
        capture_mode="sweep",
        supervision_enabled=True,
        dwell_busy=False,
        now=100.0,
    )
    assert scheduler.take_pending() is None
