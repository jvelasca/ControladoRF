"""Tests ruta de aplicación AUTO (sin colgar GUI / sin reiniciar IQ en PLAY)."""
from __future__ import annotations

import numpy as np

from core.monitor.monitor_flow_log import (
    AUTO_TUNE_APPLY_KEYS,
    is_auto_tune_hw_unchanged,
    is_auto_tune_soft_only_patch,
)
from core.monitor.sdr_auto_tune import (
    apply_wfm_auto_profile,
    compute_sdr_auto_tune,
    freeze_auto_tune_hw_for_live_capture,
    merge_auto_tune_params,
)
from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams
from tests.core.test_sdr_auto_tune import _frame_with_peak


def test_auto_tune_apply_keys_cover_wfm_profile() -> None:
    required = {
        "lna_gain_db",
        "vga_gain_db",
        "rf_amp_enable",
        "demod_bandwidth_hz",
        "demod_snap_interval",
        "demod_deemphasis",
        "demod_noise_blanker_db",
        "freq_readout",
        "vfo_freq_hz",
    }
    assert required <= AUTO_TUNE_APPLY_KEYS


def test_wfm_auto_profile_preserves_rds_and_stereo_prefs() -> None:
    prev = SpectrumParams(
        demod_wfm_rds=False,
        demod_wfm_stereo=False,
        center_freq_hz=93_200_000.0,
        sample_rate_hz=2_000_000.0,
        span_hz=2_000_000.0,
        manual_span_hz=2_000_000.0,
    )
    updated = apply_wfm_auto_profile(prev, tune_hz=93_200_000.0)
    assert updated.demod_wfm_rds is False
    assert updated.demod_wfm_stereo is False
    assert updated.lna_gain_db == 40
    assert updated.vga_gain_db == 18


def test_wfm_auto_profile_keeps_wide_span_when_adequate() -> None:
    prev = SpectrumParams(
        center_freq_hz=92_000_000.0,
        vfo_freq_hz=92_200_000.0,
        sample_rate_hz=4_000_000.0,
        span_hz=4_000_000.0,
        manual_span_hz=4_000_000.0,
    )
    updated = apply_wfm_auto_profile(prev, tune_hz=92_200_000.0)
    assert updated.sample_rate_hz == 4_000_000.0
    assert updated.center_freq_hz == 92_000_000.0


def test_wfm_auto_profile_raises_span_below_2mhz() -> None:
    prev = SpectrumParams(
        center_freq_hz=92_000_000.0,
        vfo_freq_hz=92_200_000.0,
        sample_rate_hz=1_000_000.0,
        span_hz=1_000_000.0,
        manual_span_hz=1_000_000.0,
    )
    updated = apply_wfm_auto_profile(prev, tune_hz=92_200_000.0)
    assert updated.sample_rate_hz == 2_000_000.0


def test_freeze_auto_tune_hw_restores_live_capture_window() -> None:
    prev = SpectrumParams(
        center_freq_hz=100_000_000.0,
        sample_rate_hz=4_000_000.0,
        span_hz=4_000_000.0,
        manual_span_hz=4_000_000.0,
        capture_mode="iq",
    )
    tuned = SpectrumParams(
        center_freq_hz=93_200_000.0,
        sample_rate_hz=2_000_000.0,
        span_hz=2_000_000.0,
        manual_span_hz=2_000_000.0,
        capture_mode="iq",
    )
    frozen = freeze_auto_tune_hw_for_live_capture(prev, tuned)
    assert frozen.center_freq_hz == prev.center_freq_hz
    assert frozen.sample_rate_hz == prev.sample_rate_hz
    assert frozen.span_hz == prev.span_hz
    assert frozen.lna_gain_db == tuned.lna_gain_db


def test_merge_auto_tune_params_overlays_tuned_fields() -> None:
    prev = SpectrumParams(lna_gain_db=8, demod_snap_interval=25_000.0, demod_wfm_rds=False)
    tuned = SpectrumParams(lna_gain_db=40, demod_snap_interval=100_000.0, demod_wfm_rds=True)
    merged = merge_auto_tune_params(prev, tuned)
    assert merged.lna_gain_db == 40
    assert merged.demod_snap_interval == 100_000.0
    assert merged.demod_wfm_rds is True


