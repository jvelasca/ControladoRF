"""Notch DC IQ — portadora FM vs spur LO."""
from __future__ import annotations

import numpy as np

from core.monitor.iq_fft import apply_display_band_edge_guard, apply_display_dc_notch, find_peak_excluding_dc, interior_power_db


def _fm_like_spectrum(n: int = 801) -> np.ndarray:
    power = np.full(n, -75.0, dtype=float)
    center = n // 2
    for offset in range(-40, 41):
        idx = center + offset
        if 0 <= idx < n:
            power[idx] = -20.0 - abs(offset) * 0.15
    return power


def test_dc_notch_preserves_fm_carrier_with_sidebands():
    power = _fm_like_spectrum()
    center = power.size // 2
    before = float(power[center])
    out = apply_display_dc_notch(power, center_freq_hz=98e6, sample_rate_hz=20e6)
    assert float(out[center]) >= before - 1.0


def test_dc_notch_suppresses_isolated_lo_spur():
    power = np.full(801, -70.0, dtype=float)
    center = power.size // 2
    power[center] = -15.0
    out = apply_display_dc_notch(power, center_freq_hz=98e6, sample_rate_hz=20e6)
    assert float(out[center]) < -60.0


def test_dc_notch_suppresses_moderate_lo_spur():
    """Fuga LO típica en IQ: pico central moderado sobre ruido (responde al VGA)."""
    power = np.full(1024, -72.0, dtype=float)
    center = power.size // 2
    power[center] = -52.0
    out = apply_display_dc_notch(power, center_freq_hz=98e6, sample_rate_hz=20e6)
    assert float(out[center]) < -65.0


def test_dc_notch_tracks_gain_like_lo_not_fm():
    """Tras bajar VGA el spur baja pero sigue siendo LO espurio, no portadora FM."""
    power = np.full(1024, -72.0, dtype=float)
    center = power.size // 2
    for spur_db in (-35.0, -50.0, -58.0):
        trial = power.copy()
        trial[center] = spur_db
        out = apply_display_dc_notch(trial, center_freq_hz=98e6, sample_rate_hz=20e6)
        assert float(out[center]) < -65.0


def test_band_edge_guard_clamps_fi_ff_spikes():
    n = 1024
    power = np.full(n, -70.0, dtype=float)
    power[0] = -18.0
    power[-1] = -18.0
    center = n // 2
    power[center - 5 : center + 6] = -35.0
    out = apply_display_band_edge_guard(power)
    assert float(out[0]) < -50.0
    assert float(out[-1]) < -50.0
    assert float(out[center]) == -35.0


def test_find_peak_skips_band_edges():
    n = 1024
    center = 97.3e6
    rate = 10e6
    freqs = np.linspace(center - rate / 2, center + rate / 2, n)
    power = np.full(n, -75.0, dtype=float)
    power[0] = -20.0
    power[-1] = -20.0
    carrier_idx = n // 2 + 30
    power[carrier_idx] = -38.0
    peak = find_peak_excluding_dc(
        freqs,
        power,
        center_freq_hz=center,
        sample_rate_hz=rate,
    )
    assert peak is not None
    assert abs(peak[0] - freqs[carrier_idx]) < rate / n * 3


def test_interior_power_excludes_center_dc_bin():
    n = 1024
    power = np.full(n, -75.0, dtype=float)
    power[n // 2] = -20.0
    power[n // 2 + 40] = -38.0
    interior = interior_power_db(power)
    assert float(np.max(interior)) <= -38.0 + 0.1
    assert float(np.max(interior)) > -50.0
