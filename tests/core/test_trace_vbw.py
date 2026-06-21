"""Suavizado de traza (SUAV) — pipeline espacial en IQ y barrido."""
from __future__ import annotations

import numpy as np

from core.monitor.spectrum_params import SpectrumParams
from core.rf.analysis.pipeline import apply_trace_smooth
from core.rf.bridge import analysis_config_from_params


def test_trace_smooth_auto_is_instant():
    params = SpectrumParams(capture_mode="iq", trace_smooth_auto=True, rbw_auto=True, fft_size=2048)
    config = analysis_config_from_params(params)
    x = np.array([-50.0, -40.0, -30.0], dtype=float)
    y = apply_trace_smooth(x, config)
    assert np.allclose(y, x)


def test_trace_smooth_manual_spatial_smooths_narrow_peak():
    params = SpectrumParams(
        capture_mode="sweep",
        rbw_auto=False,
        rbw_hz=100_000.0,
        trace_smooth_auto=False,
        trace_smooth_bins=10,
    )
    config = analysis_config_from_params(params)
    x = np.full(128, -60.0, dtype=float)
    x[64] = -20.0
    out = apply_trace_smooth(x, config)
    assert float(out[64]) < -20.0
    assert float(out[63]) > -60.0


def test_trace_smooth_bins_at_one_has_no_effect():
    params = SpectrumParams(
        capture_mode="iq",
        rbw_auto=False,
        rbw_hz=10_000.0,
        trace_smooth_auto=False,
        trace_smooth_bins=1,
    )
    config = analysis_config_from_params(params)
    x = np.array([-50.0, -20.0, -50.0], dtype=float)
    out = apply_trace_smooth(x, config)
    assert np.allclose(out, x)


def test_trace_smooth_iq_manual_smooths_single_frame():
    params = SpectrumParams(
        capture_mode="iq",
        rbw_auto=False,
        rbw_hz=10_000.0,
        trace_smooth_auto=False,
        trace_smooth_bins=10,
        fft_size=128,
        sample_rate_hz=2_000_000.0,
    )
    config = analysis_config_from_params(params)
    x = np.full(64, -70.0, dtype=float)
    x[32] = -25.0
    out = apply_trace_smooth(x, config)
    assert float(out[32]) < -25.0
    assert float(out[31]) > -70.0
