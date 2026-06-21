"""Tests histórico de eventos de supervisión."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from core.monitor.supervision.alarm_catalog import RF_SNR_WARNING, resolve_alarm_type
from core.monitor.supervision.alarm_log_repository import (
    AlarmLogEntry,
    export_alarm_log_csv,
    filter_alarm_log_entries,
    read_alarm_log_csv,
)
from core.monitor.supervision.alarm_manager import AlarmTransition
from core.monitor.supervision.alarm_report import build_alarm_episodes, export_alarm_report_txt
from db.config import DatabaseConfig
from db.connection import Database
from db.migration import ensure_migrations
from db.repositories.supervision_event_repository import SupervisionEventRepository


def _transition(**kwargs) -> AlarmTransition:
    base = dict(
        channel_key="k1",
        label="Vocal 1",
        frequency_hz=100e6,
        severity="warning",
        phase="raised",
        rule="snr_below_warning",
        message="Low SNR",
        carrier_dbm=-40.0,
        noise_dbm=-50.0,
        snr_above_noise_db=4.0,
        threshold_db=6.0,
    )
    base.update(kwargs)
    if "alarm_type" not in base:
        base["alarm_type"] = resolve_alarm_type(
            rule=str(base["rule"]),
            phase=str(base["phase"]),
            severity=str(base["severity"]),
        )
    return AlarmTransition(**base)


@pytest.fixture
def event_db():
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(DatabaseConfig(path=Path(tmp) / "test.db"))
        db.connect()
        ensure_migrations(db)
        yield db
        db.close()


def test_alarm_log_csv_roundtrip(tmp_path):
    path = tmp_path / "events.csv"
    rows = [
        AlarmLogEntry(
            timestamp_utc="2026-06-12T10:00:00+00:00",
            alarm_type=RF_SNR_WARNING,
            channel_key="k1",
            label="Vocal 1",
            frequency_mhz=100.0,
            severity="warning",
            phase="raised",
            snr_db=4.0,
            carrier_dbm=-40.0,
            noise_dbm=-50.0,
            threshold_db=6.0,
            rule="snr_below_warning",
            message="Low SNR",
            ack_at="",
        )
    ]
    export_alarm_log_csv(rows, path)
    restored = read_alarm_log_csv(path)
    assert len(restored) == 1
    assert restored[0].channel_key == "k1"
    assert restored[0].phase == "raised"


def test_filter_alarm_log_entries():
    rows = [
        AlarmLogEntry(
            timestamp_utc="t",
            alarm_type=RF_SNR_WARNING,
            channel_key="k1",
            label="A",
            frequency_mhz=100.0,
            severity="warning",
            phase="raised",
            snr_db=None,
            carrier_dbm=None,
            noise_dbm=None,
            threshold_db=None,
            rule="",
            message="",
            ack_at="",
        ),
        AlarmLogEntry(
            timestamp_utc="t",
            alarm_type="RF_SNR_CRITICAL_LATCH",
            channel_key="k2",
            label="B",
            frequency_mhz=200.0,
            severity="critical",
            phase="latched",
            snr_db=None,
            carrier_dbm=None,
            noise_dbm=None,
            threshold_db=None,
            rule="",
            message="",
            ack_at="",
        ),
    ]
    filtered = filter_alarm_log_entries(rows, severity="critical")
    assert len(filtered) == 1
    assert filtered[0].channel_key == "k2"


def test_alarm_report_txt_episode(tmp_path):
    def _tr(key: str) -> str:
        return key

    rows = [
        AlarmLogEntry(
            timestamp_utc="2026-06-12T10:00:00+00:00",
            alarm_type=RF_SNR_WARNING,
            channel_key="k1",
            label="Vocal 1",
            frequency_mhz=100.0,
            severity="warning",
            phase="raised",
            snr_db=4.0,
            carrier_dbm=-40.0,
            noise_dbm=-50.0,
            threshold_db=6.0,
            rule="snr_below_warning",
            message="Low SNR",
            ack_at="",
        ),
        AlarmLogEntry(
            timestamp_utc="2026-06-12T10:05:00+00:00",
            alarm_type="RF_SNR_WARNING_LATCH",
            channel_key="k1",
            label="Vocal 1",
            frequency_mhz=100.0,
            severity="warning",
            phase="latched",
            snr_db=12.0,
            carrier_dbm=-30.0,
            noise_dbm=-50.0,
            threshold_db=6.0,
            rule="snr_recovered_warning",
            message="Recovered",
            ack_at="",
        ),
        AlarmLogEntry(
            timestamp_utc="2026-06-12T10:10:00+00:00",
            alarm_type="RF_ACK_MANUAL",
            channel_key="k1",
            label="Vocal 1",
            frequency_mhz=100.0,
            severity="warning",
            phase="acked",
            snr_db=None,
            carrier_dbm=None,
            noise_dbm=None,
            threshold_db=None,
            rule="manual_ack",
            message="Vocal 1",
            ack_at="2026-06-12T10:10:00+00:00",
        ),
    ]
    episodes = build_alarm_episodes(rows, tr=_tr)
    assert len(episodes) == 1
    assert episodes[0].label == "Vocal 1"
    assert episodes[0].end_utc is not None

    out_path = tmp_path / "report.txt"
    export_alarm_report_txt(rows, out_path, project_name="Demo", tr=_tr)
    text = out_path.read_text(encoding="utf-8")
    assert "monitor_alarm_report_title" in text
    assert "Vocal 1" in text


def test_supervision_event_repository_insert_and_list(event_db):
    repo = SupervisionEventRepository(event_db)
    repo.insert_transitions("proj-a", [_transition()])
    repo.insert_ack("proj-a", channel_key="k1", label="Vocal 1", manual=True)
    rows = repo.list_by_project("proj-a")
    assert len(rows) == 2
    assert rows[0].phase in ("raised", "acked")
    critical = repo.list_by_project("proj-a", severity="warning", phase="raised")
    assert len(critical) == 1
