"""Tests parser y limpieza hackrf_sweep."""
import numpy as np

from core.monitor.hackrf_sweep_source import (
    parse_hackrf_sweep_output,
    resample_sweep_to_display_bins,
    sanitize_sweep_spectrum,
)


SAMPLE = """
2026-06-12, 19:31:02.093377, 100000000, 105000000, 1000000.00, 20, -49.69, -53.29
2026-06-12, 19:31:02.093377, 105000000, 110000000, 1000000.00, 20, -57.49, -54.79
"""


def test_parse_hackrf_sweep_output():
    freqs, power = parse_hackrf_sweep_output(SAMPLE)
    assert len(freqs) == 4
    assert len(power) == 4
    assert float(freqs[0]) == 100_000_000.0


def test_sanitize_merges_duplicate_bins_by_peak():
    freqs = np.array([100e6, 100e6, 101e6], dtype=float)
    power = np.array([-50.0, -120.0, -52.0], dtype=float)
    out_f, out_p = sanitize_sweep_spectrum(freqs, power)
    assert out_f.size == 2
    assert out_p[0] == -50.0


def test_sanitize_suppresses_isolated_downward_spike():
    freqs = np.linspace(100e6, 110e6, 11)
    power = np.full(11, -60.0)
    power[5] = -110.0
    _, out_p = sanitize_sweep_spectrum(freqs, power)
    assert out_p[5] > -95.0
    assert out_p[5] > power[5] + 15.0


def test_resample_sweep_avoids_deep_notches():
    freqs = np.linspace(1e6, 6e9, 500)
    power = np.full(500, -55.0)
    power[50] = -130.0
    power[250] = -125.0
    grid_f, grid_p = resample_sweep_to_display_bins(freqs, power, num_bins=256)
    assert grid_f.size == 256
    assert float(np.min(grid_p)) > -80.0
