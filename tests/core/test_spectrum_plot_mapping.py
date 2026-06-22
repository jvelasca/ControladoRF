"""Tests eje frecuencia del espectro vs ventana FI/FF."""
import numpy as np
import pytest

from core.monitor.spectrum_params import SpectrumParams
from core.monitor.spectrum_plot_mapping import plot_freq_bounds


def test_plot_freq_bounds_prefers_freq_window_over_stale_frame():
    params = SpectrumParams(
        operating_mode="spectrum",
        capture_mode="sweep",
        span_mode="manual",
        manual_span_hz=21_000_000.0,
        span_hz=21_000_000.0,
        center_freq_hz=98_000_000.0,
        marker_start_hz=87_000_000.0,
        marker_stop_hz=108_000_000.0,
    )
    assert params.uses_start_stop_window()
    stale_freqs = np.linspace(95_000_000.0, 105_000_000.0, 256)
    start, stop = plot_freq_bounds(params, stale_freqs)
    assert start == pytest.approx(87_000_000.0)
    assert stop == pytest.approx(108_000_000.0)


def test_plot_freq_bounds_uses_frame_in_center_span_mode():
    params = SpectrumParams(
        operating_mode="spectrum",
        capture_mode="sweep",
        center_freq_hz=100_000_000.0,
        manual_span_hz=10_000_000.0,
        span_mode="manual",
    )
    freqs = np.linspace(95_000_000.0, 105_000_000.0, 128)
    start, stop = plot_freq_bounds(params, freqs)
    assert start == pytest.approx(95_000_000.0)
    assert stop == pytest.approx(105_000_000.0)


def test_plot_freq_bounds_iq_crops_usable_center_bandwidth():
    """IQ: no pintar el 10 % exterior de cada borde (roll-off / lobos FI-FF)."""
    params = SpectrumParams(
        operating_mode="sdr",
        capture_mode="iq",
        center_freq_hz=100_000_000.0,
        sample_rate_hz=10_000_000.0,
    )
    freqs = np.linspace(95_000_000.0, 105_000_000.0, 1024)
    start, stop = plot_freq_bounds(params, freqs)
    assert start == pytest.approx(96_000_000.0)
    assert stop == pytest.approx(104_000_000.0)
