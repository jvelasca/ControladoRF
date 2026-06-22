"""Tests de métricas RF y alineación espectro/waterfall."""
from __future__ import annotations

import numpy as np

from core.monitor.rf_metrics import compute_rf_link_metrics
from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams
from core.monitor.spectrum_plot_mapping import plot_freq_bounds, resample_power_to_grid


def test_resample_power_preserves_peak_position():
    n = 512
    center = 100_000_000.0
    span = 2_000_000.0
    freqs = np.linspace(center - span / 2, center + span / 2, n)
    power = np.full(n, -90.0)
    peak_idx = n // 4
    power[peak_idx] = -40.0

    grid = resample_power_to_grid(
        freqs,
        power,
        start_hz=float(freqs[0]),
        stop_hz=float(freqs[-1]),
        num_columns=n,
    )
    assert abs(int(np.argmax(grid)) - peak_idx) <= 3


def test_resample_power_suppresses_fft_edge_spikes():
    n = 256
    freqs = np.linspace(99e6, 101e6, n)
    power = np.full(n, -90.0)
    power[0] = -25.0
    power[-1] = -25.0
    power[n // 2] = -40.0

    grid = resample_power_to_grid(
        freqs,
        power,
        start_hz=98e6,
        stop_hz=102e6,
        num_columns=120,
    )
    assert float(grid[0]) < -50.0
    assert float(grid[-1]) < -50.0
    assert int(np.argmax(grid)) == 60


def test_plot_freq_bounds_uses_marker_window_without_frame():
    params = SpectrumParams(
        center_freq_hz=100e6,
        span_hz=2e6,
        capture_mode="sweep",
        marker_start_hz=99.5e6,
        marker_stop_hz=100.5e6,
    )
    start, stop = plot_freq_bounds(params, None)
    assert start == params.freq_start_hz()
    assert stop == params.freq_stop_hz()


def test_plot_freq_bounds_prefers_frame_freqs():
    params = SpectrumParams(
        center_freq_hz=100e6,
        span_hz=2e6,
        sample_rate_hz=2e6,
        capture_mode="iq",
        marker_start_hz=99.5e6,
        marker_stop_hz=100.5e6,
    )
    freqs = np.linspace(99e6, 101e6, 256)
    start, stop = plot_freq_bounds(params, freqs)
    assert start == float(freqs[0])
    assert stop == float(freqs[-1])


def test_rf_link_metrics_detects_tone():
    center = 470_000_000.0
    n = 1024
    freqs = np.linspace(center - 1_000_000, center + 1_000_000, n)
    power = np.full(n, -95.0)
    tone_idx = n // 2
    power[tone_idx - 2 : tone_idx + 3] = -45.0

    params = SpectrumParams(
        center_freq_hz=center,
        span_hz=2_000_000,
        selected_freq_hz=center,
        freq_readout="f",
    )
    frame = SpectrumFrame(
        freqs_hz=freqs,
        power_db=power,
        center_freq_hz=center,
        span_hz=2_000_000,
    )
    metrics = compute_rf_link_metrics(frame, params)
    assert metrics.channel_power_dbm is not None
    assert metrics.channel_power_dbm > -60.0
    assert metrics.snr_db is not None
    assert metrics.snr_db > 20.0
    assert metrics.link_score > 40


def test_rf_link_metrics_acp_uses_adjacent_bands():
    center = 100_000_000.0
    n = 2048
    freqs = np.linspace(center - 2_000_000, center + 2_000_000, n)
    power = np.full(n, -95.0)
    main_mask = (freqs >= center - 100_000) & (freqs <= center + 100_000)
    power[main_mask] = -45.0
    left_mask = (freqs >= center - 300_000) & (freqs < center - 100_000)
    power[left_mask] = -80.0
    right_mask = (freqs > center + 100_000) & (freqs <= center + 300_000)
    power[right_mask] = -75.0

    params = SpectrumParams(
        center_freq_hz=center,
        span_hz=4_000_000,
        selected_freq_hz=center,
        demod_bandwidth_hz=200_000,
        freq_readout="f",
    )
    frame = SpectrumFrame(
        freqs_hz=freqs,
        power_db=power,
        center_freq_hz=center,
        span_hz=4_000_000,
    )
    metrics = compute_rf_link_metrics(frame, params)
    assert metrics.acp_left_db is not None
    assert metrics.acp_right_db is not None
    assert metrics.acp_left_db > 30.0
    assert metrics.acp_right_db > 25.0
