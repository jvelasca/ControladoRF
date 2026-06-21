"""Tests FFT IQ Monitor."""
import numpy as np

from core.monitor.iq_fft import (
    compute_spectrum_frame,
    find_peak_excluding_dc,
    iq_bytes_to_complex,
    spectrum_frame_from_iq_bytes,
)
from core.monitor.spectrum_params import SpectrumParams


def test_iq_bytes_to_complex_tone():
    n = 256
    t = np.arange(n, dtype=np.float32)
    i = (127 * np.cos(2 * np.pi * 10 * t / n)).astype(np.int8)
    q = (127 * np.sin(2 * np.pi * 10 * t / n)).astype(np.int8)
    interleaved = np.empty(n * 2, dtype=np.int8)
    interleaved[0::2] = i
    interleaved[1::2] = q
    samples = iq_bytes_to_complex(interleaved.tobytes(), num_samples=n)
    assert samples.shape == (n,)
    assert np.max(np.abs(samples)) <= 1.1


def test_spectrum_frame_from_iq_has_bins():
    params = SpectrumParams(
        center_freq_hz=100e6,
        sample_rate_hz=2e6,
        fft_size=512,
        capture_mode="iq",
    )
    params.sync_iq_display()
    n = params.fft_size
    noise = np.random.randint(-30, 30, size=n * 2, dtype=np.int8)
    frame = spectrum_frame_from_iq_bytes(noise.tobytes(), params)
    assert len(frame.power_db) == n
    assert len(frame.freqs_hz) == n
    assert abs(frame.span_hz - params.sample_rate_hz) < 1.0


def test_compute_spectrum_peak_near_center():
    params = SpectrumParams(
        center_freq_hz=100e6,
        sample_rate_hz=1e6,
        fft_size=1024,
        capture_mode="iq",
    )
    params.sync_iq_display()
    n = params.fft_size
    sample_rate = params.sample_rate_hz
    t = np.arange(n)
    tone = np.exp(2j * np.pi * 0.05 * t)  # offset bin
    frame = compute_spectrum_frame(tone.astype(np.complex64), params)
    peak_idx = int(np.argmax(frame.power_db))
    peak_freq = frame.freqs_hz[peak_idx]
    assert abs(peak_freq - params.center_freq_hz) < sample_rate * 0.1


def test_find_peak_excluding_dc_skips_lo():
    n = 256
    center = 100e6
    rate = 2e6
    freqs = np.linspace(center - rate / 2, center + rate / 2, n)
    power = np.full(n, -90.0)
    power[n // 2] = -15.0
    off_idx = n // 2 + 20
    power[off_idx] = -40.0
    peak = find_peak_excluding_dc(
        freqs,
        power,
        center_freq_hz=center,
        sample_rate_hz=rate,
    )
    assert peak is not None
    assert abs(peak[0] - freqs[off_idx]) < rate / n * 2
