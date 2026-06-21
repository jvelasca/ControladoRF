"""Orquestación medición → reglas → alarmas → log."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from core.monitor.spectrum_params import SpectrumFrame
from core.monitor.supervision.alarm_log_repository import AlarmLogRepository
from core.monitor.supervision.alarm_manager import AlarmManager, AlarmTransition
from core.monitor.supervision.measurement_engine import measure_targets
from core.monitor.supervision.supervision_event_store import SupervisionEventStore
from core.monitor.supervision.supervision_models import (
    AlarmSummaryCounts,
    AlarmDisplayRow,
    ResolvedSupervisionTarget,
    SupervisionChannelMetrics,
    SupervisionState,
)
from core.inventory_channel import find_equipo_in_list, normalize_equipo
from core.monitor.supervision.rules_resolver import resolve_effective_rules
from core.monitor.supervision.threshold_resolver import resolve_effective_thresholds
from core.monitor.supervision.supervision_log_session import SupervisionLogSessionManager
from core.monitor.supervision.supervision_resolve import resolve_supervision_targets
from core.monitor.supervision.supervision_dwell_scheduler import (
    SupervisionDwellRequest,
    SupervisionDwellScheduler,
)


@dataclass
class SupervisionSnapshot:
    counts: AlarmSummaryCounts
    alarm_states: Dict[str, str]
    alarm_lines: List[str]
    alarm_rows: List[AlarmDisplayRow] = field(default_factory=list)
    channel_metrics: Dict[str, SupervisionChannelMetrics] = field(default_factory=dict)
    pending_attention: int = 0
    transitions: List[AlarmTransition] = field(default_factory=list)


class SupervisionEngine:
    def __init__(self) -> None:
        self._state = SupervisionState()
        self._resolved: List[ResolvedSupervisionTarget] = []
        self._alarm_manager = AlarmManager()
        self._log = AlarmLogRepository()
        self._event_store: SupervisionEventStore | None = None
        self._project_key = ""
        self._last_process_at = 0.0
        self._process_interval_s = 0.5
        self._logging_enabled = False
        self._last_snapshot = SupervisionSnapshot(
            counts=AlarmSummaryCounts(),
            alarm_states={},
            alarm_lines=[],
            alarm_rows=[],
        )
        self._equipo_by_key: Dict[str, dict] = {}
        self._dwell_scheduler = SupervisionDwellScheduler()
        self._last_capture_mode = "sweep"
        self._session_manager = SupervisionLogSessionManager()
        self._project_name = ""
        self._log_directory: Optional[Path] = None

    @property
    def session_manager(self) -> SupervisionLogSessionManager:
        return self._session_manager

    @property
    def is_recording(self) -> bool:
        return self._session_manager.is_recording

    def rec_elapsed_seconds(self) -> int:
        return self._session_manager.elapsed_seconds()

    def get_equipo(self, channel_key: str) -> dict | None:
        return self._equipo_by_key.get(channel_key)

    def take_pending_dwell(self) -> SupervisionDwellRequest | None:
        return self._dwell_scheduler.take_pending()

    def mark_dwell_started(self, channel_key: str) -> None:
        self._dwell_scheduler.mark_dwell_started(channel_key)

    def clear_digital_state(self, channel_key: str) -> None:
        self._alarm_manager.clear_digital_state(channel_key)

    @property
    def log_path(self) -> Optional[Path]:
        return self._log.path

    def set_event_store(self, store: SupervisionEventStore | None) -> None:
        self._event_store = store

    @property
    def last_snapshot(self) -> SupervisionSnapshot:
        return self._last_snapshot

    def configure(
        self,
        state: SupervisionState,
        equipos: list,
        *,
        project_name: str = "",
        project_key: str = "",
        log_directory: Path | str | None = None,
    ) -> None:
        self._state = state
        self._project_key = str(project_key or "")
        self._project_name = str(project_name or "")
        if log_directory is not None:
            self._log_directory = Path(log_directory).expanduser()
        self._resolved = resolve_supervision_targets(state, equipos)
        normalized = [normalize_equipo(item) for item in equipos if isinstance(item, dict)]
        self._equipo_by_key = {
            str(item.get("channel_key") or ""): item
            for item in normalized
            if item.get("channel_key")
        }
        labels = {
            target.channel_key: (target.label, target.frequency_hz)
            for target in self._resolved
        }
        self._alarm_manager.reset(labels)
        self._dwell_scheduler.reset()
        self._apply_dwell_settings(state.settings)
        self._last_snapshot = self._build_snapshot([], include_metrics=True)

    def start_logging(self, *, project_name: str, log_directory: Path | str) -> Optional[Path]:
        if self._session_manager.is_recording:
            return self._log.path
        path = self._log.open_session(project_name=project_name, directory=log_directory)
        self._logging_enabled = True
        return path

    def start_recording(self, *, log_root: Path | str, project_name: str) -> Path:
        session = self._session_manager.start(log_root=log_root, project_name=project_name)
        self._log.open_session_file(session.csv_path)
        self._logging_enabled = False
        return session.csv_path

    def stop_recording(self, *, project_name: str, tr) -> Optional[object]:
        session = self._session_manager.stop(project_name=project_name, tr=tr)
        self._log.close_session()
        return session

    def stop_logging(self) -> None:
        if self._session_manager.is_recording:
            return
        self._logging_enabled = False
        self._log.close_session()

    def should_log_while_running(self) -> bool:
        if self._session_manager.is_recording:
            return True
        trigger = self._state.settings.log_trigger
        if trigger == "auto":
            return True
        if trigger == "manual":
            return False
        return self._logging_enabled

    def process_frame(
        self,
        frame: SpectrumFrame,
        *,
        engine_running: bool,
        force: bool = False,
        capture_mode: str = "sweep",
        supervision_enabled: bool = False,
        dwell_busy: bool = False,
    ) -> SupervisionSnapshot:
        now = time.monotonic()
        if (
            not force
            and now - self._last_process_at < self._process_interval_s
            and self._last_snapshot.alarm_states
        ):
            return self._last_snapshot
        self._last_process_at = now
        if not self._resolved:
            snapshot = SupervisionSnapshot(
                counts=AlarmSummaryCounts(),
                alarm_states={},
                alarm_lines=[],
                alarm_rows=[],
            )
            self._last_snapshot = snapshot
            return snapshot

        transitions: List[AlarmTransition] = []
        measurements = measure_targets(frame, self._resolved)
        for measurement in measurements:
            equipo = self._equipo_by_key.get(measurement.channel_key)
            if equipo is None:
                equipo = find_equipo_in_list(
                    list(self._equipo_by_key.values()),
                    measurement.channel_key,
                )
            target = next(
                (item for item in self._state.targets if item.channel_key == measurement.channel_key),
                None,
            )
            resolved = resolve_effective_thresholds(
                self._state,
                channel_key=measurement.channel_key,
                equipo=equipo,
                target=target,
            )
            rules = resolved.to_supervision_rules()
            transitions.extend(
                self._alarm_manager.update(
                    measurement,
                    rules,
                    self._state.settings,
                    checks=resolved.checks,
                    threshold_mode=resolved.threshold_mode,
                    reference=resolved.reference,
                    now_monotonic=now,
                )
            )

        self._dwell_scheduler.consider(
            measurements,
            resolved=self._resolved,
            equipo_by_key=self._equipo_by_key,
            state=self._state,
            capture_mode=capture_mode,
            supervision_enabled=supervision_enabled,
            dwell_busy=dwell_busy,
            now=now,
        )
        self._last_capture_mode = capture_mode

        if engine_running and self.should_log_while_running() and transitions:
            loggable = [t for t in transitions if t.phase in ("raised", "latched", "cleared")]
            if loggable:
                if self._log.path is None:
                    directory = self._log_directory
                    if directory is None:
                        from core.monitor.monitor_export_paths import EXPORT_ALARM_CSV, export_directory

                        directory = export_directory(EXPORT_ALARM_CSV)
                    self._log.open_session(
                        project_name=self._project_name or "session",
                        directory=directory,
                    )
                self._log.append(loggable)
                if self._event_store is not None and self._project_key:
                    self._event_store.append_transitions(self._project_key, loggable)

        snapshot = self._build_snapshot(transitions)
        return snapshot

    def acknowledge(self, channel_key: str) -> SupervisionSnapshot:
        transitions = self._alarm_manager.acknowledge(channel_key)
        record = self._alarm_manager.records.get(channel_key)
        if transitions and self._log.path is not None and record is not None:
            self._log.append_ack(channel_key, record.label, manual=True)
        if transitions and record is not None and self._event_store is not None and self._project_key:
            self._event_store.append_ack(
                self._project_key,
                channel_key=channel_key,
                label=record.label,
                manual=True,
            )
        return self._build_snapshot(transitions)

    def acknowledge_all(self) -> SupervisionSnapshot:
        transitions = self._alarm_manager.acknowledge_all()
        if transitions and self._log.path is not None:
            for item in transitions:
                if item.phase == "acked":
                    self._log.append_ack(item.channel_key, item.label, manual=True)
        if transitions and self._event_store is not None and self._project_key:
            for item in transitions:
                if item.phase == "acked":
                    self._event_store.append_ack(
                        self._project_key,
                        channel_key=item.channel_key,
                        label=item.label,
                        manual=True,
                    )
        return self._build_snapshot(transitions)

    def update_settings(self, state: SupervisionState) -> None:
        self._state.settings = state.settings
        self._state.rules = state.rules
        self._state.rule_overrides = dict(state.rule_overrides)
        self._state.default_preset_id = state.default_preset_id
        self._state.active_alarm_preset_id = state.active_alarm_preset_id
        self._state.user_presets = dict(state.user_presets)
        self._apply_dwell_settings(state.settings)

    def _apply_dwell_settings(self, settings) -> None:
        self._dwell_scheduler.configure(
            periodic_interval_s=settings.dwell_periodic_interval_s,
            min_global_gap_s=settings.dwell_min_global_gap_s,
            snr_recheck_interval_s=settings.dwell_snr_recheck_interval_s,
        )

    def _digital_modes_for_targets(self) -> Dict[str, str]:
        from core.monitor.supervision.digital_supervision import effective_digital_mode_for_equipo

        modes: Dict[str, str] = {}
        for target in self._resolved:
            equipo = self._equipo_by_key.get(target.channel_key) or {}
            rules = resolve_effective_rules(
                self._state,
                channel_key=target.channel_key,
                equipo=equipo,
            )
            modulation = str(equipo.get("modulation_class") or "analog_fm")
            modes[target.channel_key] = effective_digital_mode_for_equipo(
                modulation_class=modulation,
                digital_metrics_enabled=rules.digital_metrics_enabled,
            )
        return modes

    def _build_snapshot(
        self,
        transitions: List[AlarmTransition],
        *,
        include_metrics: bool = True,
    ) -> SupervisionSnapshot:
        digital_modes = self._digital_modes_for_targets() if include_metrics else {}
        snapshot = SupervisionSnapshot(
            counts=self._alarm_manager.summary_counts(),
            alarm_states=self._alarm_manager.alarm_states_for_display(),
            alarm_lines=self._alarm_manager.active_alarm_lines(),
            alarm_rows=self._alarm_manager.alarm_display_rows(),
            channel_metrics=(
                self._alarm_manager.channel_metrics_snapshot(digital_modes=digital_modes)
                if include_metrics
                else {}
            ),
            pending_attention=self._alarm_manager.pending_attention_count(),
            transitions=transitions,
        )
        self._last_snapshot = snapshot
        return snapshot

    def process_digital_analysis(
        self,
        *,
        channel_key: str = "",
        vfo_hz: float = 0.0,
        mer_db: float | None,
        mer_db_smoothed: float | None,
        sync_ok: bool,
        engine_running: bool,
    ) -> SupervisionSnapshot:
        from core.monitor.supervision.digital_supervision import (
            is_digital_modulation_class,
            match_supervision_target_for_vfo,
            resolve_supervision_target,
        )

        if not engine_running or not self._resolved:
            return self._last_snapshot

        target = resolve_supervision_target(self._resolved, channel_key) if channel_key else None
        if target is None and vfo_hz > 0:
            target = match_supervision_target_for_vfo(self._resolved, vfo_hz)
        if target is None:
            return self._last_snapshot

        equipo = self._equipo_by_key.get(target.channel_key)
        modulation_class = str((equipo or {}).get("modulation_class") or "analog_fm")
        if not is_digital_modulation_class(modulation_class):
            return self._last_snapshot

        target_obj = next(
            (item for item in self._state.targets if item.channel_key == target.channel_key),
            None,
        )
        resolved = resolve_effective_thresholds(
            self._state,
            channel_key=target.channel_key,
            equipo=equipo,
            target=target_obj,
        )
        rules = resolved.to_supervision_rules()
        mer_value = mer_db_smoothed if mer_db_smoothed is not None else mer_db
        transitions = self._alarm_manager.update_digital(
            channel_key=target.channel_key,
            label=target.label,
            frequency_hz=target.frequency_hz,
            mer_db=mer_value,
            sync_ok=sync_ok,
            rules=rules,
            settings=self._state.settings,
            checks=resolved.checks,
            threshold_mode=resolved.threshold_mode,
            reference=resolved.reference,
        )

        if engine_running and self.should_log_while_running() and transitions:
            loggable = [t for t in transitions if t.phase in ("raised", "latched", "cleared")]
            if loggable:
                if self._log.path is None:
                    directory = self._log_directory
                    if directory is None:
                        from core.monitor.monitor_export_paths import EXPORT_ALARM_CSV, export_directory

                        directory = export_directory(EXPORT_ALARM_CSV)
                    self._log.open_session(
                        project_name=self._project_name or "session",
                        directory=directory,
                    )
                self._log.append(loggable)
                if self._event_store is not None and self._project_key:
                    self._event_store.append_transitions(self._project_key, loggable)

        snapshot = self._build_snapshot(transitions)
        return snapshot
