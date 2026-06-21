"""Escala vertical AUTO — sin PyQt."""
from __future__ import annotations

import numpy as np

from core.monitor.iq_fft import interior_power_db
from core.rf.types import DisplayConfig, SpectrumDisplayFrame, SpectrumFrame

REF_RANGE_STEPS_DB = (40.0, 50.0, 60.0, 80.0, 100.0, 120.0)


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
    floor = float(np.percentile(interior if interior.size else power, 8))
    dynamic = max(peak - floor, 10.0)
    target_range = dynamic * 1.15 + 10.0
    range_db = min(REF_RANGE_STEPS_DB, key=lambda r: abs(r - target_range))
    db_per_div = range_db / 10.0
    ref = peak + db_per_div * 0.8
    return SpectrumDisplayFrame(frame=frame, ref_level_dbm=ref, ref_range_db=range_db)
