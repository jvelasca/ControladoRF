"""Formato compacto para la franja de estado del espectro."""
from __future__ import annotations


def format_freq_compact(freq_hz: float) -> str:
    """Frecuencia con 3 decimales en la unidad adecuada."""
    if abs(freq_hz) >= 1_000_000_000:
        return f"{freq_hz / 1_000_000_000:.3f} GHz"
    if abs(freq_hz) >= 1_000_000:
        return f"{freq_hz / 1_000_000:.3f} MHz"
    if abs(freq_hz) >= 1_000:
        return f"{freq_hz / 1_000:.3f} kHz"
    return f"{freq_hz:.3f} Hz"


def format_step_compact(step_hz: float) -> str:
    if step_hz >= 1_000_000.0:
        return f"{step_hz / 1_000_000.0:.3f} MHz"
    if step_hz >= 1_000.0:
        return f"{step_hz / 1_000.0:.3f} kHz"
    return f"{step_hz:.3f} Hz"
