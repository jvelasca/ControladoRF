"""Tests del catálogo de canalización RF."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from core.rf.channelization_seed import (
    CATALOG_VERSION,
    DVB_T_ES_LAST,
    ensure_channelization_seed,
)
from core.rf.channelization_service import ChannelizationService
from db.config import DatabaseConfig
from db.connection import Database
from db.migration import ensure_migrations
from db.repositories.rf_channelization_prefs_repository import RfChannelizationPrefsRepository
from db.repositories.rf_standard_repository import RfStandardRepository


@pytest.fixture
def channelization_db():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        db = Database(DatabaseConfig(path=db_path))
        db.connect()
        ensure_migrations(db)
        ensure_channelization_seed(db)
        yield db
        db.close()


def test_seed_creates_eight_standards(channelization_db):
    repo = RfStandardRepository(channelization_db)
    assert repo.count_standards() == 8


def test_catalog_version_is_current(channelization_db):
    row = channelization_db.fetchone(
        "SELECT value FROM rf_app_channelization WHERE key = 'catalog_version'"
    )
    assert row is not None
    assert int(row["value"]) == CATALOG_VERSION


def test_fm_eu_channel_count(channelization_db):
    repo = RfStandardRepository(channelization_db)
    channels = repo.list_channels("FM_EU_100K")
    assert len(channels) == 206
    assert channels[0].center_freq_hz == pytest.approx(87.5e6)
    assert channels[-1].center_freq_hz == pytest.approx(108.0e6)


def test_dvb_t_channels(channelization_db):
    repo = RfStandardRepository(channelization_db)
    eu = repo.list_channels("DVB-T_EU")
    es = repo.list_channels("DVB-T_ES")
    assert len(eu) == 49
    assert len(es) == 28
    assert eu[0].channel_number == 21
    assert eu[0].center_freq_hz == pytest.approx(474.0e6)
    assert es[-1].channel_number == DVB_T_ES_LAST
    assert es[-1].center_freq_hz == pytest.approx(690.0e6)


def test_spain_mobile_700_blocks(channelization_db):
    repo = RfStandardRepository(channelization_db)
    channels = repo.list_channels("MOBILE_700_ES")
    assert len(channels) == 12
    assert channels[0].channel_number == 49
    assert channels[0].center_freq_hz == pytest.approx(698.0e6)
    assert channels[-1].channel_number == 60
    assert channels[-1].center_freq_hz == pytest.approx(786.0e6)


def test_spain_lte_800_and_5g(channelization_db):
    repo = RfStandardRepository(channelization_db)
    b20 = repo.list_channels("MOBILE_800_ES")
    lte = repo.list_channels("MOBILE_LTE_ES")
    nr = repo.list_channels("MOBILE_5G_ES")
    assert {ch.channel_label for ch in b20} == {"B20-DL", "B20-UL"}
    assert len(lte) == 4
    assert any(ch.channel_label == "n78-3500" for ch in nr)


def test_channelization_service_resolve(channelization_db):
    service = ChannelizationService(
        RfStandardRepository(channelization_db),
        RfChannelizationPrefsRepository(channelization_db),
    )
    freq = service.resolve_frequency_hz("FM_EU_100K", channel_number=1)
    assert freq == pytest.approx(87.5e6)
    ch = service.find_nearest_channel("FM_US_200K", 100.1e6)
    assert ch is not None
    assert ch.center_freq_hz == pytest.approx(100.1e6)
    tdt48 = service.resolve_channel("DVB-T_ES", label="CH48")
    assert tdt48 is not None
    assert tdt48.center_freq_hz == pytest.approx(690.0e6)


def test_default_state_prefs(channelization_db):
    service = ChannelizationService(
        RfStandardRepository(channelization_db),
        RfChannelizationPrefsRepository(channelization_db),
    )
    state = service.get_state()
    assert state.active_region == "ES"
    assert "FM_EU_100K" in state.active_standard_ids
    assert "DVB-T_ES" in state.active_standard_ids
    assert "MOBILE_700_ES" in state.active_standard_ids


def test_catalog_upgrade_from_legacy_v1():
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(DatabaseConfig(path=Path(tmp) / "legacy.db"))
        db.connect()
        ensure_migrations(db)
        try:
            with db.transaction():
                db.execute(
                    """
                    INSERT INTO rf_standards (
                        id, name, region_code, service_type,
                        freq_min_hz, freq_max_hz, channel_spacing_hz, metadata_json, enabled
                    ) VALUES ('DVB-T_ES', 'old', 'ES', 'dvb-t', 474e6, 862e6, 8e6, '{}', 1)
                    """
                )
                for n in range(21, 70):
                    center = 474.0e6 + (n - 21) * 8_000_000.0
                    db.execute(
                        """
                        INSERT INTO rf_standard_channels (
                            standard_id, channel_number, channel_label,
                            center_freq_hz, bandwidth_hz, sort_order, metadata_json
                        ) VALUES ('DVB-T_ES', ?, ?, ?, 8e6, ?, '{}')
                        """,
                        (n, f"CH{n}", center, n),
                    )
                db.execute(
                    """
                    INSERT INTO rf_app_channelization (key, value)
                    VALUES ('active_standards_json', '["FM_EU_100K","DVB-T_ES"]')
                    """
                )
            ensure_channelization_seed(db)
            repo = RfStandardRepository(db)
            es = repo.list_channels("DVB-T_ES")
            assert len(es) == 28
            assert repo.get_standard("MOBILE_700_ES") is not None
            row = db.fetchone(
                "SELECT value FROM rf_app_channelization WHERE key = 'catalog_version'"
            )
            assert int(row["value"]) == CATALOG_VERSION
        finally:
            db.close()


def test_spectrum_allocation_segments_respect_span(channelization_db):
    service = ChannelizationService(
        RfStandardRepository(channelization_db),
        RfChannelizationPrefsRepository(channelization_db),
    )
    state = service.get_state()
    state.show_spectrum_allocations = True
    state.active_standard_ids = ["DVB-T_ES"]
    service.save_state(state)

    empty = service.spectrum_allocation_segments(100e6, 200e6)
    assert empty == []

    segments = service.spectrum_allocation_segments(470e6, 510e6)
    assert segments
    assert all(seg.service_type == "dvb-t" for seg in segments)
    assert all(
        seg.freq_max_hz >= 470e6 and seg.freq_min_hz <= 510e6 for seg in segments
    )


def test_spectrum_allocation_segments_disabled_by_pref(channelization_db):
    service = ChannelizationService(
        RfStandardRepository(channelization_db),
        RfChannelizationPrefsRepository(channelization_db),
    )
    state = service.get_state()
    state.show_spectrum_allocations = False
    service.save_state(state)
    assert service.spectrum_allocation_segments(470e6, 510e6) == []


def test_user_exclusions_roundtrip(channelization_db):
    service = ChannelizationService(
        RfStandardRepository(channelization_db),
        RfChannelizationPrefsRepository(channelization_db),
    )
    from core.rf.spectrum_user_exclusions import SpectrumUserExclusion

    item = SpectrumUserExclusion(
        id="DVB-T_ES:CH21",
        label="CH21",
        standard_id="DVB-T_ES",
        freq_min_hz=470e6,
        freq_max_hz=478e6,
        color_hex="#c0404088",
    )
    service.upsert_user_exclusion(item)
    loaded = service.find_user_exclusion("DVB-T_ES:CH21")
    assert loaded is not None
    assert loaded.label == "CH21"
    service.remove_user_exclusion("DVB-T_ES:CH21")
    assert service.find_user_exclusion("DVB-T_ES:CH21") is None


def test_clear_user_exclusions(channelization_db):
    service = ChannelizationService(
        RfStandardRepository(channelization_db),
        RfChannelizationPrefsRepository(channelization_db),
    )
    from core.rf.spectrum_user_exclusions import SpectrumUserExclusion

    service.upsert_user_exclusion(
        SpectrumUserExclusion(
            id="A:1",
            label="1",
            standard_id="A",
            freq_min_hz=100e6,
            freq_max_hz=101e6,
        )
    )
    service.clear_user_exclusions()
    assert service.list_user_exclusions() == []
