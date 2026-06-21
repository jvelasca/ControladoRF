"""Estados de alarma por canal — debounce, latch y ack."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

from core.monitor.supervision.alarm_catalog import resolve_alarm_type
from core.monitor.supervision.measurement_engine import ChannelMeasurement
from core.monitor.supervision.alarm_severity import (
    AlarmSeverityLevel,
    LEGACY_SEVERITY_TO_CANONICAL,
    normalize_severity,
)
from core.monitor.supervision.rule_evaluator import (
    ChannelHealth,
    evaluate_channel_health,
    evaluate_channel_health_from_checks,
)
from core.monitor.supervision.supervision_models import (
    AlarmSummaryCounts,
    ChannelReferenceCapture,
    SupervisionRules,
    SupervisionSettings,
)
from core.monitor.supervision.threshold_checks import ThresholdCheckConfig, CHECK_DIG_SYNC

_ACTIVE_ALARM_HEALTH = frozenset({"critica", "menor", "aviso"})
_ALL_ALARM_HEALTH = frozenset({"comentario", "aviso", "menor", "critica"})


def _valid_committed(health: ChannelHealth) -> ChannelHealth:
    if health in ("ok", "unknown", "comentario", "aviso", "menor", "critica"):
        return health
    mapped = normalize_severity(str(health))
    return mapped or "ok"


def _is_actionable_health(health: ChannelHealth) -> bool:
    return health in _ACTIVE_ALARM_HEALTH


AlarmSeverity = AlarmSeverityLevel


@dataclass
class ChannelAlarmRecord:
    channel_key: str
    label: str
    frequency_hz: float
    health: ChannelHealth = "unknown"
    active_severity: Optional[AlarmSeverity] = None
    latched_severity: Optional[AlarmSeverity] = None
    active_acknowledged: bool = False
    carrier_dbm: Optional[float] = None
    noise_dbm: Optional[float] = None
    snr_above_noise_db: Optional[float] = None
    mer_db: Optional[float] = None
    digital_sync_ok: Optional[bool] = None
    latched_at: float = 0.0
    ack_at: float = 0.0

    @property
    def display_severity(self) -> Optional[AlarmSeverity]:
        if self.active_severity is not None:
            return self.active_severity
        return self.latched_severity


@dataclass
class _PendingHealth:
    health: ChannelHealth
    since_monotonic: float


@dataclass
class AlarmTransition:
    channel_key: str
    label: str
    frequency_hz: float
    severity: AlarmSeverity
    phase: Literal["raised", "latched", "cleared", "acked"]
    alarm_type: str
    rule: str
    message: str
    carrier_dbm: Optional[float]
    noise_dbm: Optional[float]
    snr_above_noise_db: Optional[float]
    threshold_db: float


@dataclass
class AlarmManager:
    records: Dict[str, ChannelAlarmRecord] = field(default_factory=dict)
    _pending: Dict[str, _PendingHealth] = field(default_factory=dict)
    _committed: Dict[str, ChannelHealth] = field(default_factory=dict)
    _digital_pending: Dict[str, _PendingHealth] = field(default_factory=dict)
    _digital_committed: Dict[str, ChannelHealth] = field(default_factory=dict)

    def reset(self, labels: Dict[str, tuple[str, float]]) -> None:
        """``labels``: channel_key → (label, frequency_hz)."""
        self.records = {
            key: ChannelAlarmRecord(
                channel_key=key,
                label=str(label),
                frequency_hz=float(freq_hz),
            )
            for key, (label, freq_hz) in labels.items()
        }
        self._pending.clear()
        self._committed = {key: "unknown" for key in labels}
        self._digital_pending.clear()
        self._digital_committed = {key: "unknown" for key in labels}

    def update_digital(
        self,
        *,
        channel_key: str,
        label: str,
        frequency_hz: float,
        mer_db: Optional[float],
        sync_ok: bool,
        rules: SupervisionRules,
        settings: SupervisionSettings,
        checks: Dict[str, ThresholdCheckConfig] | None = None,
        threshold_mode: str = "noise_relative",
        reference: ChannelReferenceCapture | None = None,
        now_monotonic: float | None = None,
    ) -> List[AlarmTransition]:
        from core.monitor.supervision.digital_rule_evaluator import (
            digital_debounce_ms_from_checks,
            digital_health_to_channel_health,
            evaluate_digital_health_from_checks,
            evaluate_digital_mer_health,
        )

        if not rules.digital_metrics_enabled and not checks:
            return []
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        record = self.records.get(channel_key)
        if record is None:
            record = ChannelAlarmRecord(
                channel_key=channel_key,
                label=label,
                frequency_hz=frequency_hz,
            )
            self.records[channel_key] = record
        record.label = label
        record.frequency_hz = frequency_hz
        record.mer_db = mer_db
        record.digital_sync_ok = sync_ok

        committed = self._digital_committed.get(channel_key, "ok")
        if checks:
            digital_health = evaluate_digital_health_from_checks(
                mer_db=mer_db,
                sync_ok=sync_ok,
                checks=checks,
                rules=rules,
                threshold_mode=threshold_mode,
                reference=reference,
                committed=_valid_committed(committed),
            )
            raw = digital_health_to_channel_health(digital_health)
            sync_cfg = checks.get(CHECK_DIG_SYNC)
            rule_prefix = "dig_sync" if sync_cfg and sync_cfg.enabled and not sync_ok else "mer"
            debounce_ms = digital_debounce_ms_from_checks(checks, rules)
        else:
            if not sync_ok:
                raw = "critica"
                rule_prefix = "dig_sync"
            else:
                raw = digital_health_to_channel_health(
                    evaluate_digital_mer_health(mer_db=mer_db, sync_ok=sync_ok, rules=rules)
                )
                rule_prefix = "mer"
            debounce_ms = int(rules.digital_debounce_ms)

        record.health = raw
        pending = self._digital_pending.get(channel_key)
        debounce_s = max(debounce_ms, 0) / 1000.0
        if pending is None or pending.health != raw:
            self._digital_pending[channel_key] = _PendingHealth(raw, now)
            return []
        if now - pending.since_monotonic < debounce_s:
            return []

        previous = self._digital_committed.get(channel_key, "unknown")
        if previous == raw:
            return self._apply_auto_reset(record, settings, now)

        self._digital_committed[channel_key] = raw
        transitions = self._transition_digital_record(
            record,
            previous,
            raw,
            rules,
            rule_prefix,
            now,
            checks=checks,
            threshold_mode=threshold_mode,
            reference=reference,
        )
        transitions.extend(self._apply_auto_reset(record, settings, now))
        return transitions

    def _transition_digital_record(
        self,
        record: ChannelAlarmRecord,
        previous: ChannelHealth,
        current: ChannelHealth,
        rules: SupervisionRules,
        rule_prefix: str,
        now: float,
        *,
        checks: Dict[str, ThresholdCheckConfig] | None = None,
        threshold_mode: str = "noise_relative",
        reference: ChannelReferenceCapture | None = None,
    ) -> List[AlarmTransition]:
        from core.monitor.supervision.threshold_checks import CHECK_MER

        transitions: List[AlarmTransition] = []
        mer_cfg = (checks or {}).get(CHECK_MER)
        nominal_mer = (
            threshold_mode == "nominal_delta"
            and reference is not None
            and reference.mer_db is not None
            and mer_cfg is not None
            and mer_cfg.enabled
        )
        if current in _ALL_ALARM_HEALTH:
            severity: AlarmSeverity = current  # type: ignore[assignment]
            if current == "comentario":
                transitions.append(
                    AlarmTransition(
                        channel_key=record.channel_key,
                        label=record.label,
                        frequency_hz=record.frequency_hz,
                        severity="comentario",
                        phase="raised",
                        alarm_type=resolve_alarm_type(rule="mer_comment", phase="raised", severity="comentario"),
                        rule="mer_comment",
                        message=self._format_digital_message(record, "comentario"),
                        carrier_dbm=record.carrier_dbm,
                        noise_dbm=record.noise_dbm,
                        snr_above_noise_db=record.snr_above_noise_db,
                        threshold_db=0.0,
                    )
                )
                return transitions
            record.active_severity = severity
            record.active_acknowledged = False
            record.latched_severity = None
            record.latched_at = 0.0
            record.ack_at = 0.0
            if rule_prefix == "dig_sync":
                rule = "dig_sync_lost"
                threshold = 0.0
            elif nominal_mer:
                rule = f"mer_drop_{severity}"
                threshold = (
                    float(mer_cfg.critical_raise)
                    if severity == "critica" and mer_cfg.critical_raise is not None
                    else float(mer_cfg.menor_raise or mer_cfg.warning_raise or 0.0)
                    if severity == "menor"
                    else float(mer_cfg.warning_raise or 0.0)
                )
            else:
                rule = f"mer_below_{severity}"
                threshold = (
                    rules.mer_critical_db
                    if severity == "critica"
                    else rules.mer_warning_db
                )
            alarm_type = resolve_alarm_type(rule=rule, phase="raised", severity=severity)
            transitions.append(
                AlarmTransition(
                    channel_key=record.channel_key,
                    label=record.label,
                    frequency_hz=record.frequency_hz,
                    severity=severity,
                    phase="raised",
                    alarm_type=alarm_type,
                    rule=rule,
                    message=self._format_digital_message(record, severity),
                    carrier_dbm=record.carrier_dbm,
                    noise_dbm=record.noise_dbm,
                    snr_above_noise_db=record.snr_above_noise_db,
                    threshold_db=float(threshold),
                )
            )
            return transitions

        if previous in _ACTIVE_ALARM_HEALTH and current == "ok":
            severity = previous
            record.active_severity = None
            record.latched_severity = severity
            record.latched_at = now
            record.ack_at = 0.0
            if rule_prefix == "dig_sync" or not record.digital_sync_ok:
                rule = "dig_sync_recovered_critical"
                threshold = 0.0
            elif nominal_mer:
                rule = f"mer_drop_recovered_{severity}"
                threshold = (
                    float(mer_cfg.critical_raise)
                    if severity == "critica" and mer_cfg.critical_raise is not None
                    else float(mer_cfg.menor_raise or mer_cfg.warning_raise or 0.0)
                    if severity == "menor"
                    else float(mer_cfg.warning_raise or 0.0)
                )
            else:
                rule = f"mer_recovered_{severity}"
                threshold = (
                    rules.mer_critical_db
                    if severity == "critica"
                    else rules.mer_warning_db
                )
            alarm_type = resolve_alarm_type(rule=rule, phase="latched", severity=severity)
            transitions.append(
                AlarmTransition(
                    channel_key=record.channel_key,
                    label=record.label,
                    frequency_hz=record.frequency_hz,
                    severity=severity,
                    phase="latched",
                    alarm_type=alarm_type,
                    rule=rule,
                    message=self._format_digital_message(record, severity, recovered=True),
                    carrier_dbm=record.carrier_dbm,
                    noise_dbm=record.noise_dbm,
                    snr_above_noise_db=record.snr_above_noise_db,
                    threshold_db=float(threshold),
                )
            )
        elif current == "ok":
            record.active_severity = None
        return transitions

    @staticmethod
    def _format_digital_message(
        record: ChannelAlarmRecord,
        severity: AlarmSeverity,
        *,
        recovered: bool = False,
    ) -> str:
        mer = record.mer_db
        mer_text = f"{mer:.1f} dB" if mer is not None else "—"
        freq_mhz = record.frequency_hz / 1e6
        if not record.digital_sync_ok:
            base = f"{record.label} ({freq_mhz:.3f} MHz) — sync digital perdido"
        else:
            base = f"{record.label} ({freq_mhz:.3f} MHz) — MER {mer_text}"
        if recovered:
            return f"{base} — recuperado"
        return f"{base} — {severity}"

    def update(
        self,
        measurement: ChannelMeasurement,
        rules: SupervisionRules,
        settings: SupervisionSettings,
        *,
        checks: Dict[str, ThresholdCheckConfig] | None = None,
        threshold_mode: str = "noise_relative",
        reference: ChannelReferenceCapture | None = None,
        now_monotonic: float | None = None,
    ) -> List[AlarmTransition]:
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        transitions: List[AlarmTransition] = []
        record = self.records.get(measurement.channel_key)
        if record is None:
            record = ChannelAlarmRecord(
                channel_key=measurement.channel_key,
                label=measurement.label,
                frequency_hz=measurement.frequency_hz,
            )
            self.records[measurement.channel_key] = record
        record.label = measurement.label
        record.frequency_hz = measurement.frequency_hz
        record.carrier_dbm = measurement.carrier_dbm
        record.noise_dbm = measurement.noise_dbm
        record.snr_above_noise_db = measurement.snr_above_noise_db

        committed = self._committed.get(measurement.channel_key, "unknown")
        if checks:
            raw = evaluate_channel_health_from_checks(
                measurement,
                checks,
                committed=_valid_committed(committed),
                threshold_mode=threshold_mode,
                reference=reference,
            )
        else:
            raw = evaluate_channel_health(measurement, rules)
        record.health = raw
        pending = self._pending.get(measurement.channel_key)
        debounce_s = max(int(rules.debounce_ms), 0) / 1000.0
        if pending is None or pending.health != raw:
            self._pending[measurement.channel_key] = _PendingHealth(raw, now)
            return transitions
        if now - pending.since_monotonic < debounce_s:
            return transitions

        previous = self._committed.get(measurement.channel_key, "unknown")
        if previous == raw:
            transitions.extend(self._apply_auto_reset(record, settings, now))
            return transitions

        self._committed[measurement.channel_key] = raw
        transitions.extend(
            self._transition_record(record, previous, raw, rules, now)
        )
        transitions.extend(self._apply_auto_reset(record, settings, now))
        return transitions

    def _transition_record(
        self,
        record: ChannelAlarmRecord,
        previous: ChannelHealth,
        current: ChannelHealth,
        rules: SupervisionRules,
        now: float,
    ) -> List[AlarmTransition]:
        transitions: List[AlarmTransition] = []
        if current in _ALL_ALARM_HEALTH:
            severity: AlarmSeverity = current  # type: ignore[assignment]
            if current == "comentario":
                transitions.append(
                    AlarmTransition(
                        channel_key=record.channel_key,
                        label=record.label,
                        frequency_hz=record.frequency_hz,
                        severity="comentario",
                        phase="raised",
                        alarm_type=resolve_alarm_type(rule="snr_comment", phase="raised", severity="comentario"),
                        rule="snr_comment",
                        message=self._format_message(record, "comentario"),
                        carrier_dbm=record.carrier_dbm,
                        noise_dbm=record.noise_dbm,
                        snr_above_noise_db=record.snr_above_noise_db,
                        threshold_db=0.0,
                    )
                )
                return transitions
            record.active_severity = severity
            record.active_acknowledged = False
            record.latched_severity = None
            record.latched_at = 0.0
            record.ack_at = 0.0
            threshold = (
                rules.critical_above_noise_db
                if severity == "critica"
                else rules.warning_above_noise_db
            )
            rule = f"snr_below_{severity}"
            alarm_type = resolve_alarm_type(rule=rule, phase="raised", severity=severity)
            transitions.append(
                AlarmTransition(
                    channel_key=record.channel_key,
                    label=record.label,
                    frequency_hz=record.frequency_hz,
                    severity=severity,
                    phase="raised",
                    alarm_type=alarm_type,
                    rule=rule,
                    message=self._format_message(record, severity),
                    carrier_dbm=record.carrier_dbm,
                    noise_dbm=record.noise_dbm,
                    snr_above_noise_db=record.snr_above_noise_db,
                    threshold_db=float(threshold),
                )
            )
            return transitions

        if previous in _ACTIVE_ALARM_HEALTH and current == "ok":
            severity = previous
            record.active_severity = None
            record.latched_severity = severity
            record.latched_at = now
            record.ack_at = 0.0
            threshold = (
                rules.critical_above_noise_db
                if severity == "critica"
                else rules.warning_above_noise_db
            )
            rule = f"snr_recovered_{severity}"
            alarm_type = resolve_alarm_type(rule=rule, phase="latched", severity=severity)
            transitions.append(
                AlarmTransition(
                    channel_key=record.channel_key,
                    label=record.label,
                    frequency_hz=record.frequency_hz,
                    severity=severity,
                    phase="latched",
                    alarm_type=alarm_type,
                    rule=rule,
                    message=self._format_message(record, severity, recovered=True),
                    carrier_dbm=record.carrier_dbm,
                    noise_dbm=record.noise_dbm,
                    snr_above_noise_db=record.snr_above_noise_db,
                    threshold_db=float(threshold),
                )
            )
        elif current == "ok":
            record.active_severity = None
        return transitions

    def _apply_auto_reset(
        self,
        record: ChannelAlarmRecord,
        settings: SupervisionSettings,
        now: float,
    ) -> List[AlarmTransition]:
        if record.latched_severity is None or record.latched_at <= 0.0:
            return []
        severity = record.latched_severity
        if severity in ("aviso", "comentario"):
            if settings.warning_ack_mode != "auto_reset":
                return []
            timeout = max(int(settings.warning_auto_reset_sec), 0)
        else:
            if settings.critical_ack_mode != "auto_reset":
                return []
            timeout = max(int(settings.critical_auto_reset_sec), 0)
        if timeout <= 0 or now - record.latched_at < timeout:
            return []
        return self._ack_record(record, auto=True)

    def acknowledge(self, channel_key: str) -> List[AlarmTransition]:
        record = self.records.get(channel_key)
        if record is None:
            return []
        transitions: List[AlarmTransition] = []
        if record.latched_severity is not None:
            transitions.extend(self._ack_record(record, auto=False))
        elif record.active_severity is not None and not record.active_acknowledged:
            transitions.extend(self._ack_active_record(record))
        return transitions

    def acknowledge_all(self) -> List[AlarmTransition]:
        transitions: List[AlarmTransition] = []
        for key in list(self.records.keys()):
            transitions.extend(self.acknowledge(key))
        return transitions

    def _ack_active_record(self, record: ChannelAlarmRecord) -> List[AlarmTransition]:
        if record.active_severity is None or record.active_acknowledged:
            return []
        severity = record.active_severity
        record.active_acknowledged = True
        record.ack_at = time.monotonic()
        rule = "manual_ack_active"
        alarm_type = resolve_alarm_type(rule=rule, phase="acked", severity=severity)
        return [
            AlarmTransition(
                channel_key=record.channel_key,
                label=record.label,
                frequency_hz=record.frequency_hz,
                severity=severity,
                phase="acked",
                alarm_type=alarm_type,
                rule=rule,
                message=record.label,
                carrier_dbm=record.carrier_dbm,
                noise_dbm=record.noise_dbm,
                snr_above_noise_db=record.snr_above_noise_db,
                threshold_db=0.0,
            )
        ]

    def _ack_record(self, record: ChannelAlarmRecord, *, auto: bool) -> List[AlarmTransition]:
        if record.latched_severity is None:
            return []
        severity = record.latched_severity
        threshold = 0.0
        rule = "auto_reset" if auto else "manual_ack"
        phase: Literal["raised", "latched", "cleared", "acked"] = (
            "cleared" if auto else "acked"
        )
        alarm_type = resolve_alarm_type(rule=rule, phase=phase, severity=severity)
        transitions = [
            AlarmTransition(
                channel_key=record.channel_key,
                label=record.label,
                frequency_hz=record.frequency_hz,
                severity=severity,
                phase=phase,
                alarm_type=alarm_type,
                rule=rule,
                message=record.label,
                carrier_dbm=record.carrier_dbm,
                noise_dbm=record.noise_dbm,
                snr_above_noise_db=record.snr_above_noise_db,
                threshold_db=threshold,
            )
        ]
        record.latched_severity = None
        record.latched_at = 0.0
        record.ack_at = time.monotonic()
        return transitions

    @staticmethod
    def _format_message(
        record: ChannelAlarmRecord,
        severity: AlarmSeverity,
        *,
        recovered: bool = False,
    ) -> str:
        snr = record.snr_above_noise_db
        snr_text = f"{snr:.1f} dB" if snr is not None else "—"
        freq_mhz = record.frequency_hz / 1e6
        if recovered:
            return f"{record.label} ({freq_mhz:.3f} MHz) — recuperado, S/R {snr_text}"
        return f"{record.label} ({freq_mhz:.3f} MHz) — {severity}, S/R {snr_text}"

    def summary_counts(self) -> AlarmSummaryCounts:
        ok = warning_active = warning_latched = critical_active = critical_latched = 0
        for record in self.records.values():
            if record.active_severity == "critica":
                critical_active += 1
            elif record.active_severity in ("aviso", "menor"):
                warning_active += 1
            elif record.latched_severity == "critica":
                critical_latched += 1
            elif record.latched_severity in ("aviso", "menor"):
                warning_latched += 1
            elif record.health in ("ok", "unknown"):
                ok += 1
            else:
                ok += 1
        return AlarmSummaryCounts(
            ok=ok,
            warning_active=warning_active,
            warning_latched=warning_latched,
            critical_active=critical_active,
            critical_latched=critical_latched,
        )

    def alarm_states_for_display(self) -> Dict[str, str]:
        """Mapa channel_key → ok | warning | critical | warning_latched | critical_latched."""
        states: Dict[str, str] = {}
        for key, record in self.records.items():
            if record.active_severity == "critica":
                states[key] = "critical"
            elif record.active_severity == "menor":
                states[key] = "warning"
            elif record.active_severity == "aviso":
                states[key] = "warning"
            elif record.latched_severity == "critica":
                states[key] = "critical_latched"
            elif record.latched_severity in ("aviso", "menor"):
                states[key] = "warning_latched"
            elif record.health == "comentario":
                states[key] = "comentario"
            else:
                states[key] = "ok"
        return states

    def active_alarm_lines(self) -> List[str]:
        return [row.message for row in self.alarm_display_rows() if not row.acknowledged or row.phase == "latched"]

    def alarm_display_rows(self) -> List["AlarmDisplayRow"]:
        from core.monitor.supervision.supervision_models import AlarmDisplayRow

        rows: List[AlarmDisplayRow] = []
        for record in sorted(
            self.records.values(),
            key=lambda row: (row.frequency_hz, row.label.casefold()),
        ):
            if record.active_severity is not None:
                rows.append(
                    AlarmDisplayRow(
                        channel_key=record.channel_key,
                        label=record.label,
                        frequency_mhz=record.frequency_hz / 1e6,
                        severity=record.active_severity,
                        phase="active",
                        snr_db=record.snr_above_noise_db,
                        carrier_dbm=record.carrier_dbm,
                        noise_dbm=record.noise_dbm,
                        message=f"{'🔴' if record.active_severity == 'critica' else '🟠' if record.active_severity == 'menor' else '🟡'} {self._format_message(record, record.active_severity)}",
                        can_ack=not record.active_acknowledged,
                        acknowledged=record.active_acknowledged,
                    )
                )
            elif record.latched_severity is not None:
                sev = record.latched_severity
                rows.append(
                    AlarmDisplayRow(
                        channel_key=record.channel_key,
                        label=record.label,
                        frequency_mhz=record.frequency_hz / 1e6,
                        severity=f"{sev}_latched",
                        phase="latched",
                        snr_db=record.snr_above_noise_db,
                        carrier_dbm=record.carrier_dbm,
                        noise_dbm=record.noise_dbm,
                        message=f"🟠 {record.label} — {'crítica' if sev == 'critica' else 'menor' if sev == 'menor' else 'aviso'} memorizado · {self._format_message(record, sev, recovered=True)}",
                        can_ack=True,
                        acknowledged=False,
                    )
                )
        return rows

    def pending_attention_count(self) -> int:
        count = 0
        for record in self.records.values():
            if record.latched_severity is not None:
                count += 1
            elif record.active_severity is not None and not record.active_acknowledged:
                count += 1
        return count

    def clear_digital_state(self, channel_key: str) -> None:
        """Elimina estado pendiente/activo de alarmas digitales (MER/sync)."""
        key = str(channel_key or "")
        if not key:
            return
        self._digital_pending.pop(key, None)
        self._digital_committed.pop(key, None)
        record = self.records.get(key)
        if record is None:
            return
        record.mer_db = None
        record.digital_sync_ok = None

    def channel_metrics_snapshot(
        self,
        *,
        digital_modes: Dict[str, str] | None = None,
    ) -> Dict[str, "SupervisionChannelMetrics"]:
        from core.monitor.supervision.supervision_models import SupervisionChannelMetrics

        modes = digital_modes or {}
        result: Dict[str, SupervisionChannelMetrics] = {}
        for key, record in self.records.items():
            result[key] = SupervisionChannelMetrics(
                channel_key=key,
                snr_db=record.snr_above_noise_db,
                mer_db=record.mer_db,
                sync_ok=record.digital_sync_ok,
                digital_mode=modes.get(key, "none"),
            )
        return result