def test_auto_tune_soft_only_when_snap_and_gains_change() -> None:
    prev = SpectrumParams(
        operating_mode="sdr",
        capture_mode="iq",
        center_freq_hz=92_000_000.0,
        sample_rate_hz=2_000_000.0,
        span_hz=2_000_000.0,
        manual_span_hz=2_000_000.0,
        lna_gain_db=8,
        demod_snap_interval=25_000.0,
        freq_readout="fc",
    )
    tuned = prev.copy()
    tuned.lna_gain_db = 40
    tuned.vga_gain_db = 18
    tuned.demod_snap_interval = 100_000.0
    tuned.freq_readout = "f"
    assert is_auto_tune_soft_only_patch(prev, tuned)
    assert is_auto_tune_hw_unchanged(prev, tuned)


def test_auto_tune_not_soft_when_center_changes() -> None:
    prev = SpectrumParams(
        center_freq_hz=92_000_000.0,
        sample_rate_hz=2_000_000.0,
        span_hz=2_000_000.0,
        manual_span_hz=2_000_000.0,
    )
    tuned = prev.copy()
    tuned.center_freq_hz = 105_000_000.0
    assert not is_auto_tune_hw_unchanged(prev, tuned)


def test_compute_auto_tune_does_not_force_rds_on() -> None:
    params = SpectrumParams(
        center_freq_hz=92_000_000.0,
        vfo_freq_hz=92_200_000.0,
        selected_freq_hz=92_200_000.0,
        operating_mode="sdr",
        audio_enabled=True,
        capture_mode="iq",
        sample_rate_hz=2_000_000.0,
        span_hz=2_000_000.0,
        manual_span_hz=2_000_000.0,
        demod_mode="wfm",
        demod_wfm_rds=False,
    )
    frame = _frame_with_peak(center_hz=92e6, peak_hz=92.2e6, peak_db=-30.0)
    result = compute_sdr_auto_tune(params, frame)
    assert result.ok
    assert result.params.demod_wfm_rds is False


def test_compute_auto_tune_am_mode_adjusts_gains_not_wfm_preset() -> None:
    params = SpectrumParams(
        center_freq_hz=1_000_000.0,
        vfo_freq_hz=1_000_000.0,
        operating_mode="sdr",
        audio_enabled=True,
        capture_mode="iq",
        sample_rate_hz=2_000_000.0,
        span_hz=2_000_000.0,
        manual_span_hz=2_000_000.0,
        demod_mode="am",
        lna_gain_db=8,
        vga_gain_db=8,
    )
    freqs = np.linspace(0.5e6, 1.5e6, 256)
    power = np.full(256, -85.0)
    idx = np.argmin(np.abs(freqs - 1.0e6))
    power[idx - 1 : idx + 2] = -30.0
    frame = SpectrumFrame(
        freqs_hz=freqs,
        power_db=power,
        center_freq_hz=1e6,
        span_hz=2e6,
        ref_level_dbm=0.0,
        ref_range_db=100.0,
    )
    result = compute_sdr_auto_tune(params, frame)
    assert result.ok
    assert result.params.demod_mode == "am"
    assert result.params.demod_bandwidth_hz == 1_000.0
    assert result.params.lna_gain_db >= 8


def test_compute_auto_tune_nfm_mode() -> None:
    params = SpectrumParams(
        center_freq_hz=145_000_000.0,
        vfo_freq_hz=145_500_000.0,
        operating_mode="sdr",
        audio_enabled=True,
        capture_mode="iq",
        sample_rate_hz=2_000_000.0,
        demod_mode="nfm",
    )
    frame = _frame_with_peak(center_hz=145.25e6, peak_hz=145.5e6, peak_db=-32.0)
    result = compute_sdr_auto_tune(params, frame)
    assert result.ok
    assert result.params.demod_mode == "nfm"
    assert result.params.demod_bandwidth_hz == 12_500.0
