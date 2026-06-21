"""Informe de alarmas de supervisión — episodios y exportación TXT."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from core.monitor.supervision.alarm_catalog import (
    alarm_type_label,
    format_alarm_cause,
    get_alarm_type,
    resolve_alarm_type,
)
from core.monitor.supervision.alarm_log_repository import AlarmLogEntry


@dataclass
class AlarmReportEpisode:
    index: int
    alarm_type: str
    channel_key: str
    label: str
    frequency_mhz: Optional[float]
    severity: str
    start_utc: datetime
    end_utc: Optional[datetime]
    snr_db: Optional[float]
    threshold_db: Optional[float]
    cause: str = ""
    resolution: str = ""
    resolution_utc: Optional[datetime] = None
    open: bool = False


@dataclass
class AlarmReportMeta:
    project_name: str = ""
    generated_at: Optional[datetime] = None
    source_rows: int = 0


def parse_alarm_timestamp(value: str) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def build_alarm_episodes(
    entries: Iterable[AlarmLogEntry],
    *,
    tr: Callable[[str], str],
) -> List[AlarmReportEpisode]:
    """Agrupa eventos en incidentes con inicio, fin, causa y resolución."""
    rows = sorted(
        list(entries),
        key=lambda row: (parse_alarm_timestamp(row.timestamp_utc) or datetime.min.replace(tzinfo=timezone.utc), row.channel_key),
    )
    episodes: List[AlarmReportEpisode] = []
    open_by_channel: dict[str, AlarmReportEpisode] = {}

    for row in rows:
        alarm_type = row.alarm_type or resolve_alarm_type(
            rule=row.rule,
            phase=row.phase,
            severity=row.severity,
        )
        ts = parse_alarm_timestamp(row.timestamp_utc) or datetime.now(timezone.utc)
        definition = get_alarm_type(alarm_type)
        phase = row.phase

        if phase == "raised" and definition is not None and definition.phase == "raised":
            previous = open_by_channel.pop(row.channel_key, None)
            if previous is not None and previous.open:
                previous.open = False
                if previous.end_utc is None:
                    previous.end_utc = ts
                episodes.append(previous)
            cause = format_alarm_cause(
                alarm_type,
                tr,
                snr_db=row.snr_db,
                threshold_db=row.threshold_db,
                label=row.label,
                frequency_mhz=row.frequency_mhz,
            )
            episode = AlarmReportEpisode(
                index=0,
                alarm_type=alarm_type,
                channel_key=row.channel_key,
                label=row.label,
                frequency_mhz=row.frequency_mhz,
                severity=row.severity,
                start_utc=ts,
                end_utc=None,
                snr_db=row.snr_db,
                threshold_db=row.threshold_db,
                cause=cause,
                open=True,
            )
            open_by_channel[row.channel_key] = episode
            continue

        open_episode = open_by_channel.get(row.channel_key)
        if open_episode is None:
            if phase in ("acked", "cleared") and not row.severity:
                cause = format_alarm_cause(
                    alarm_type,
                    tr,
                    label=row.label,
                    frequency_mhz=row.frequency_mhz,
                )
                episodes.append(
                    AlarmReportEpisode(
                        index=0,
                        alarm_type=alarm_type,
                        channel_key=row.channel_key,
                        label=row.label,
                        frequency_mhz=row.frequency_mhz,
                        severity=row.severity,
                        start_utc=ts,
                        end_utc=ts,
                        snr_db=row.snr_db,
                        threshold_db=row.threshold_db,
                        cause=cause,
                        resolution=_resolution_text(alarm_type, tr, ts),
                        resolution_utc=ts,
                    )
                )
            continue

        if phase == "latched":
            open_episode.end_utc = open_episode.end_utc or ts
            open_episode.resolution = tr("monitor_alarm_resolution_latched")
            continue

        if phase in ("acked", "cleared"):
            end_ts = parse_alarm_timestamp(row.ack_at) or ts
            open_episode.end_utc = end_ts
            open_episode.resolution = _resolution_text(alarm_type, tr, end_ts)
            open_episode.resolution_utc = end_ts
            open_episode.open = False
            episodes.append(open_episode)
            open_by_channel.pop(row.channel_key, None)

    for episode in open_by_channel.values():
        if episode.open:
            episode.resolution = tr("monitor_alarm_resolution_open")
            episodes.append(episode)

    episodes.sort(key=lambda item: item.start_utc, reverse=True)
    for index, episode in enumerate(episodes, start=1):
        episode.index = index
    return episodes


def format_alarm_report_txt(
    episodes: Iterable[AlarmReportEpisode],
    *,
    meta: AlarmReportMeta,
    tr: Callable[[str], str],
) -> str:
    rows = list(episodes)
    generated = meta.generated_at or datetime.now(timezone.utc)
    lines: List[str] = [
        "=" * 70,
        tr("monitor_alarm_report_title"),
        "=" * 70,
        tr("monitor_alarm_report_project").format(project=meta.project_name or "—"),
        tr("monitor_alarm_report_generated").format(
            datetime=_format_report_datetime(generated, tr)
        ),
        tr("monitor_alarm_report_rows").format(count=meta.source_rows),
        tr("monitor_alarm_report_incidents").format(count=len(rows)),
        "",
    ]

    if not rows:
        lines.append(tr("monitor_alarm_report_empty"))
        lines.append("")
        return "\n".join(lines)

    for episode in rows:
        title = tr("monitor_alarm_report_item_title").format(
            index=episode.index,
            type=alarm_type_label(episode.alarm_type, tr),
        )
        lines.extend(
            [
                "-" * 70,
                title,
                "-" * 70,
                _field(tr("monitor_alarm_report_field_channel"), episode.label),
                _field(
                    tr("monitor_alarm_report_field_frequency"),
                    _format_frequency(episode.frequency_mhz),
                ),
                _field(
                    tr("monitor_alarm_report_field_start"),
                    _format_report_datetime(episode.start_utc, tr),
                ),
                _field(
                    tr("monitor_alarm_report_field_end"),
                    _format_report_datetime(episode.end_utc, tr)
                    if episode.end_utc
                    else tr("monitor_alarm_report_field_end_open"),
                ),
                _field(
                    tr("monitor_alarm_report_field_duration"),
                    _format_duration(episode.start_utc, episode.end_utc, tr),
                ),
                _field(tr("monitor_alarm_report_field_cause"), episode.cause or "—"),
                _field(
                    tr("monitor_alarm_report_field_resolution"),
                    episode.resolution or tr("monitor_alarm_report_field_resolution_none"),
                ),
                "",
            ]
        )
    return "\n".join(lines)


def export_alarm_report_txt(
    entries: Iterable[AlarmLogEntry],
    path: Path | str,
    *,
    project_name: str = "",
    tr: Callable[[str], str],
) -> None:
    rows = list(entries)
    episodes = build_alarm_episodes(rows, tr=tr)
    meta = AlarmReportMeta(
        project_name=project_name,
        generated_at=datetime.now(timezone.utc),
        source_rows=len(rows),
    )
    text = format_alarm_report_txt(episodes, meta=meta, tr=tr)
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(text, encoding="utf-8")


def _resolution_text(alarm_type: str, tr: Callable[[str], str], when: datetime) -> str:
    definition = get_alarm_type(alarm_type)
    if definition is None or not definition.i18n_resolution_key:
        return tr("monitor_alarm_resolution_manual").format(
            datetime=_format_report_datetime(when, tr)
        )
    return tr(definition.i18n_resolution_key).format(
        datetime=_format_report_datetime(when, tr)
    )


def _field(label: str, value: str) -> str:
    dots = max(1, 18 - len(label))
    return f"{label}{'.' * dots} {value}"


def _format_frequency(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{float(value):.3f} MHz"


def _format_report_datetime(value: Optional[datetime], tr: Callable[[str], str]) -> str:
    if value is None:
        return "—"
    local = value.astimezone(timezone.utc)
    clock = tr("monitor_alarm_report_time_format").format(
        hour=local.hour,
        minute=local.minute,
        second=local.second,
    )
    return tr("monitor_alarm_report_datetime_format").format(
        date=local.strftime("%d/%m/%Y"),
        time=clock,
        tz="UTC",
    )


def _format_duration(
    start: datetime,
    end: Optional[datetime],
    tr: Callable[[str], str],
) -> str:
    if end is None:
        return tr("monitor_alarm_report_duration_open")
    seconds = max(0, int((end - start).total_seconds()))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return tr("monitor_alarm_report_duration_format").format(
        hours=hours,
        minutes=minutes,
        seconds=secs,
    )
