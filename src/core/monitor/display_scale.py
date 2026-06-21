"""Utilidades de escala y pasos para controles del Monitor."""
from __future__ import annotations

import numpy as np

from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams

SPAN_STEPS_HZ = (
    100_000.0,
    250_000.0,
    500_000.0,
    1_000_000.0,
    2_000_000.0,
    2_500_000.0,
    3_500_000.0,
    5_000_000.0,
    7_000_000.0,
    10_000_000.0,
    14_000_000.0,
    20_000_000.0,
    21_000_000.0,
    25_000_000.0,
    30_000_000.0,
    31_000_000.0,
    35_000_000.0,
    40_000_000.0,
    50_000_000.0,
    60_000_000.0,
    80_000_000.0,
)

REF_RANGE_STEPS_DB = (40.0, 50.0, 60.0, 80.0, 100.0, 120.0)

LNA_GAIN_STEPS_DB = (0, 8, 16, 24, 32, 40)

VGA_GAIN_MIN_DB = 0
VGA_GAIN_MAX_DB = 62
VGA_GAIN_STEP_DB = 2
VGA_GAIN_STEP_COUNT = VGA_GAIN_MAX_DB // VGA_GAIN_STEP_DB + 1

REF_SCALE_PRESETS = (
    (100.0, 10.0),
    (80.0, 8.0),
    (60.0, 6.0),
    (50.0, 5.0),
    (40.0, 4.0),
    (20.0, 2.0),
)

FREQ_SLIDER_MIN_HZ = 1_000_000.0
FREQ_SLIDER_MAX_HZ = 6_000_000_000.0
SPAN_SLIDER_MIN_HZ = 100_000.0


def snap_iq_sample_rate_hz(rate_hz: float) -> float:
    """Sample rate IQ válido para HackRF (2–20 MHz, rejilla 0,5 MHz)."""
    rate = max(SPAN_STEPS_HZ[0], min(SPAN_STEPS_HZ[-1], float(rate_hz)))
    snapped = round(rate / 500_000.0) * 500_000.0
    return max(SPAN_STEPS_HZ[0], min(SPAN_STEPS_HZ[-1], snapped))


def center_freq_step_hz(center_hz: float) -> float:
    if center_hz >= 900_000_000:
        return 1_000_000.0
    if center_hz >= 100_000_000:
        return 100_000.0
    if center_hz >= 10_000_000:
        return 10_000.0
    if center_hz >= 1_000_000:
        return 1_000.0
    return 100.0


def step_span_hz(current_hz: float, direction: int) -> float:
    steps = SPAN_STEPS_HZ
    if current_hz <= steps[0]:
        idx = 0
    elif current_hz >= steps[-1]:
        idx = len(steps) - 1
    else:
        idx = min(range(len(steps)), key=lambda i: abs(steps[i] - current_hz))
    idx = max(0, min(len(steps) - 1, idx + direction))
    return steps[idx]


def step_ref_range_db(current_db: float, direction: int) -> float:
    steps = REF_RANGE_STEPS_DB
    idx = min(range(len(steps)), key=lambda i: abs(steps[i] - current_db))
    idx = max(0, min(len(steps) - 1, idx + direction))
    return steps[idx]


def _log_ratio(value: float, vmin: float, vmax: float) -> float:
    import math

    value = max(vmin, min(vmax, value))
    if vmax <= vmin:
        return 0.0
    return (math.log10(value) - math.log10(vmin)) / (math.log10(vmax) - math.log10(vmin))


def _log_interp(ratio: float, vmin: float, vmax: float) -> float:
    import math

    ratio = max(0.0, min(1.0, ratio))
    return vmin * ((vmax / vmin) ** ratio)


def freq_to_slider_value(freq_hz: float) -> int:
    ratio = _log_ratio(freq_hz, FREQ_SLIDER_MIN_HZ, FREQ_SLIDER_MAX_HZ)
    return int(round(ratio * 10_000))


def slider_value_to_freq(value: int) -> float:
    ratio = max(0, min(10_000, int(value))) / 10_000.0
    return _log_interp(ratio, FREQ_SLIDER_MIN_HZ, FREQ_SLIDER_MAX_HZ)


def span_to_slider_value(
    span_hz: float,
    *,
    max_span_hz: float,
    min_span_hz: float = SPAN_SLIDER_MIN_HZ,
) -> int:
    min_hz = max(SPAN_SLIDER_MIN_HZ, float(min_span_hz))
    max_hz = max(min_hz, float(max_span_hz))
    ratio = _log_ratio(max(min_hz, span_hz), min_hz, max_hz)
    return int(round(ratio * 10_000))


