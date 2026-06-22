"""Tests de entrada por canal."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from core.rf.channel_input import (
    format_channel_display,
    format_channel_readout,
    parse_channel_input,
    snap_channel_frequency,
    step_channel_frequency,
)
from core.rf.channelization_seed import ensure_channelization_seed
from core.rf.channelization_service import ChannelizationService
from db.config import DatabaseConfig
from db.connection import Database
from db.migration import ensure_migrations
from db.repositories.rf_channelization_prefs_repository import RfChannelizationPrefsRepository
from db.repositories.rf_standard_repository import RfStandardRepository


@pytest.fixture
def channelization_service():
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(DatabaseConfig(path=Path(tmp) / "test.db"))
        db.connect()
        ensure_migrations(db)
        ensure_channelization_seed(db)
        service = ChannelizationService(
            RfStandardRepository(db),
            RfChannelizationPrefsRepository(db),
        )
        yield service
        db.close()


def test_format_fm_channel(channelization_service):
    label = format_channel_display(channelization_service, 87.5e6)
    assert label == "FM1"


def test_format_channel_readout(channelization_service):
    text = format_channel_readout(channelization_service, 87.5e6)
    assert text == "87.500000 (FM1)"


def test_parse_channel_readout_text(channelization_service):
    hz = parse_channel_input(channelization_service, "87.600000 (FM2)")
    assert hz == pytest.approx(87.6e6)


def test_parse_fm_channel_label(channelization_service):
    hz = parse_channel_input(channelization_service, "FM1")
    assert hz == pytest.approx(87.5e6)


def test_step_fm_channel(channelization_service):
    hz = step_channel_frequency(channelization_service, 87.5e6, 1)
    assert hz == pytest.approx(87.6e6)


def test_snap_fm_channel(channelization_service):
    hz = snap_channel_frequency(channelization_service, 87.65e6)
    assert hz == pytest.approx(87.6e6)
