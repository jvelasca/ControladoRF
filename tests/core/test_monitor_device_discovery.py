"""Tests de descubrimiento USB/backend Monitor."""
from core.monitor.device_discovery import (
    _serial_from_instance_id,
    detect_sources,
    idle_message_for_source,
)


def test_serial_from_instance_id():
    inst = r"USB\VID_1D50&PID_6089\000000000000000017C467DC339B4FC3"
    assert _serial_from_instance_id(inst) == "000000000000000017C467DC339B4FC3"


def test_detect_sources_has_mock():
    items = detect_sources(probe_backend=False)
    ids = [item.source_id for item in items]
    assert "mock" in ids


def test_idle_message_mock():
    msg = idle_message_for_source("mock")
    assert "Simul" in msg or "sint" in msg.lower() or "intern" in msg.lower()
