"""Repositorio SQLite de eventos de supervisión RF."""
from __future__ import annotations

from typing import Iterable, List, Optional

from core.monitor.supervision.alarm_manager import AlarmTransition

from ..connection import Database
from ..models.supervision_event import SupervisionEvent
from .base import BaseRepository


class SupervisionEventRepository(BaseRepository[SupervisionEvent]):
    table_name = "supervision_events"

    def _row_to_entity(self, row) -> SupervisionEvent:
        return SupervisionEvent(
            id=int(row["id"]),
            project_key=str(row["project_key"]),
            timestamp_utc=str(row["timestamp_utc"]),
            channel_key=str(row["channel_key"] or ""),
            label=str(row["label"] or ""),
            frequency_mhz=_optional_float(row["frequency_mhz"]),
            severity=str(row["severity"] or ""),
            phase=str(row["phase"] or ""),
            snr_db=_optional_float(row["snr_db"]),
            carrier_dbm=_optional_float(row["carrier_dbm"]),
            noise_dbm=_optional_float(row["noise_dbm"]),
            threshold_db=_optional_float(row["threshold_db"]),
            rule=str(row["rule"] or ""),
            message=str(row["message"] or ""),
            alarm_type=str(row["alarm_type"] or "") if "alarm_type" in row.keys() else "",
            ack_at=str(row["ack_at"] or ""),
        )

    def insert_transitions(
        self,
        project_key: str,
        transitions: Iterable[AlarmTransition],
        *,
        timestamp_utc: str | None = None,
    ) -> int:
        from core.monitor.supervision.alarm_log_repository import utc_now_iso

        rows = list(transitions)
        if not rows:
            return 0
        stamp = timestamp_utc or utc_now_iso()
        count = 0
        with self._db.transaction():
            for item in rows:
                alarm_type = item.alarm_type or ""
                self._db.execute(
                    """
                    INSERT INTO supervision_events (
                        project_key, timestamp_utc, alarm_type, channel_key, label, frequency_mhz,
                        severity, phase, snr_db, carrier_dbm, noise_dbm, threshold_db,
                        rule, message, ack_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_key,
                        stamp,
                        alarm_type,
                        item.channel_key,
                        item.label,
                        item.frequency_hz / 1e6,
                        item.severity,
                        item.phase,
                        item.snr_above_noise_db,
                        item.carrier_dbm,
                        item.noise_dbm,
                        item.threshold_db,
                        item.rule,
                        item.message,
                        stamp if item.phase == "acked" else "",
                    ),
                )
                count += 1
        return count

    def insert_ack(
        self,
        project_key: str,
        *,
        channel_key: str,
        label: str,
        manual: bool = True,
        timestamp_utc: str | None = None,
    ) -> None:
        from core.monitor.supervision.alarm_catalog import resolve_alarm_type
        from core.monitor.supervision.alarm_log_repository import utc_now_iso

        stamp = timestamp_utc or utc_now_iso()
        rule = "manual_ack" if manual else "auto_reset"
        alarm_type = resolve_alarm_type(rule=rule, phase="acked", severity="")
        self._db.execute(
            """
            INSERT INTO supervision_events (
                project_key, timestamp_utc, alarm_type, channel_key, label, frequency_mhz,
                severity, phase, snr_db, carrier_dbm, noise_dbm, threshold_db,
                rule, message, ack_at
            ) VALUES (?, ?, ?, ?, ?, NULL, '', 'acked', NULL, NULL, NULL, NULL, ?, ?, ?)
            """,
            (
                project_key,
                stamp,
                alarm_type,
                channel_key,
                label,
                rule,
                label,
                stamp,
            ),
        )

    def list_by_project(
        self,
        project_key: str,
        *,
        limit: int = 2000,
        channel_key: str = "",
        severity: str = "",
        phase: str = "",
    ) -> List[SupervisionEvent]:
        clauses = ["project_key = ?"]
        params: list = [project_key]
        if channel_key:
            clauses.append("channel_key = ?")
            params.append(channel_key)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        if phase:
            clauses.append("phase = ?")
            params.append(phase)
        params.append(max(1, min(int(limit), 10_000)))
        sql = f"""
            SELECT * FROM supervision_events
            WHERE {' AND '.join(clauses)}
            ORDER BY timestamp_utc DESC, id DESC
            LIMIT ?
        """
        rows = self._db.fetchall(sql, tuple(params))
        return [self._row_to_entity(row) for row in rows]


def _optional_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
