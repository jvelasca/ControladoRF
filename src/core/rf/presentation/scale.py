"""Escala vertical AUTO — sin PyQt."""
from __future__ import annotations

import numpy as np

from core.monitor.iq_fft import interior_power_db
from core.rf.types import DisplayConfig, SpectrumDisplayFrame, SpectrumFrame

REF_RANGE_STEPS_DB = (40.0, 50.0, 60.0, 80.0, 100.0, 120.0)


def stabilize_ref_range_db(
    target_range_db: float,
    prev_range_db: float | None,
) -> float:
    """Elige el escalón de rango vertical con histéresis para reducir parpadeo."""
    target_step = min(REF_RANGE_STEPS_DB, key=lambda r: abs(r - target_range_db))
    if prev_range_db is None:
        return target_step
    prev_step = min(REF_RANGE_STEPS_DB, key=lambda r: abs(r - prev_range_db))
    if target_step == prev_step:
        return prev_step
    lo, hi = sorted((prev_step, target_step))
    midpoint = (lo + hi) / 2.0
    if target_step > prev_step:
        return target_step if target_range_db >= midpoint else prev_step
    return target_step if target_range_db <= midpoint else prev_step


def stabilize_ref_level_dbm(
    target_ref_dbm: float,
    prev_ref_dbm: float | None,
    *,
    deadband_db: float = 2.0,
) -> float:
    """Suaviza el nivel de referencia AUTO para evitar micro-saltos verticales."""
    if prev_ref_dbm is None:
        return float(target_ref_dbm)
    delta = float(target_ref_dbm) - float(prev_ref_dbm)
    if abs(delta) <= deadband_db:
        return float(prev_ref_dbm)
    return float(prev_ref_dbm) + delta * 0.35


def apply_display_scale(frame: SpectrumFrame, config: DisplayConfig) -> SpectrumDisplayFrame:
    if not config.ref_auto:
        return SpectrumDisplayFrame(
            frame=frame,
            ref_level_dbm=config.ref_level_dbm,
            ref_range_db=config.ref_range_db,
        )
    power = np.asarray(frame.power_db, dtype=float)
    if power.size == 0:
        return SpectrumDisplayFrame(
            frame=frame,
            ref_level_dbm=config.ref_level_dbm,
            ref_range_db=config.ref_range_db,
        )
    interior = interior_power_db(power)
    peak = float(np.max(interior)) if interior.size else float(np.max(power))
    pct = 15 if power.size >= 512 else 10
    floor = float(np.percentile(interior if interior.size else power, pct))
    dynamic = max(peak - floor, 12.0)
    target_range = dynamic * 1.08 + 14.0
    range_db = stabilize_ref_range_db(
        min(REF_RANGE_STEPS_DB, key=lambda r: abs(r - target_range)),
        None,
    )
    db_per_div = range_db / 10.0
    ref = peak + db_per_div * 0.65
    return SpectrumDisplayFrame(frame=frame, ref_level_dbm=ref, ref_range_db=range_db)
