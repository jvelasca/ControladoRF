"""Tests ajuste automático SDR."""
from __future__ import annotations

import numpy as np

from core.monitor.sdr_auto_tune import _select_rf_gains, _select_wfm_rf_gains, compute_sdr_auto_tune
from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams


def _frame_with_peak(*, center_hz: float, peak_hz: float, peak_db: float = -35.0) -> SpectrumFrame:
    n = 512
    freqs = np.linspace(center_hz - 1e6, center_hz + 1e6, n)
    power = np.full(n, -90.0, dtype=float)
    idx = int(np.argmin(np.abs(freqs - peak_hz)))
    power[max(0, idx - 2) : idx + 3] = peak_db
    return SpectrumFrame(
        freqs_hz=freqs,
        power_db=power,
        center_freq_hz=center_hz,
        span_hz=2e6,
        ref_level_dbm=0.0,
        ref_range_db=100.0,
    )


def test_auto_tune_wfm_uses_broadcast_span_and_bw() -> None:
    params = SpectrumParams(
        center_freq_hz=92_000_000.0,
        vfo_freq_hz=92_200_000.0,
        selected_freq_hz=92_200_000.0,
        operating_mode="sdr",
        audio_enabled=True,
        capture_mode="iq",
        sample_rate_hz=4_000_000.0,
        span_hz=4_000_000.0,
        manual_span_hz=4_000_000.0,
        lna_gain_db=8,
        vga_gain_db=8,
        rf_amp_enable=False,
        demod_mode="wfm",
        squelch_db=-75.0,
    )
    frame = _frame_with_peak(center_hz=92e6, peak_hz=92.2e6, peak_db=-28.0)
    result = compute_sdr_auto_tune(params, frame)
    assert result.ok
    p = result.params
    assert p.capture_mode == "iq"
    assert p.sample_rate_hz == 4_000_000.0
    assert p.center_freq_hz == 92_000_000.0
    assert p.demod_bandwidth_hz == 200_000.0
    assert p.lna_gain_db == 40
    assert p.vga_gain_db == 18
    assert p.rf_amp_enable is True
    assert p.rf_bias_tee_enable is False
    assert p.demod_iq_correction is False
    assert p.demod_iq_invert is False
    assert p.freq_offset_hz == 0.0
    assert p.squelch_db == -75.0
    assert abs(p.vfo_freq_hz - 92_200_000.0) < 1.0
    assert p.demod_wfm_stereo is True


def test_auto_tune_raises_narrow_span_to_2mhz_for_wfm() -> None:
    params = SpectrumParams(
        center_freq_hz=92_000_000.0,
        vfo_freq_hz=92_200_000.0,
        operating_mode="sdr",
        audio_enabled=True,
        capture_mode="iq",
        sample_rate_hz=1_000_000.0,
        span_hz=1_000_000.0,
        manual_span_hz=1_000_000.0,
        demod_mode="wfm",
    )
    frame = _frame_with_peak(center_hz=92e6, peak_hz=92.2e6, peak_db=-30.0)
    result = compute_sdr_auto_tune(params, frame)
    assert result.ok
    assert result.params.sample_rate_hz == 2_000_000.0


def test_auto_tune_rejects_without_frame() -> None:
    params = SpectrumParams(operating_mode="sdr", audio_enabled=True)
    result = compute_sdr_auto_tune(params, None)
    assert not result.ok
    assert result.summary == "monitor_auto_tune_no_frame"


def test_preamp_off_first_when_signal_adequate() -> None:
    params = SpectrumParams(source_id="hackrf")
    gain = _select_rf_gains(params, signal_db=-28.0, noise_db=-90.0, snr=25.0)
    assert not gain.amp


def test_preamp_trial_considers_on_for_weak_signal() -> None:
    params = SpectrumParams(source_id="hackrf")
    gain = _select_rf_gains(params, signal_db=-58.0, noise_db=-78.0, snr=4.5)
    assert gain.lna >= 24


def test_wfm_gains_reference_uses_sdrpp_vga18() -> None:
    from core.monitor.wfm_broadcast_profile import apply_sdrpp_wfm_reference

    params = apply_sdrpp_wfm_reference(SpectrumParams(source_id="hackrf"), tune_hz=105_200_000.0)
    assert params.lna_gain_db == 40
    assert params.vga_gain_db == 18
    assert params.rf_amp_enable is True
    assert params.demod_snap_interval == 100_000.0


def test_wfm_gains_respect_minimum_floor() -> None:
    params = SpectrumParams(source_id="hackrf")
    gain = _select_wfm_rf_gains(params, signal_db=-28.0, snr=25.0)
    assert gain.lna >= 24
    assert gain.vga >= 28


def test_auto_tune_wfm_keeps_user_tune_not_distant_peak() -> None:
    params = SpectrumParams(
        center_freq_hz=93_200_000.0,
        vfo_freq_hz=93_200_000.0,
        selected_freq_hz=93_200_000.0,
        operating_mode="sdr",
        audio_enabled=True,
        capture_mode="iq",
        sample_rate_hz=2_000_000.0,
        span_hz=2_000_000.0,
        manual_span_hz=2_000_000.0,
        demod_mode="wfm",
    )
    n = 512
    freqs = np.linspace(92.2e6, 94.2e6, n)
    power = np.full(n, -90.0, dtype=float)
    center_idx = n // 2
    power[center_idx - 1 : center_idx + 2] = -20.0
    station_idx = int(np.argmin(np.abs(freqs - 94.0e6)))
    power[station_idx - 1 : station_idx + 2] = -38.0
    frame = SpectrumFrame(
        freqs_hz=freqs,
        power_db=power,
        center_freq_hz=93.2e6,
        span_hz=2e6,
        ref_level_dbm=0.0,
        ref_range_db=100.0,
    )
    result = compute_sdr_auto_tune(params, frame)
    assert result.ok
    assert abs(result.params.vfo_freq_hz - 93_200_000.0) < 1.0
