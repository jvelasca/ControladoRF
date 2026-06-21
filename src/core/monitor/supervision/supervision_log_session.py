"""Sesiones REC de log de supervisión — carpeta, CSV, metadata y TXT.

Cada sesión REC crea una subcarpeta bajo el directorio de logs del proyecto:

- ``alarms.csv`` — eventos append-only (mismas columnas que el log legacy).
- ``session.json`` — metadatos de inicio/fin, duración y recuento.
- ``report.txt`` — informe legible generado al detener REC.

Ver ``SupervisionLogSessionManager`` en el controlador Monitor.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from core.monitor.supervision.alarm_log_repository import (
    CSV_COLUMNS,
    read_alarm_log_csv,
    utc_now_iso,
)


@dataclass
class SupervisionLogSessionRecord:
    """Metadatos de una sesión REC (activa o cerrada)."""

    session_id: str
    directory: Path
    csv_path: Path
    txt_path: Path
    started_at_utc: str
    ended_at_utc: str = ""
    duration_s: int = 0
    event_count: int = 0

    @property
    def is_active(self) -> bool:
        return not self.ended_at_utc


@dataclass
class SupervisionLogSessionManager:
    """Gestiona la sesión REC activa y la última sesión cerrada en memoria."""

    active: Optional[SupervisionLogSessionRecord] = None
    last: Optional[SupervisionLogSessionRecord] = None
    _started_mono: float = 0.0

    @property
    def is_recording(self) -> bool:
        return self.active is not None and self.active.is_active

    def start(self, *, log_root: Path, project_name: str) -> SupervisionLogSessionRecord:
        if self.is_recording:
            raise RuntimeError("Supervision log session already active")
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        session_dir = Path(log_root).expanduser() / stamp
        session_dir.mkdir(parents=True, exist_ok=False)
        csv_path = session_dir / "alarms.csv"
        txt_path = session_dir / "report.txt"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            import csv

            writer = csv.writer(handle)
            writer.writerow(CSV_COLUMNS)
        started = utc_now_iso()
        session = SupervisionLogSessionRecord(
            session_id=stamp,
            directory=session_dir,
            csv_path=csv_path,
            txt_path=txt_path,
            started_at_utc=started,
        )
        self._write_session_json(session, project_name=project_name, partial=True)
        self.active = session
        import time

        self._started_mono = time.monotonic()
        return session

    def stop(
        self,
        *,
        project_name: str,
        tr: Callable[[str], str],
    ) -> Optional[SupervisionLogSessionRecord]:
        if not self.is_recording or self.active is None:
            return None
        session = self.active
        entries = read_alarm_log_csv(session.csv_path)
        session.event_count = len(entries)
        session.ended_at_utc = utc_now_iso()
        import time

        session.duration_s = max(0, int(time.monotonic() - self._started_mono))
        self._write_session_json(session, project_name=project_name, partial=False)
        self._write_report_txt(session, entries, project_name=project_name, tr=tr)
        self.last = session
        self.active = None
        self._started_mono = 0.0
        return session

    def active_csv_path(self) -> Optional[Path]:
        if self.active is None:
            return None
        return self.active.csv_path

    def _write_session_json(
        self,
        session: SupervisionLogSessionRecord,
        *,
        project_name: str,
        partial: bool,
    ) -> None:
        payload = {
            "session_id": session.session_id,
            "project_name": project_name,
            "started_at_utc": session.started_at_utc,
            "ended_at_utc": session.ended_at_utc,
            "duration_s": session.duration_s,
            "event_count": session.event_count,
            "csv_file": session.csv_path.name,
            "report_file": session.txt_path.name,
            "partial": partial,
        }
        path = session.directory / "session.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _write_report_txt(
        session: SupervisionLogSessionRecord,
        entries: list,
        *,
        project_name: str,
        tr: Callable[[str], str],
    ) -> None:
        from core.monitor.supervision.alarm_report import export_alarm_report_txt

        export_alarm_report_txt(
            entries,
            session.txt_path,
            project_name=project_name,
            tr=tr,
        )

    def elapsed_seconds(self) -> int:
        if not self.is_recording:
            return 0
        import time

        return max(0, int(time.monotonic() - self._started_mono))
