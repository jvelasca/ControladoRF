"""Filtro FI HackRF — auto/manual (paridad SDR++)."""
from __future__ import annotations

from core.monitor.monitor_iq_rf_logic import (
    patch_baseband_filter_auto,
    patch_baseband_filter_hz,
)
from core.monitor.spectrum_params import SpectrumParams


def test_baseband_filter_auto_tracks_sample_rate() -> None:
    params = SpectrumParams(capture_mode="iq", sample_rate_hz=2_000_000.0)
    params.baseband_filter_auto = True
    params.sync_baseband_filter_bw()
    assert params.baseband_filter_bw_hz == 1_750_000.0


def test_manual_baseband_filter_patch() -> None:
    params = SpectrumParams(capture_mode="iq", sample_rate_hz=2_000_000.0)
    updated = patch_baseband_filter_hz(params, 2_500_000.0)
    assert updated.baseband_filter_auto is False
    assert updated.baseband_filter_bw_hz == 2_500_000.0


def test_restore_auto_filter() -> None:
    params = patch_baseband_filter_hz(
        SpectrumParams(capture_mode="iq", sample_rate_hz=4_000_000.0),
        3_500_000.0,
    )
    restored = patch_baseband_filter_auto(params, enabled=True)
    assert restored.baseband_filter_auto is True
    assert restored.baseband_filter_bw_hz == 2_500_000.0
