"""Ancho de banda de supervisión por tipo de dispositivo (propiedades de inventario)."""
from __future__ import annotations

from typing import Any, Dict

from core.inventory_catalog import (
    DEVICE_TYPE_ANTENNA,
    DEVICE_TYPE_CHARGER,
    DEVICE_TYPE_IEM,
    DEVICE_TYPE_INTERCOM,
    DEVICE_TYPE_MICROPHONE,
    DEVICE_TYPE_OTHER,
    DEVICE_TYPE_SPECTRUM,
    resolve_device_type,
)

# Ancho total del canal de medición (no RBW del analizador).
DEFAULT_BANDWIDTH_HZ: Dict[str, float] = {
    DEVICE_TYPE_MICROPHONE: 200_000.0,
    DEVICE_TYPE_IEM: 200_000.0,
    DEVICE_TYPE_SPECTRUM: 500_000.0,
    DEVICE_TYPE_INTERCOM: 125_000.0,
    DEVICE_TYPE_ANTENNA: 100_000.0,
    DEVICE_TYPE_CHARGER: 50_000.0,
    DEVICE_TYPE_OTHER: 200_000.0,
}

# Ajuste opcional por banda UHF/L (heurística Workbench).
_BAND_MULTIPLIER: Dict[str, float] = {
    "G10": 0.85,
    "G50": 1.0,
    "H50": 1.0,
    "J50": 1.0,
    "K51": 1.0,
    "L50": 1.05,
    "M50": 1.05,
    "Q1": 0.9,
    "R1": 0.9,
    "VHF": 0.75,
}


def default_bandwidth_hz_for_equipo(equipo: Dict[str, Any]) -> float:
    """BW por defecto según ``device_type`` y, si existe, ``band`` del inventario."""
    device_type = resolve_device_type(equipo)
    base = DEFAULT_BANDWIDTH_HZ.get(device_type, DEFAULT_BANDWIDTH_HZ[DEVICE_TYPE_OTHER])
    band = str(equipo.get("band") or "").strip().upper()
    if not band:
        return base
    for prefix, mult in _BAND_MULTIPLIER.items():
        if band.startswith(prefix):
            return max(10_000.0, base * mult)
    return base
