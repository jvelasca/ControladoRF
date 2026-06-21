"""Mapa de color y niveles del espectrograma (estilo SDR++/analizador)."""
from __future__ import annotations

import numpy as np

WATERFALL_DB_FLOOR = -140.0
WATERFALL_DB_CEIL = 50.0
WATERFALL_COLORMAPS = ("jet", "greyscale", "rainbow", "heat")
HISTORY_AUTO_MARGIN_DB = 3.0


def clamp_waterfall_db(value: float) -> float:
    return max(WATERFALL_DB_FLOOR, min(WATERFALL_DB_CEIL, float(value)))


def db_to_slider_value(db: float) -> int:
    low, high = WATERFALL_DB_FLOOR, WATERFALL_DB_CEIL
    ratio = (clamp_waterfall_db(db) - low) / max(high - low, 1.0)
    return int(round(max(0.0, min(1.0, ratio)) * 10_000))


def slider_value_to_db(value: int) -> float:
    low, high = WATERFALL_DB_FLOOR, WATERFALL_DB_CEIL
    ratio = max(0, min(10_000, int(value))) / 10_000.0
    return clamp_waterfall_db(low + ratio * (high - low))


def compute_history_levels(
    power_db: np.ndarray,
    *,
    margin_db: float = HISTORY_AUTO_MARGIN_DB,
) -> tuple[float, float]:
    """Min/Max a partir del historial visible (contraste AUTO)."""
    if power_db.size == 0:
        return -100.0, 0.0
    bottom = clamp_waterfall_db(float(np.min(power_db)) - margin_db)
    top = clamp_waterfall_db(float(np.max(power_db)) + margin_db)
    if bottom >= top:
        top = clamp_waterfall_db(bottom + 20.0)
    return bottom, top


def resolve_waterfall_levels(
    *,
    min_db: float,
    max_db: float,
    link_spectrum: bool,
    contrast_auto: bool,
    ref_level_dbm: float,
    ref_range_db: float,
    history_power_db: np.ndarray | None = None,
) -> tuple[float, float]:
    """Niveles efectivos Min/Max (dBm) para el colormap."""
    if link_spectrum:
        top = float(ref_level_dbm)
        bottom = top - max(float(ref_range_db), 20.0)
    elif contrast_auto and history_power_db is not None and history_power_db.size > 0:
        bottom, top = compute_history_levels(history_power_db)
    else:
        top = float(max_db)
        bottom = float(min_db)
    if bottom >= top:
        bottom = top - 20.0
    return bottom, top


def apply_colormap(t: np.ndarray, colormap: str) -> np.ndarray:
    """t normalizado 0..1 → RGB uint8."""
    t = np.clip(t, 0.0, 1.0)
    name = colormap if colormap in WATERFALL_COLORMAPS else "jet"

    if name == "greyscale":
        v = (t * 255.0).astype(np.uint8)
        return np.stack([v, v, v], axis=-1)

    if name == "rainbow":
        r = np.clip(255.0 * (0.5 + 0.5 * np.sin(2.0 * np.pi * (t - 0.25))), 0.0, 255.0)
        g = np.clip(255.0 * (0.5 + 0.5 * np.sin(2.0 * np.pi * t)), 0.0, 255.0)
        b = np.clip(255.0 * (0.5 + 0.5 * np.sin(2.0 * np.pi * (t + 0.25))), 0.0, 255.0)
        return np.stack([r, g, b], axis=-1).astype(np.uint8)

    if name == "heat":
        r = np.clip(255.0 * np.minimum(1.0, t * 1.35 + 0.1), 0.0, 255.0)
        g = np.clip(255.0 * np.maximum(0.0, (t - 0.25) * 1.5), 0.0, 255.0)
        b = np.clip(255.0 * np.maximum(0.0, (t - 0.55) * 2.2), 0.0, 255.0)
        return np.stack([r, g, b], axis=-1).astype(np.uint8)

    # jet (por defecto)
    r = np.clip(255.0 * np.minimum(1.0, np.maximum(0.0, 1.5 - np.abs(4.0 * t - 3.0))), 0.0, 255.0)
    g = np.clip(255.0 * np.minimum(1.0, np.maximum(0.0, 1.5 - np.abs(4.0 * t - 2.0))), 0.0, 255.0)
    b = np.clip(255.0 * np.minimum(1.0, np.maximum(0.0, 1.5 - np.abs(4.0 * t - 1.0))), 0.0, 255.0)
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


def power_db_to_rgb(
    power_db: np.ndarray,
    *,
    min_db: float,
    max_db: float,
    colormap: str = "jet",
) -> np.ndarray:
    """Convierte potencia (dBm) a RGB; señal fuerte cerca de max_db."""
    span = max(max_db - min_db, 1.0)
    t = np.clip((power_db - min_db) / span, 0.0, 1.0)
    return apply_colormap(t, colormap)
