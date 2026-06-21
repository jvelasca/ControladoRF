"""Tests pipeline análisis v2 — SUAV manual."""
from __future__ import annotations

import numpy as np

from core.rf.analysis.pipeline import AnalysisPipeline
from core.rf.types import AcquisitionMode, AnalysisConfig, FrameMetadata, SpectrumFrame


def _flat_frame(*, n: int = 64) -> SpectrumFrame:
    power = np.full(n, -70.0, dtype=float)
    power[n // 2] = -40.0
    meta = FrameMetadata(
        acquisition_mode=AcquisitionMode.IQ_STREAM,
        device_id="mock",
        rbw_hz=100_000.0,
    )
    return SpectrumFrame(
        freqs_hz=np.linspace(90e6, 100e6, n),
        power_db=power,
        metadata=meta,
    )


def test_trace_smooth_manual_reduces_peak():
    pipe = AnalysisPipeline()
    frame = _flat_frame()
    raw_peak = float(np.max(frame.power_db))
    cfg = AnalysisConfig(
        rbw_hz=100_000.0,
        trace_smooth_auto=False,
        trace_smooth_bins=9,
    )
    out = pipe.process(frame, cfg)
    assert float(np.max(out.power_db)) < raw_peak
