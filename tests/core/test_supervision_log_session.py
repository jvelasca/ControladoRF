"""Tests sesión REC de log de supervisión."""
from __future__ import annotations

from core.monitor.supervision.alarm_log_repository import read_alarm_log_csv
from core.monitor.supervision.alarm_manager import AlarmTransition
from core.monitor.supervision.alarm_catalog import resolve_alarm_type
from core.monitor.supervision.supervision_log_session import SupervisionLogSessionManager


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


def test_rec_session_creates_csv_and_report(tmp_path):
    manager = SupervisionLogSessionManager()
    session = manager.start(log_root=tmp_path, project_name="demo")
    assert session.is_active
    assert session.csv_path.exists()
    assert session.txt_path.parent == session.directory

    from core.monitor.supervision.alarm_log_repository import AlarmLogRepository

    repo = AlarmLogRepository()
    repo.open_session_file(session.csv_path)
    repo.append([_transition()])
    repo.close_session()

    stopped = manager.stop(project_name="demo", tr=lambda key: key)
    assert stopped is not None
    assert not stopped.is_active
    assert stopped.event_count == 1
    assert stopped.txt_path.exists()
    assert stopped.txt_path.read_text(encoding="utf-8")
    entries = read_alarm_log_csv(stopped.csv_path)
    assert len(entries) == 1
    assert (stopped.directory / "session.json").exists()
