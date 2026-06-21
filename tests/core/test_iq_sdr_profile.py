"""Perfil IQ/SDR — hardware vs pantalla."""
from __future__ import annotations

from core.monitor.iq_sdr_profile import prepare_iq_for_play, sync_iq_hardware
from core.monitor.monitor_bw_sweep_logic import patch_trace_smooth_bins
from core.monitor.spectrum_params import SpectrumParams


def test_prepare_iq_does_not_force_trace_smooth_off():
    params = SpectrumParams(capture_mode="iq", trace_smooth_auto=False, trace_smooth_bins=5)
    prepare_iq_for_play(params)
    assert params.trace_smooth_auto is False
    assert params.trace_smooth_bins == 5


def test_trace_smooth_manual_patch_works_in_iq():
    params = SpectrumParams(capture_mode="iq", trace_smooth_auto=True)
    updated = patch_trace_smooth_bins(params, 11)
    assert updated.trace_smooth_auto is False
    assert updated.trace_smooth_bins == 11


def test_hardware_sync_sets_baseband_filter():
    params = SpectrumParams(capture_mode="iq", sample_rate_hz=2_000_000.0)
    sync_iq_hardware(params)
    assert params.baseband_filter_bw_hz == 1_750_000.0
