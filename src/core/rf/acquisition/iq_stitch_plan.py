"""Politica lapso vs BW instantaneo HackRF.

SPAN > BW instantaneo → ``hackrf_sweep`` (lapso ancho correcto, modo interleaved GSG).
Helpers de stitch IQ quedan solo para tests / referencia (no usados en runtime).
"""
from __future__ import annotations

import math

# Margen coherente con ``HackRfDevice.capture_iq_spectrum`` (Hz).
SWEEP_SPAN_MARGIN_HZ = 50_000.0

# Solape entre ventanas IQ consecutivas (legacy / tests).
STITCH_OVERLAP_FRAC = 0.15
MAX_STITCH_CAPTURES = 4


def span_exceeds_instant_bw(
    span_hz: float,
    instant_bw_hz: float,
    *,
    margin_hz: float = SWEEP_SPAN_MARGIN_HZ,
) -> bool:
    """True si el lapso pedido supera el BW instantaneo del SDR."""
    span = max(float(span_hz), 0.0)
    instant = max(float(instant_bw_hz), 1.0)
    return span > instant + max(0.0, float(margin_hz))


def prefers_hackrf_sweep(
    span_hz: float,
    instant_bw_hz: float,
    *,
    max_captures: int = MAX_STITCH_CAPTURES,
) -> bool:
    """True → usar hackrf_sweep (lapso ancho correcto)."""
    del max_captures  # politica fija: barrido en cuanto SPAN > BW instantaneo
    return span_exceeds_instant_bw(span_hz, instant_bw_hz)


def stitch_capture_count(span_hz: float, instant_bw_hz: float) -> int:
    """Capturas IQ necesarias para cubrir ``span_hz`` con ventanas de ``instant_bw_hz``."""
    span = max(float(span_hz), 1.0)
    instant = max(float(instant_bw_hz), 1.0)
    if span <= instant + 50_000.0:
        return 1
    overlap = instant * STITCH_OVERLAP_FRAC
    step = max(1.0, instant - overlap)
    extra = span - instant
    return max(2, int(math.ceil(extra / step)) + 1)


def stitch_center_freqs(
    center_hz: float,
    span_hz: float,
    instant_hz: float,
    *,
    max_captures: int = MAX_STITCH_CAPTURES,
) -> list[float]:
    """Centros de sintonizacion para cubrir [FC-SPAN/2, FC+SPAN/2]."""
    span = max(float(span_hz), 1.0)
    instant = max(float(instant_hz), 1.0)
    center = float(center_hz)
    if span <= instant + 50_000.0:
        return [center]

    start_hz = center - span / 2.0
    stop_hz = center + span / 2.0
    overlap = instant * STITCH_OVERLAP_FRAC
    step = max(1.0, instant - overlap)
    half = instant / 2.0

    centers: list[float] = []
    pos = start_hz + half
    while len(centers) < max(1, int(max_captures)):
        centers.append(pos)
        if pos + half >= stop_hz - 1.0:
            break
        pos += step

    if not centers:
        return [center]

    if centers[-1] + half < stop_hz - 1.0 and len(centers) < max_captures:
        centers.append(stop_hz - half)
    elif centers[-1] + half < stop_hz - 1.0:
        centers[-1] = stop_hz - half

    return centers
