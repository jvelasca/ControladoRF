"""Rejilla de pantalla y presets AUTO del analizador (801 pts, RBW barrido)."""
from __future__ import annotations

import math
from typing import Optional

from core.monitor.spectrum_params import SpectrumParams

ANALYZER_AUTO_POINTS = 801
SWEEP_RBW_MIN_HZ = 100_000.0
SWEEP_RBW_MAX_HZ = 5_000_000.0
# Por encima de este lapso, RBW más grueso → menos segmentos hackrf_sweep (panorámica fluida).
WIDE_SPAN_COARSE_THRESHOLD_HZ = 50_000_000.0
FAST_SWEEP_TARGET_BINS = 280
VERY_WIDE_SPAN_THRESHOLD_HZ = 120_000_000.0
VERY_WIDE_SWEEP_TARGET_BINS = 200

RBW_PRESETS_HZ = (
    100.0,
    300.0,
    1_000.0,
    3_000.0,
    10_000.0,
    30_000.0,
    100_000.0,
    300_000.0,
    1_000_000.0,
)

RBW_STABILITY_RATIO = 0.12


def snap_fft_size(n: int, *, min_size: int = 256) -> int:
    size = max(min_size, min(8192, int(n)))
    power = 1 << int(round(math.log2(max(size, min_size))))
    return max(min_size, min(8192, power))


def clamp_sweep_rbw_hz(rbw_hz: float) -> float:
    return max(SWEEP_RBW_MIN_HZ, min(SWEEP_RBW_MAX_HZ, float(rbw_hz)))


def sweep_rbw_presets_hz() -> tuple[float, ...]:
    return tuple(p for p in RBW_PRESETS_HZ if SWEEP_RBW_MIN_HZ <= p <= SWEEP_RBW_MAX_HZ)


def snap_sweep_rbw_to_preset(rbw_hz: float) -> float:
    clamped = clamp_sweep_rbw_hz(rbw_hz)
    presets = sweep_rbw_presets_hz()
    if not presets:
        return clamped
    nearest = min(presets, key=lambda preset: abs(preset - clamped))
    if clamped > 0 and abs(nearest - clamped) / clamped > 0.35:
        return clamped
    return nearest


def ideal_sweep_rbw_hz(span_hz: float) -> float:
    span = max(float(span_hz), 1.0)
    if span >= VERY_WIDE_SPAN_THRESHOLD_HZ:
        return clamp_sweep_rbw_hz(span / VERY_WIDE_SWEEP_TARGET_BINS)
    if span >= WIDE_SPAN_COARSE_THRESHOLD_HZ:
        return clamp_sweep_rbw_hz(span / FAST_SWEEP_TARGET_BINS)
    return clamp_sweep_rbw_hz(span / ANALYZER_AUTO_POINTS)


def pick_stable_sweep_rbw(span_hz: float, current_rbw_hz: Optional[float] = None) -> float:
    ideal = ideal_sweep_rbw_hz(span_hz)
    snapped = snap_sweep_rbw_to_preset(ideal)
    if current_rbw_hz is None or current_rbw_hz <= 0:
        return snapped
    current_snapped = snap_sweep_rbw_to_preset(current_rbw_hz)
    if current_snapped == snapped:
        return current_snapped
    if abs(ideal - current_rbw_hz) / current_rbw_hz < RBW_STABILITY_RATIO:
        return current_snapped
    return snapped


def display_trace_bins(params: SpectrumParams) -> int:
    """Puntos de la rejilla de traza en pantalla."""
    if params.capture_mode == "sweep":
        if bool(getattr(params, "fft_auto", True)):
            return ANALYZER_AUTO_POINTS
        return max(256, min(8192, int(params.fft_size)))
    return max(int(params.fft_size), 256)


def pick_auto_fft_size(params: SpectrumParams) -> int:
    if bool(getattr(params, "iq_trace_sharp", False)) and params.capture_mode == "iq":
        sr = max(float(params.sample_rate_hz or 0.0), float(params.display_span_hz() or 0.0))
        if sr >= 10_000_000.0:
            return 2048
        if sr >= 4_000_000.0:
            return 1024
    return snap_fft_size(ANALYZER_AUTO_POINTS, min_size=256)


def auto_sweep_time_ms_for_span(span_hz: float, rbw_hz: float) -> float:
    span = max(float(span_hz), 1.0)
    rbw = max(float(rbw_hz), SWEEP_RBW_MIN_HZ)
    bins = span / rbw
    ms = bins * 1.5 + 35.0
    if span <= 30_000_000.0:
        return max(40.0, min(120.0, ms))
    return max(40.0, min(30_000.0, ms))
