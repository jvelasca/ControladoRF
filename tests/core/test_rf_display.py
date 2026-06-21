"""Tests rejilla y RBW AUTO del motor RF."""
from core.rf.display import (
    ANALYZER_AUTO_POINTS,
    display_trace_bins,
    pick_stable_sweep_rbw,
)
from core.monitor.monitor_bw_sweep_logic import (
    SWEEP_RBW_MIN_HZ,
    optimize_analyzer_auto_for_span,
    sync_analysis_chain,
)
from core.monitor.monitor_freq_span_logic import patch_manual_span
from core.monitor.monitor_mode_profile import refresh_capture_and_span_limits
from core.monitor.spectrum_params import SpectrumParams


def _fm_analyzer_params(span_hz: float) -> SpectrumParams:
    params = SpectrumParams(
        operating_mode="spectrum",
        source_id="hackrf",
        center_freq_hz=98_000_000.0,
        manual_span_hz=span_hz,
        span_mode="manual",
        rbw_auto=True,
        fft_auto=True,
        sweep_auto=True,
        trace_smooth_auto=True,
        capture_mode="iq",
    )
    refresh_capture_and_span_limits(params)
    sync_analysis_chain(params)
    return params


def test_fm_20mhz_uses_iq_not_sweep():
    params = _fm_analyzer_params(20_000_000.0)
    assert params.capture_mode == "iq"


def test_fm_wide_span_uses_sweep():
    params = _fm_analyzer_params(80_000_000.0)
    assert params.capture_mode == "sweep"


def test_sweep_display_bins_auto_uses_801():
    params = SpectrumParams(capture_mode="sweep", fft_auto=True, fft_size=64)
    assert display_trace_bins(params) == ANALYZER_AUTO_POINTS


def test_sweep_display_bins_manual_uses_fft():
    params = SpectrumParams(capture_mode="sweep", fft_auto=False, fft_size=1024)
    assert display_trace_bins(params) == 1024


def test_pick_stable_sweep_rbw_hysteresis_on_small_span_change():
    rbw_19 = pick_stable_sweep_rbw(19_000_000.0)
    rbw_21 = pick_stable_sweep_rbw(21_000_000.0, current_rbw_hz=rbw_19)
    assert rbw_19 == rbw_21


def test_fm_21mhz_uses_sweep_not_iq():
    params = _fm_analyzer_params(20_000_000.0)
    updated = patch_manual_span(params, 21_000_000.0)
    assert updated.capture_mode == "sweep"
    assert abs(updated.manual_span_hz - 21_000_000.0) < 1.0
    assert abs(updated.display_span_hz() - 21_000_000.0) < 1.0


def test_fm_31mhz_uses_sweep():
    params = _fm_analyzer_params(31_000_000.0)
    assert params.capture_mode == "sweep"
    assert abs(params.manual_span_hz - 31_000_000.0) < 1.0


def test_manual_rbw_preserved_across_sweep_span_nudge():
    params = _fm_analyzer_params(20_000_000.0)
    params.rbw_auto = False
    params.fft_auto = False
    params.rbw_hz = 300_000.0
    updated = patch_manual_span(params, 31_000_000.0)
    assert updated.capture_mode == "sweep"
    assert not updated.rbw_auto
    assert abs(updated.rbw_hz - 300_000.0) < 1.0


def test_step_span_from_20mhz_reaches_21mhz():
    from core.monitor.display_scale import step_span_hz

    assert step_span_hz(20_000_000.0, 1) == 21_000_000.0


def test_optimize_auto_span_nudges_enter_sweep_rbw():
    params = _fm_analyzer_params(19_000_000.0)
    assert params.capture_mode == "iq"
    updated = patch_manual_span(params, 21_000_000.0)
    refresh_capture_and_span_limits(updated)
    sync_analysis_chain(updated)
    assert updated.capture_mode == "sweep"
    assert updated.rbw_hz >= SWEEP_RBW_MIN_HZ
    assert updated.effective_rbw_hz() >= SWEEP_RBW_MIN_HZ


def test_wide_span_200mhz_uses_coarse_sweep_rbw():
    from core.rf.display import ideal_sweep_rbw_hz

    rbw = ideal_sweep_rbw_hz(200_000_000.0)
    bins = 200_000_000.0 / rbw
    assert rbw >= 500_000.0
    assert bins <= 320
