"""FFT sobre muestras IQ (modo SDR nativo, estilo SDR++)."""
from __future__ import annotations

import numpy as np

from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams


# Compensación ventana Hanning (pico ≈ −6 dB vs rectangular; SDR++ usa magnitud normalizada).
HANNING_PEAK_CORRECTION_DB = 6.02
# Alineación aproximada con hackrf_sweep / GQRX (dBm en antena, no dBFS del ADC).
from core.monitor.hackrf_rx_gains import (
    HACKRF_ANTENNA_OFFSET_DB,
    calibrate_hackrf_antenna_power_db,
)

# Alias legacy (tests / docs).
HACKRF_IQ_ANTENNA_OFFSET_DB = HACKRF_ANTENNA_OFFSET_DB


def dc_exclude_hz(sample_rate_hz: float) -> float:
    """Ancho (Hz) alrededor de FC a ignorar (fuga LO / bin DC en FFT IQ)."""
    rate = max(float(sample_rate_hz), 1.0)
    return max(25_000.0, rate * 0.012)


def band_edge_exclude_hz(sample_rate_hz: float) -> float:
    """Ancho (Hz) a ignorar en cada borde del paso de banda (lobos FI/FF)."""
    rate = max(float(sample_rate_hz), 1.0)
    return max(75_000.0, rate * 0.035)


def band_edge_exclude_bins(n_bins: int) -> int:
    """Bins a ignorar en cada extremo del vector FFT."""
    n = max(0, int(n_bins))
    if n < 32:
        return 0
    return max(4, int(round(n * 0.035)))


def interior_power_db(power_db: np.ndarray) -> np.ndarray:
    """Recorte central sin bordes — para AUTO escala y picos."""
    power = np.asarray(power_db, dtype=float).reshape(-1)
    edge = band_edge_exclude_bins(power.size)
    if power.size < 32 or edge <= 0 or edge * 2 >= power.size:
        return power
    return power[edge:-edge]


def apply_display_band_edge_guard(power_db: np.ndarray) -> np.ndarray:
    """Atenúa picos espurios en FI/FF (bordes del paso de banda HackRF/FFT)."""
    power = np.asarray(power_db, dtype=float).copy()
    edge = band_edge_exclude_bins(power.size)
    if edge <= 0:
        return power
    interior = power[edge:-edge]
    if interior.size < 8:
        return power
    cap = float(np.percentile(interior, 92))
    for sl in (slice(0, edge), slice(-edge, None)):
        wing = power[sl]
        spike = wing > cap + 6.0
        if np.any(spike):
            wing = wing.copy()
            wing[spike] = cap
            power[sl] = wing
    return power


def find_peak_excluding_dc(
    freqs_hz: np.ndarray,
    power_db: np.ndarray,
    *,
    center_freq_hz: float,
    sample_rate_hz: float,
    search_center_hz: float | None = None,
    search_half_width_hz: float | None = None,
) -> tuple[float, float] | None:
    """Devuelve (freq_hz, power_db) del pico más alto fuera de la zona DC."""
    freqs = np.asarray(freqs_hz, dtype=float).reshape(-1)
    power = np.asarray(power_db, dtype=float).reshape(-1)
    n = min(freqs.size, power.size)
    if n < 4:
        return None
    freqs = freqs[:n]
    power = power[:n]
    dc = dc_exclude_hz(sample_rate_hz)
    edge = band_edge_exclude_hz(sample_rate_hz)
    half = float(sample_rate_hz) / 2.0
    band_start = float(center_freq_hz) - half
    band_stop = float(center_freq_hz) + half
    mask = np.abs(freqs - float(center_freq_hz)) > dc
    mask &= (freqs >= band_start + edge) & (freqs <= band_stop - edge)
    if search_center_hz is not None and search_half_width_hz is not None:
        half = max(float(search_half_width_hz), dc * 2.0)
        center = float(search_center_hz)
        mask &= (freqs >= center - half) & (freqs <= center + half)
    if not np.any(mask):
        return None
    sub_f = freqs[mask]
    sub_p = power[mask]
    idx = int(np.argmax(sub_p))
    return float(sub_f[idx]), float(sub_p[idx])


def apply_display_dc_notch(power_db: np.ndarray, *, center_freq_hz: float, sample_rate_hz: float) -> np.ndarray:
    """Atenúa solo un spur LO aislado en el bin central; conserva portadora FM real."""
    del center_freq_hz, sample_rate_hz
    power = np.asarray(power_db, dtype=float).copy()
    n = power.size
    if n < 16:
        return power
    center_bin = n // 2
    wing = 5
    left = power[max(0, center_bin - wing):center_bin]
    right = power[center_bin + 1:min(n, center_bin + wing + 1)]
    neighbors = np.concatenate([left, right]) if left.size and right.size else np.array([], dtype=float)
    if neighbors.size < 4:
        return power
    neighbor_med = float(np.median(neighbors))
    neighbor_max = float(np.max(neighbors))
    center_val = float(power[center_bin])
    # LO: pico muy aislado en DC; FM/WFM: vecinos elevados por sidebands.
    isolated_lo = (
        center_val > neighbor_max + 12.0
        and (neighbor_max - neighbor_med) < 8.0
        and center_val > neighbor_med + 18.0
    )
    if isolated_lo:
        power[center_bin] = neighbor_med
    return power


def iq_bytes_to_complex(iq_bytes: bytes, *, num_samples: int) -> np.ndarray:
    """Convierte bytes intercalados int8 I/Q a complex64 normalizado."""
    need = num_samples * 2
    if len(iq_bytes) < need:
        raise ValueError(f"IQ insuficiente: {len(iq_bytes)} < {need} bytes")
    raw = np.frombuffer(iq_bytes[:need], dtype=np.int8).astype(np.float32)
    pairs = raw.reshape(-1, 2)
    return (pairs[:, 0] + 1j * pairs[:, 1]) / 128.0


def compute_spectrum_frame(
    samples: np.ndarray,
    params: SpectrumParams,
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
    if params.capture_mode == "iq":
        power = calibrate_hackrf_antenna_power_db(
            power,
            lna_gain_db=int(params.lna_gain_db),
            vga_gain_db=int(params.vga_gain_db),
            rf_amp_enable=bool(params.rf_amp_enable),
        )
    else:
        from core.monitor.hackrf_rx_gains import gains_from_params

        power = power - gains_from_params(params).nominal_gain_db()
    sample_rate = params.sample_rate_hz
    power = apply_display_dc_notch(
        power,
        center_freq_hz=params.center_freq_hz,
        sample_rate_hz=sample_rate,
    )
    power = apply_display_band_edge_guard(power)
    freqs = np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / sample_rate)) + params.center_freq_hz
    span = sample_rate

    return SpectrumFrame(
        freqs_hz=freqs,
        power_db=power,
        center_freq_hz=params.center_freq_hz,
        span_hz=span,
        ref_level_dbm=params.ref_level_dbm,
        ref_range_db=params.ref_range_db,
    )


def spectrum_frame_from_iq_bytes(iq_bytes: bytes, params: SpectrumParams) -> SpectrumFrame:
    """Pipeline completo: bytes IQ → SpectrumFrame."""
    n = max(256, params.fft_size)
    samples = iq_bytes_to_complex(iq_bytes, num_samples=n)
    return compute_spectrum_frame(samples, params)
