"""Planificador de dwell IQ para métricas digitales en supervisión por barrido."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.monitor.supervision.digital_supervision import is_digital_modulation_class
from core.monitor.supervision.measurement_engine import ChannelMeasurement
from core.monitor.supervision.rule_evaluator import evaluate_channel_health
from core.monitor.supervision.rules_resolver import resolve_effective_rules
from core.monitor.supervision.supervision_models import ResolvedSupervisionTarget, SupervisionState


@dataclass(frozen=True)
class SupervisionDwellRequest:
    channel_key: str
    label: str
    frequency_hz: float
    reason: str  # snr_degraded | periodic


class SupervisionDwellScheduler:
    """Elige un canal digital para captura IQ puntual durante supervisión en barrido."""

    def __init__(
        self,
        *,
        periodic_interval_s: float = 60.0,
        min_global_gap_s: float = 4.0,
        snr_recheck_interval_s: float = 12.0,
    ) -> None:
        self._periodic_interval_s = max(15.0, float(periodic_interval_s))
        self._min_global_gap_s = max(1.0, float(min_global_gap_s))
        self._snr_recheck_interval_s = max(5.0, float(snr_recheck_interval_s))
        self._last_dwell_at: Dict[str, float] = {}
        self._last_global_dwell_at = 0.0
        self._pending: SupervisionDwellRequest | None = None

    def reset(self) -> None:
        self._last_dwell_at.clear()
        self._last_global_dwell_at = 0.0
        self._pending = None

    def configure(
        self,
        *,
        periodic_interval_s: float | None = None,
        min_global_gap_s: float | None = None,
        snr_recheck_interval_s: float | None = None,
    ) -> None:
        if periodic_interval_s is not None:
            self._periodic_interval_s = max(15.0, float(periodic_interval_s))
        if min_global_gap_s is not None:
            self._min_global_gap_s = max(1.0, float(min_global_gap_s))
        if snr_recheck_interval_s is not None:
            self._snr_recheck_interval_s = max(5.0, float(snr_recheck_interval_s))

    def take_pending(self) -> SupervisionDwellRequest | None:
        req = self._pending
        self._pending = None
        return req

    def mark_dwell_started(self, channel_key: str, *, now: float | None = None) -> None:
        ts = time.monotonic() if now is None else float(now)
        self._last_global_dwell_at = ts
        self._last_dwell_at[str(channel_key)] = ts
        self._pending = None

    def consider(
        self,
        measurements: List[ChannelMeasurement],
        *,
        resolved: List[ResolvedSupervisionTarget],
        equipo_by_key: Dict[str, dict],
        state: SupervisionState,
        capture_mode: str,
        supervision_enabled: bool,
        dwell_busy: bool,
        now: float | None = None,
    ) -> None:
        if self._pending is not None or dwell_busy:
            return
        if capture_mode != "sweep" or not supervision_enabled:
            return
        ts = time.monotonic() if now is None else float(now)
        if ts - self._last_global_dwell_at < self._min_global_gap_s:
            return

        targets_by_key = {target.channel_key: target for target in resolved if target.enabled}
        measurement_by_key = {item.channel_key: item for item in measurements}

        priority: list[tuple[int, float, SupervisionDwellRequest]] = []

        for target in resolved:
            if not target.enabled:
                continue
            equipo = equipo_by_key.get(target.channel_key) or {}
            modulation = str(equipo.get("modulation_class") or "analog_fm")
            if not is_digital_modulation_class(modulation):
                continue
            rules = resolve_effective_rules(
                state,
                channel_key=target.channel_key,
                equipo=equipo,
            )
            if not rules.digital_metrics_enabled:
                continue
            last = self._last_dwell_at.get(target.channel_key, 0.0)
            measurement = measurement_by_key.get(target.channel_key)
            health = (
                evaluate_channel_health(measurement, rules)
                if measurement is not None
                else "unknown"
            )
            if health in ("warning", "critical"):
                if ts - last >= self._snr_recheck_interval_s:
                    priority.append(
                        (
                            0,
                            target.frequency_hz,
                            SupervisionDwellRequest(
                                channel_key=target.channel_key,
                                label=target.label,
                                frequency_hz=target.frequency_hz,
                                reason="snr_degraded",
                            ),
                        )
                    )
                continue
            if ts - last >= self._periodic_interval_s:
                priority.append(
                    (
                        1,
                        target.frequency_hz,
                        SupervisionDwellRequest(
                            channel_key=target.channel_key,
                            label=target.label,
                            frequency_hz=target.frequency_hz,
                            reason="periodic",
                        ),
                    )
                )

        if not priority:
            return
        priority.sort(key=lambda item: (item[0], item[1]))
        self._pending = priority[0][2]