def slider_value_to_span(
    value: int,
    *,
    max_span_hz: float,
    min_span_hz: float = SPAN_SLIDER_MIN_HZ,
) -> float:
    min_hz = max(SPAN_SLIDER_MIN_HZ, float(min_span_hz))
    max_hz = max(min_hz, float(max_span_hz))
    ratio = max(0, min(10_000, int(value))) / 10_000.0
    return _log_interp(ratio, min_hz, max_hz)


def freq_in_span_to_slider(freq_hz: float, start_hz: float, stop_hz: float) -> int:
    span = float(stop_hz) - float(start_hz)
    if span <= 0.0:
        return 5000
    ratio = (float(freq_hz) - float(start_hz)) / span
    return int(round(max(0.0, min(1.0, ratio)) * 10_000))


def slider_to_freq_in_span(value: int, start_hz: float, stop_hz: float) -> float:
    span = float(stop_hz) - float(start_hz)
    if span <= 0.0:
        return float(start_hz)
    ratio = max(0, min(10_000, int(value))) / 10_000.0
    return float(start_hz) + ratio * span


def snap_lna_gain_db(value: int) -> int:
    from core.monitor.hackrf_rx_gains import snap_lna_db

    return snap_lna_db(value)


def snap_vga_gain_db(value: int) -> int:
    from core.monitor.hackrf_rx_gains import snap_vga_db

    return snap_vga_db(value)


def apply_auto_vertical_scale(
    frame: SpectrumFrame,
    params: SpectrumParams,
    *,
    force: bool = False,
) -> SpectrumFrame:
    """Ajusta ref/rango vertical para que el trazo quepa en pantalla (modo AUTO)."""
    if not force and not params.ref_scale_auto:
        return frame
    power = np.asarray(frame.power_db, dtype=float)
    if power.size == 0:
        return frame

    from core.monitor.iq_fft import interior_power_db

    interior = interior_power_db(power)
    peak = float(np.max(interior)) if interior.size else float(np.max(power))
    floor = float(np.percentile(interior if interior.size else power, 5))
    dynamic = max(peak - floor, 12.0)

    target_range = dynamic * 1.25 + 12.0
    range_db = min(REF_RANGE_STEPS_DB, key=lambda r: abs(r - target_range))
    divs = max(params.vertical_divisions, 10)
    db_per_div = range_db / divs
    ref = peak + db_per_div * 1.2

    return SpectrumFrame(
        freqs_hz=frame.freqs_hz,
        power_db=frame.power_db,
        center_freq_hz=frame.center_freq_hz,
        span_hz=frame.span_hz,
        ref_level_dbm=ref,
        ref_range_db=range_db,
    )


def level_to_normalized_y(level: float, top: float, bottom: float) -> float:
    """Posición 0..1 en el eje vertical (0 = arriba)."""
    span = max(top - bottom, 1.0)
    return max(0.0, min(1.0, (top - level) / span))


def ref_range_to_slider_value(ref_range_db: float) -> int:
    return ref_range_step_index(ref_range_db)


def slider_value_to_ref_range(value: int) -> float:
    return ref_range_from_step_index(value)


def ref_range_step_index(ref_range_db: float) -> int:
    return min(range(len(REF_RANGE_STEPS_DB)), key=lambda i: abs(REF_RANGE_STEPS_DB[i] - float(ref_range_db)))


def ref_range_from_step_index(index: int) -> float:
    idx = max(0, min(len(REF_RANGE_STEPS_DB) - 1, int(index)))
    return REF_RANGE_STEPS_DB[idx]


def lna_step_index(lna_gain_db: int) -> int:
    snapped = snap_lna_gain_db(lna_gain_db)
    return LNA_GAIN_STEPS_DB.index(snapped)


def lna_gain_from_step_index(index: int) -> int:
    idx = max(0, min(len(LNA_GAIN_STEPS_DB) - 1, int(index)))
    return LNA_GAIN_STEPS_DB[idx]


def vga_step_index(vga_gain_db: int) -> int:
    return snap_vga_gain_db(vga_gain_db) // VGA_GAIN_STEP_DB


def vga_gain_from_step_index(index: int) -> int:
    idx = max(0, min(VGA_GAIN_STEP_COUNT - 1, int(index)))
    return idx * VGA_GAIN_STEP_DB
