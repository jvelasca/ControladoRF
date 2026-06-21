"""FFT IQ greenfield — sin SpectrumParams."""
from __future__ import annotations

import time

import numpy as np

from core.monitor.hackrf_rx_gains import calibrate_hackrf_antenna_power_db
from core.monitor.iq_fft import (
    HANNING_PEAK_CORRECTION_DB,
    apply_display_band_edge_guard,
    apply_display_dc_notch,
    iq_bytes_to_complex,
)
from core.rf.types import (
    AcquisitionMode,
    FrameMetadata,
    RxGainConfig,
    SpectrumFrame,
)

__all__ = [
    "compute_iq_spectrum_frame",
    "iq_bytes_to_complex",
    "nominal_rx_gain_db",
]


def nominal_rx_gain_db(rx_gain: RxGainConfig) -> float:
    from core.monitor.hackrf_rx_gains import snap_gains

    g = snap_gains(rx_gain.lna_db, rx_gain.vga_db, rx_gain.rf_amp_enable)
    return float(g.nominal_gain_db())


def compute_iq_spectrum_frame(
    samples: np.ndarray,
    *,
    center_freq_hz: float,
    sample_rate_hz: float,
    rx_gain: RxGainConfig,
    device_id: str = "hackrf",
    rbw_hz: float | None = None,
) -> SpectrumFrame:
    """Calcula trazo de potencia (dB) centrado en center_freq_hz."""
    n = len(samples)
    if n < 16:
        raise ValueError("Muestras IQ insuficientes para FFT")

    window = np.hanning(n)
    spectrum = np.fft.fftshift(np.fft.fft(samples * window))
    power = 20.0 * np.log10(np.abs(spectrum) + 1e-12)
    power = power - 20.0 * np.log10(max(n, 1))
    power = power + HANNING_PEAK_CORRECTION_DB
    power = calibrate_hackrf_antenna_power_db(
        power,
        lna_gain_db=int(rx_gain.lna_db),
        vga_gain_db=int(rx_gain.vga_db),
        rf_amp_enable=bool(rx_gain.rf_amp_enable),
    )

    sample_rate = float(sample_rate_hz)
    power = apply_display_dc_notch(
        power,
        center_freq_hz=center_freq_hz,
        sample_rate_hz=sample_rate,
    )
    power = apply_display_band_edge_guard(power)
    freqs = np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / sample_rate)) + center_freq_hz
    effective_rbw = rbw_hz if rbw_hz is not None else sample_rate / max(n, 1)

    meta = FrameMetadata(
        acquisition_mode=AcquisitionMode.IQ_STREAM,
        device_id=device_id,
        rbw_hz=float(effective_rbw),
        timestamp=time.monotonic(),
        acquisition_reason="iq_fft",
    )
    return SpectrumFrame(
        freqs_hz=np.asarray(freqs, dtype=np.float64),
        power_db=np.asarray(power, dtype=np.float64),
        metadata=meta,
    )
