"""Formateo de lecturas del analizador (toolbar LCD)."""
from __future__ import annotations

import re
from typing import Literal


def parse_locale_float(text: str) -> float:
    """Interpreta 90.9 y 90,9 (y variantes con separadores de miles)."""
    raw = text.strip()
    if not raw:
        raise ValueError("empty")
    cleaned = re.sub(r"[^\d,.\-+eE]", "", raw)
    if not cleaned or cleaned in ("-", "+", ".", ",", "-.", "+."):
        raise ValueError("invalid")
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    return float(cleaned)

TraceMode = Literal["clear_write", "max_hold", "min_hold", "average"]
DetectorMode = Literal["peak", "rms", "sample", "neg_peak", "average"]


def format_freq_short(freq_hz: float) -> str:
    abs_hz = abs(freq_hz)
    if abs_hz >= 1_000_000_000:
        return f"{freq_hz / 1_000_000_000:.3f} GHz"
    if abs_hz >= 1_000_000:
        return f"{freq_hz / 1_000_000:.3f} MHz"
    if abs_hz >= 1_000:
        return f"{freq_hz / 1_000:.1f} kHz"
    return f"{freq_hz:.0f} Hz"


def format_bw_hz(bw_hz: float) -> str:
    if bw_hz >= 1_000_000:
        return f"{bw_hz / 1_000_000:.2f} MHz"
    if bw_hz >= 1_000:
        return f"{bw_hz / 1_000:.1f} kHz"
    return f"{bw_hz:.0f} Hz"


def format_sweep_ms(ms: float) -> str:
    if ms >= 1000.0:
        return f"{ms / 1000.0:.2f} s"
    if ms >= 1.0:
        return f"{ms:.0f} ms"
    return f"{ms * 1000.0:.0f} µs"


def format_ref_level(value_dbm: float, unit: str = "dBm") -> str:
    return f"{value_dbm:.1f} {unit}"


def format_attenuation_db(value_db: float) -> str:
    return f"{value_db:.0f} dB"


def format_db_per_div(ref_range_db: float, divisions: int) -> str:
    div = max(divisions, 1)
    return f"{ref_range_db / div:.0f} dB/div"


def format_freq_per_div(span_hz: float, divisions: int) -> str:
    div = max(divisions, 1)
    return format_freq_short(span_hz / div) + "/div"


def trace_mode_label(mode: str) -> str:
    labels = {
        "clear_write": "Clear/Write",
        "max_hold": "Max Hold",
        "min_hold": "Min Hold",
        "average": "Average",
    }
    return labels.get(mode, mode)


def detector_label(mode: str) -> str:
    labels = {
        "peak": "Peak",
        "rms": "RMS",
        "sample": "Sample",
        "neg_peak": "Neg Peak",
        "average": "Average",
    }
    return labels.get(mode, mode.upper())
