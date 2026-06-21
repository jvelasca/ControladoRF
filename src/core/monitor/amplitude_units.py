"""Conversión de amplitud FFT (dBm interno) a unidades de pantalla."""
from __future__ import annotations

import math
from typing import Tuple

AMPLITUDE_UNITS = ("dBm", "dBmV", "dBuV", "V", "W")

# R = 50 Ω (referencia habitual en analizadores RF)
_IMPEDANCE_OHM = 50.0


def dbm_to_display(dbm: float, unit: str, *, ref_offset_db: float = 0.0) -> float:
    """Convierte dBm interno a valor de eje Y en la unidad seleccionada."""
    dbm = float(dbm) + float(ref_offset_db)
    normalized = (unit or "dBm").strip()
    if normalized == "dBm":
        return dbm
    if normalized == "dBmV":
        return dbm + 47.0
    if normalized == "dBuV":
        return dbm + 107.0
    if normalized == "V":
        vrms = math.sqrt(10 ** (dbm / 10.0) * 1e-3 * _IMPEDANCE_OHM)
        return 20.0 * math.log10(max(vrms, 1e-15))
    if normalized == "W":
        watts = 10 ** ((dbm - 30.0) / 10.0)
        return 10.0 * math.log10(max(watts, 1e-18))
    return dbm


def display_to_dbm(display: float, unit: str, *, ref_offset_db: float = 0.0) -> float:
    """Inversa aproximada para ajustar nivel de referencia desde el slider."""
    normalized = (unit or "dBm").strip()
    if normalized == "dBm":
        return float(display) - ref_offset_db
    if normalized == "dBmV":
        return float(display) - 47.0 - ref_offset_db
    if normalized == "dBuV":
        return float(display) - 107.0 - ref_offset_db
    if normalized == "V":
        vrms = 10 ** (float(display) / 20.0)
        dbm = 10.0 * math.log10(max(vrms * vrms / _IMPEDANCE_OHM, 1e-18)) + 30.0
        return dbm - ref_offset_db
    if normalized == "W":
        watts = 10 ** (float(display) / 10.0)
        dbm = 10.0 * math.log10(max(watts, 1e-18)) + 30.0
        return dbm - ref_offset_db
    return float(display) - ref_offset_db


def format_amplitude_value(display: float, unit: str) -> str:
    """Texto compacto para rejilla y cursor."""
    normalized = (unit or "dBm").strip()
    if normalized in ("dBm", "dBmV", "dBuV"):
        return f"{display:.0f}"
    if normalized == "V":
        vrms = 10 ** (display / 20.0)
        if vrms >= 1.0:
            return f"{vrms:.2f}"
        if vrms >= 1e-3:
            return f"{vrms * 1e3:.1f}m"
        return f"{vrms * 1e6:.0f}µ"
    if normalized == "W":
        watts = 10 ** (display / 10.0)
        if watts >= 1.0:
            return f"{watts:.2f}"
        if watts >= 1e-3:
            return f"{watts * 1e3:.1f}m"
        return f"{watts * 1e6:.1f}µ"
    return f"{display:.0f}"


def amplitude_axis_label(unit: str) -> str:
    normalized = (unit or "dBm").strip()
    if normalized == "dBmV":
        return "dBmV"
    if normalized == "dBuV":
        return "dBµV"
    return normalized


def ref_level_display_range(unit: str) -> Tuple[float, float]:
    """Rango del slider AMPT en unidades de pantalla (log)."""
    top = dbm_to_display(30.0, unit)
    bottom = dbm_to_display(-120.0, unit)
    if top < bottom:
        top, bottom = bottom, top
    return bottom, top
