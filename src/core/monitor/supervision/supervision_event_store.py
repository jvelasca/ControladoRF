"""Persistencia de eventos de supervisión (SQLite + consulta unificada)."""
from __future__ import annotations

from typing import Iterable, List, Optional, TYPE_CHECKING

from core.monitor.supervision.alarm_log_repository import (
    AlarmLogEntry,
    export_alarm_log_csv,
    read_alarm_log_csv,
)
from core.monitor.supervision.alarm_manager import AlarmTransition
from db.models.supervision_event import SupervisionEvent

if TYPE_CHECKING:
    from db.repositories.supervision_event_repository import SupervisionEventRepository


class SupervisionEventStore:
    """Escribe en SQLite y expone consultas para la GUI."""

    def __init__(self, repository: Optional[SupervisionEventRepository] = None) -> None:
        self._repo = repository

    @property
    def available(self) -> bool:
        return self._repo is not None

    def append_transitions(self, project_key: str, transitions: Iterable[AlarmTransition]) -> None:
        if not self._repo or not project_key:
            return
        rows = list(transitions)
        if rows:
            self._repo.insert_transitions(project_key, rows)

    def append_ack(
        self,
        project_key: str,
        *,
        channel_key: str,
        label: str,
        manual: bool = True,
    ) -> None:
        if not self._repo or not project_key:
            return
        self._repo.insert_ack(
            project_key,
            channel_key=channel_key,
            label=label,
            manual=manual,
        )

    def query(
        self,
        project_key: str,
        *,
        limit: int = 2000,
        channel_key: str = "",
        severity: str = "",
        phase: str = "",
    ) -> List[AlarmLogEntry]:
        if not self._repo or not project_key:
            return []
        rows = self._repo.list_by_project(
            project_key,
            limit=limit,
            channel_key=channel_key,
            severity=severity,
            phase=phase,
        )
        return [_event_to_entry(row) for row in rows]

    def query_merged(
        self,
        project_key: str,
        *,
        csv_path=None,
        limit: int = 2000,
        channel_key: str = "",
        severity: str = "",
        phase: str = "",
    ) -> List[AlarmLogEntry]:
        entries = self.query(
            project_key,
            limit=limit,
            channel_key=channel_key,
            severity=severity,
            phase=phase,
        )
        if csv_path:
            from pathlib import Path

            csv_entries = read_alarm_log_csv(Path(csv_path))
            entries = _merge_entries(entries, csv_entries)
        entries = _filter_entries(entries, channel_key, severity, phase)
        entries.sort(key=lambda row: (row.timestamp_utc, row.channel_key), reverse=True)
        return entries[:limit]

    @staticmethod
    def export_csv(entries: Iterable[AlarmLogEntry], path) -> None:
        export_alarm_log_csv(entries, path)

    @staticmethod
    def export_txt(
        entries: Iterable[AlarmLogEntry],
        path,
        *,
        project_name: str = "",
        tr,
    ) -> None:
        from core.monitor.supervision.alarm_report import export_alarm_report_txt

        export_alarm_report_txt(entries, path, project_name=project_name, tr=tr)


def _event_to_entry(row: SupervisionEvent) -> AlarmLogEntry:
    from core.monitor.supervision.alarm_catalog import resolve_alarm_type

    alarm_type = row.alarm_type or resolve_alarm_type(
        rule=row.rule,
        phase=row.phase,
        severity=row.severity,
    )
    return AlarmLogEntry(
        timestamp_utc=row.timestamp_utc,
        alarm_type=alarm_type,
        channel_key=row.channel_key,
        label=row.label,
        frequency_mhz=row.frequency_mhz,
        severity=row.severity,
        phase=row.phase,
        snr_db=row.snr_db,
        carrier_dbm=row.carrier_dbm,
        noise_dbm=row.noise_dbm,
        threshold_db=row.threshold_db,
        rule=row.rule,
        message=row.message,
        ack_at=row.ack_at,
    )


def _entry_key(entry: AlarmLogEntry) -> tuple:
    return (
        entry.timestamp_utc,
        entry.channel_key,
        entry.phase,
        entry.severity,
        entry.rule,
    )


def _merge_entries(primary: List[AlarmLogEntry], extra: List[AlarmLogEntry]) -> List[AlarmLogEntry]:
    seen = {_entry_key(item) for item in primary}
    merged = list(primary)
    for item in extra:
        key = _entry_key(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _filter_entries(
    entries: List[AlarmLogEntry],
    channel_key: str,
    severity: str,
    phase: str,
) -> List[AlarmLogEntry]:
    filtered = entries
    if channel_key:
        filtered = [row for row in filtered if row.channel_key == channel_key]
    if severity:
        filtered = [row for row in filtered if row.severity == severity]
    if phase:
        filtered = [row for row in filtered if row.phase == phase]
    return filtered
