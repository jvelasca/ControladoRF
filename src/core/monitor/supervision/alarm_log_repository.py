"""Log CSV append-only de eventos de supervisión."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from core.monitor.supervision.alarm_catalog import resolve_alarm_type
from core.monitor.supervision.alarm_manager import AlarmTransition

CSV_COLUMNS = (
    "timestamp_utc",
    "alarm_type",
    "channel_key",
    "label",
    "frequency_mhz",
    "severity",
    "phase",
    "snr_db",
    "carrier_dbm",
    "noise_dbm",
    "threshold_db",
    "rule",
    "message",
    "ack_at",
)


@dataclass(frozen=True)
class AlarmLogEntry:
    timestamp_utc: str
    alarm_type: str
    channel_key: str
    label: str
    frequency_mhz: Optional[float]
    severity: str
    phase: str
    snr_db: Optional[float]
    carrier_dbm: Optional[float]
    noise_dbm: Optional[float]
    threshold_db: Optional[float]
    rule: str
    message: str
    ack_at: str


class AlarmLogRepository:
    def __init__(self) -> None:
        self._path: Optional[Path] = None

    @property
    def path(self) -> Optional[Path]:
        return self._path

    def open_session(self, *, project_name: str, directory: Path | str) -> Path:
        folder = Path(directory).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        safe_name = _safe_filename(project_name or "project")
        return self.open_session_file(folder / f"supervision_alarms_{safe_name}_{stamp}.csv")

    def open_session_file(self, path: Path | str) -> Path:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        self._path = target
        if not self._path.exists():
            with self._path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(CSV_COLUMNS)
        return self._path

    def close_session(self) -> None:
        self._path = None

    def append(self, transitions: Iterable[AlarmTransition]) -> None:
        if self._path is None:
            return
        rows = list(transitions)
        if not rows:
            return
        with self._path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            for item in rows:
                writer.writerow(_transition_row(item))

    def append_ack(self, channel_key: str, label: str, *, manual: bool = True) -> None:
        if self._path is None:
            return
        now = _utc_now()
        alarm_type = resolve_alarm_type(
            rule="manual_ack" if manual else "auto_reset",
            phase="acked",
            severity="",
        )
        with self._path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    now,
                    alarm_type,
                    channel_key,
                    label,
                    "",
                    "",
                    "acked",
                    "",
                    "",
                    "",
                    "",
                    "manual_ack" if manual else "auto_reset",
                    label,
                    now,
                ]
            )


def filter_alarm_log_entries(
    entries: List[AlarmLogEntry],
    *,
    severity: str = "",
    phase: str = "",
    channel_keys: Iterable[str] | None = None,
) -> List[AlarmLogEntry]:
    filtered = entries
    if severity:
        filtered = [row for row in filtered if row.severity == severity]
    if phase:
        filtered = [row for row in filtered if row.phase == phase]
    if channel_keys is not None:
        key_set = {str(key) for key in channel_keys if key}
        if key_set:
            filtered = [row for row in filtered if row.channel_key in key_set]
    return filtered


def read_alarm_log_csv(path: Path | str) -> List[AlarmLogEntry]:
    """Lee filas de un CSV de supervisión (cabecera estándar)."""
    file_path = Path(path)
    if not file_path.is_file():
        return []
    entries: List[AlarmLogEntry] = []
    with file_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            entries.append(
                AlarmLogEntry(
                    timestamp_utc=str(row.get("timestamp_utc") or ""),
                    alarm_type=str(
                        row.get("alarm_type")
                        or resolve_alarm_type(
                            rule=str(row.get("rule") or ""),
                            phase=str(row.get("phase") or ""),
                            severity=str(row.get("severity") or ""),
                        )
                    ),
                    channel_key=str(row.get("channel_key") or ""),
                    label=str(row.get("label") or ""),
                    frequency_mhz=_parse_optional_float(row.get("frequency_mhz")),
                    severity=str(row.get("severity") or ""),
                    phase=str(row.get("phase") or ""),
                    snr_db=_parse_optional_float(row.get("snr_db")),
                    carrier_dbm=_parse_optional_float(row.get("carrier_dbm")),
                    noise_dbm=_parse_optional_float(row.get("noise_dbm")),
                    threshold_db=_parse_optional_float(row.get("threshold_db")),
                    rule=str(row.get("rule") or ""),
                    message=str(row.get("message") or ""),
                    ack_at=str(row.get("ack_at") or ""),
                )
            )
    return entries


def export_alarm_log_csv(entries: Iterable[AlarmLogEntry], path: Path | str) -> None:
    """Exporta entradas al formato CSV estándar de supervisión."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        for item in entries:
            writer.writerow(
                [
                    item.timestamp_utc,
                    item.alarm_type,
                    item.channel_key,
                    item.label,
                    _fmt_optional_mhz(item.frequency_mhz),
                    item.severity,
                    item.phase,
                    _fmt_optional(item.snr_db),
                    _fmt_optional(item.carrier_dbm),
                    _fmt_optional(item.noise_dbm),
                    _fmt_optional(item.threshold_db),
                    item.rule,
                    item.message,
                    item.ack_at,
                ]
            )


def _parse_optional_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_optional_mhz(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{float(value):.6f}"


def _transition_row(item: AlarmTransition) -> list:
    alarm_type = item.alarm_type or resolve_alarm_type(
        rule=item.rule,
        phase=item.phase,
        severity=item.severity,
    )
    return [
        _utc_now(),
        alarm_type,
        item.channel_key,
        item.label,
        f"{item.frequency_hz / 1e6:.6f}",
        item.severity,
        item.phase,
        _fmt_optional(item.snr_above_noise_db),
        _fmt_optional(item.carrier_dbm),
        _fmt_optional(item.noise_dbm),
        f"{item.threshold_db:.2f}",
        item.rule,
        item.message,
        _utc_now() if item.phase == "acked" else "",
    ]


def _utc_now() -> str:
    return utc_now_iso()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _fmt_optional(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{float(value):.2f}"


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name.strip())
    return cleaned[:48] or "project"
