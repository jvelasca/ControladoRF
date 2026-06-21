"""Tests tap IQ compartido motor RF v2."""
from __future__ import annotations

from core.rf.demod_iq_source import RfDemodIqSource
from core.rf.devices.hackrf.device import HackRfDevice
from core.rf.session import RfSession


def test_hackrf_demod_iq_source_from_session():
    session = RfSession(device=HackRfDevice())
    session.attach_source("hackrf")
    session.open()
    tap = session.create_demod_iq_source()
    assert tap is not None
    assert isinstance(tap, RfDemodIqSource)
    assert tap.source_id == "hackrf"


def test_mock_device_has_no_demod_iq_source():
    session = RfSession()
    session.attach_source("mock")
    assert session.create_demod_iq_source() is None
