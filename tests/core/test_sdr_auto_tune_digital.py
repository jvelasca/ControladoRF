"""Tests AUTO modo DIG."""
from __future__ import annotations

from core.monitor.sdr_auto_tune import compute_digital_auto_tune
from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams
from tests.core.test_sdr_auto_tune import _frame_with_peak


def test_digital_auto_tune_at_dab_freq() -> None:
    params = SpectrumParams(
        operating_mode="sdr",
        demod_mode="dig",
        center_freq_hz=202_928_000.0,
        vfo_freq_hz=202_928_000.0,
        capture_mode="iq",
    )
    frame = _frame_with_peak(center_hz=202.928e6, peak_hz=202.928e6, peak_db=-32.0)
    result = compute_digital_auto_tune(params, frame)
    assert result.ok
    assert result.params.digital_profile == "dab_iii"
    assert result.params.demod_mode == "dig"
    assert not result.params.audio_enabled
    assert result.params.digital_analysis_enabled
