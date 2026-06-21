"""Mapeo frecuencia ↔ columnas del trazo y del espectrograma (espectro alineado)."""
from __future__ import annotations

import numpy as np

from core.monitor.spectrum_params import SpectrumParams


def frame_freq_bounds(freqs_hz: np.ndarray | None) -> tuple[float, float] | None:
    """Límites reales del vector FFT (Hz), o None si no hay datos."""
    if freqs_hz is None:
        return None
    freqs = np.asarray(freqs_hz, dtype=float).reshape(-1)
    if freqs.size < 2:
        return None
    if freqs[0] < freqs[-1]:
        return float(freqs[0]), float(freqs[-1])
    return float(freqs[-1]), float(freqs[0])


def plot_freq_bounds(
    params: SpectrumParams,
    freqs_hz: np.ndarray | None,
) -> tuple[float, float]:
    """Rango de frecuencias visible en espectro y waterfall."""
    if params.uses_start_stop_window() and params.capture_mode == "sweep":
        start = float(params.freq_start_hz())
        stop = float(params.freq_stop_hz())
        if stop > start:
            return start, stop
    bounds = frame_freq_bounds(freqs_hz)
    if bounds is not None:
        return bounds
    if params.capture_mode == "iq":
        start = float(params.center_freq_hz) - float(params.sample_rate_hz) / 2.0
        stop = float(params.center_freq_hz) + float(params.sample_rate_hz) / 2.0
        if stop > start:
            return start, stop
    start = float(params.freq_start_hz())
    stop = float(params.freq_stop_hz())
    if stop <= start:
        stop = start + max(1.0, float(params.sample_rate_hz or params.span_hz or 1.0))
    return start, stop


def resample_power_to_grid(
    freqs_hz: np.ndarray,
    power_db: np.ndarray,
    *,
    start_hz: float,
    stop_hz: float,
    num_columns: int,
) -> np.ndarray:
    """Interpola potencia (dBm) a una rejilla uniforme en frecuencia."""
    if num_columns < 2:
        return np.array([], dtype=np.float32)
    freqs = np.asarray(freqs_hz, dtype=float).reshape(-1)
    power = np.asarray(power_db, dtype=float).reshape(-1)
    if freqs.size == 0 or power.size == 0:
        return np.zeros(num_columns, dtype=np.float32)
    n = min(freqs.size, power.size)
    freqs = freqs[:n]
    power = power[:n]
    order = np.argsort(freqs)
    freqs = freqs[order]
    power = power[order]
    uniq_freqs, uniq_idx = np.unique(freqs, return_index=True)
    uniq_power = power[uniq_idx]
    if uniq_freqs.size < 2:
        return np.full(num_columns, float(uniq_power[0]), dtype=np.float32)

    data_start = float(uniq_freqs[0])
    data_stop = float(uniq_freqs[-1])
    plot_start = float(start_hz)
    plot_stop = float(stop_hz)
    if plot_stop <= plot_start:
        plot_start = data_start
        plot_stop = data_stop

    grid = np.linspace(plot_start, plot_stop, num_columns, dtype=float)
    floor = float(np.percentile(uniq_power, 5))
    out = np.interp(grid, uniq_freqs, uniq_power, left=floor, right=floor)
    return out.astype(np.float32)


def resample_frame_to_plot(
    freqs_hz: np.ndarray,
    power_db: np.ndarray,
    params: SpectrumParams,
    *,
    num_columns: int | None = None,
) -> tuple[np.ndarray, float, float]:
    """Devuelve potencia remuestreada y límites [start, stop] del eje."""
    start, stop = plot_freq_bounds(params, freqs_hz)
    width = int(num_columns) if num_columns is not None else max(2, len(power_db))
    grid_power = resample_power_to_grid(
        freqs_hz,
        power_db,
        start_hz=start,
        stop_hz=stop,
        num_columns=width,
    )
    return grid_power, start, stop
