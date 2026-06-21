"""Estabilidad espectro IQ: RBW desacoplado y trazo estable al mover ganancia RX."""
from __future__ import annotations

import numpy as np

from core.monitor.monitor_bw_sweep_logic import patch_rbw_hz
from core.monitor.monitor_rf_limits import max_lna_gain_db, max_vga_gain_db
from core.monitor.spectrum_params import SpectrumParams
from core.monitor.iq_fft import compute_spectrum_frame


def _tone_samples(*, n: int, rate: float, offset_hz: float) -> np.ndarray:
    t = np.arange(n, dtype=np.float64) / rate
    return (0.4 * np.exp(2j * np.pi * offset_hz * t)).astype(np.complex64)


def test_iq_manual_rbw_updates_fft_size():
    params = SpectrumParams(
        capture_mode="iq",
        sample_rate_hz=2_000_000.0,
        fft_size=2048,
        rbw_auto=True,
    )
    updated = patch_rbw_hz(params, 50_000.0)
    assert updated.rbw_auto is False
    assert updated.fft_size == 64
    assert abs(updated.effective_rbw_hz() - 2_000_000.0 / 64) < 1.0
    assert abs(updated.rbw_hz - updated.effective_rbw_hz()) < 1.0


def test_spectrum_peak_stable_when_rx_gain_changes():
    """Misma señal RF de entrada: distinta ganancia RX → mismo pico en pantalla."""
    rate = 2_000_000.0
    n = 2048
    base = _tone_samples(n=n, rate=rate, offset_hz=80_000.0)

    low = SpectrumParams(
        center_freq_hz=93_200_000.0,
        sample_rate_hz=rate,
        fft_size=n,
        lna_gain_db=8,
        vga_gain_db=16,
        rf_amp_enable=False,
    )
    high = low.copy()
    high.lna_gain_db = 24
    high.vga_gain_db = 32

    low_gain_db = 8 + 16
    high_gain_db = 24 + 32
    samples_low = base * (10 ** (low_gain_db / 20.0))
    samples_high = base * (10 ** (high_gain_db / 20.0))

    f_low = compute_spectrum_frame(samples_low, low)
    f_high = compute_spectrum_frame(samples_high, high)
    p_low = float(np.max(f_low.power_db))
    p_high = float(np.max(f_high.power_db))
    assert abs(p_low - p_high) < 1.0


def test_vga_max_is_fixed_libhackrf_limit():
    assert max_vga_gain_db(40, False) == 62
    assert max_vga_gain_db(24, True) == 62
    assert max_lna_gain_db(62, False) == 40
