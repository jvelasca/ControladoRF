"""Tests ventana frecuencia 88–108 MHz y persistencia RBW/SWEEP."""
from core.monitor.monitor_bw_sweep_logic import (
    ANALYZER_AUTO_POINTS,
    SWEEP_RBW_MAX_HZ,
    SWEEP_RBW_MIN_HZ,
    capture_trace_now,
    optimize_analyzer_auto_for_span,
    patch_rbw_auto,
    patch_rbw_manual,
    patch_sweep_trigger_mode,
    patch_trace_smooth_auto,
    sweep_bin_width_hz,
)
from core.monitor.monitor_freq_span_logic import patch_freq_start, patch_freq_stop
from core.monitor.spectrum_params import SpectrumParams
from core.monitor.spectrum_params_io import params_from_dict, params_to_dict


def test_patch_rbw_auto_seeds_manual_value():
    params = SpectrumParams(rbw_auto=True, fft_size=2048, sample_rate_hz=2_000_000.0)
    auto_hz = params.effective_rbw_hz()
    updated = patch_rbw_manual(params)
    assert updated.rbw_auto is False
    assert abs(updated.rbw_hz - auto_hz) < 0.01


def test_patch_rbw_auto_resets_fft_after_coarse_manual():
    from core.monitor.monitor_bw_sweep_logic import patch_rbw_hz

    manual = patch_rbw_hz(
        SpectrumParams(span_hz=20_000_000.0, capture_mode="sweep", fft_size=2048),
        300_000.0,
    )
    assert manual.rbw_hz == 300_000.0
    assert manual.fft_size == 2048
    updated = patch_rbw_auto(manual)
    assert updated.rbw_auto is True
    assert updated.effective_rbw_hz() >= SWEEP_RBW_MIN_HZ


def test_patch_rbw_auto_iq_uses_sample_rate():
    from core.monitor.monitor_bw_sweep_logic import pick_auto_fft_size

    manual = SpectrumParams(
        capture_mode="iq",
        sample_rate_hz=10_000_000.0,
        span_hz=10_000_000.0,
        rbw_auto=False,
        rbw_hz=100_000.0,
        fft_size=256,
        fft_auto=False,
    )
    updated = patch_rbw_auto(manual)
    auto_fft = pick_auto_fft_size(updated)
    assert updated.fft_auto is True
    assert updated.fft_size == auto_fft
    assert abs(updated.rbw_hz - 10_000_000.0 / auto_fft) < 1.0


def test_capture_trace_now_uses_max_hold():
    params = SpectrumParams(trace_mode="clear_write", sweep_mode="single", single_sweep_pending=True)
    updated = capture_trace_now(params)
    assert updated.trace_mode == "max_hold"
    assert updated.sweep_mode == "continuous"
    assert updated.single_sweep_pending is False


def test_patch_trace_smooth_auto_seeds_manual_value():
    from core.monitor.monitor_bw_profile import trace_smoothing_bins

    params = SpectrumParams(trace_smooth_auto=True, rbw_auto=True, fft_size=2048, sample_rate_hz=2_000_000.0)
    updated = patch_trace_smooth_auto(params, enabled=False)
    assert updated.trace_smooth_auto is False
    assert trace_smoothing_bins(updated) >= 3


def test_patch_vbw_hz_legacy_converts_to_bins():
    from core.monitor.monitor_bw_sweep_logic import patch_vbw_hz

    params = SpectrumParams(
        capture_mode="sweep",
        rbw_auto=False,
        rbw_hz=100_000.0,
        trace_smooth_auto=True,
    )
    updated = patch_vbw_hz(params, 10_000.0)
    assert updated.trace_smooth_auto is False
    assert updated.trace_smooth_bins == 10


def test_smooth_presets_respect_fft_cap():
    from core.monitor.monitor_bw_profile import smooth_presets_for_params

    wide = SpectrumParams(fft_size=8192)
    assert smooth_presets_for_params(wide) == (1, 3, 5, 11, 21, 51)

    narrow = SpectrumParams(fft_size=8)
    presets = smooth_presets_for_params(narrow)
    assert presets
    assert max(presets) <= max(narrow.fft_size, 64)


def test_patch_sweep_trigger_manual():
    params = SpectrumParams()
    updated = patch_sweep_trigger_mode(params, "manual")
    assert updated.sweep_trigger_mode == "manual"
    assert updated.sweep_mode == "single"
    assert updated.single_sweep_pending is False


def test_freq_window_88_to_108_mhz():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        manual_span_hz=2_000_000.0,
        span_mode="manual",
        source_id="hackrf",
        operating_mode="spectrum",
    )
    updated = patch_freq_start(params, 88_000_000.0)
    updated = patch_freq_stop(updated, 108_000_000.0)
    assert abs(updated.marker_start_hz - 88_000_000.0) < 1.0
    assert abs(updated.marker_stop_hz - 108_000_000.0) < 1.0
    assert abs(updated.freq_start_hz() - 88_000_000.0) < 1.0
    assert abs(updated.freq_stop_hz() - 108_000_000.0) < 1.0
    assert abs(updated.center_freq_hz - 98_000_000.0) < 1.0
    assert abs(updated.display_span_hz() - 20_000_000.0) < 1000.0


def test_sweep_auto_time_uses_hardware_bin_floor_in_sweep_mode():
    from core.monitor.monitor_bw_sweep_logic import auto_sweep_time_ms, patch_rbw_hz, sync_analysis_chain

    params = SpectrumParams(
        capture_mode="sweep",
        span_hz=21_000_000.0,
        center_freq_hz=97_500_000.0,
        sweep_auto=True,
    )
    updated = patch_rbw_hz(params, 100.0)
    sync_analysis_chain(updated)
    assert updated.sweep_time_ms < 5000.0


def test_persist_rbw_sweep_and_markers():
    base = SpectrumParams(
        operating_mode="spectrum",
        capture_mode="sweep",
        span_mode="manual",
        manual_span_hz=20_000_000.0,
        center_freq_hz=98_000_000.0,
        marker_start_hz=88_000_000.0,
        marker_stop_hz=108_000_000.0,
        rbw_auto=False,
        rbw_hz=100_000.0,
        trace_smooth_auto=False,
        trace_smooth_bins=3,
        sweep_auto=False,
        sweep_time_ms=500.0,
        sweep_mode="single",
        trace_mode="max_hold",
        detector="peak",
    )
    data = params_to_dict(base)
    assert data["rbw_hz"] == 100_000.0
    assert data["sweep_mode"] == "single"
    restored = params_from_dict(data)
    assert abs(restored.marker_start_hz - 88_000_000.0) < 1.0
    assert restored.trace_smooth_auto is False
    assert restored.trace_smooth_bins == 3
    assert restored.trace_mode == "max_hold"


def test_persist_legacy_vbw_migrates_to_trace_smooth():
    from core.monitor.spectrum_params_io import migrate_legacy_vbw_fields

    base = SpectrumParams(
        capture_mode="sweep",
        rbw_auto=False,
        rbw_hz=100_000.0,
        fft_size=2048,
    )
    migrate_legacy_vbw_fields(base, {"vbw_auto": False, "vbw_hz": 10_000.0})
    assert base.trace_smooth_auto is False
    assert base.trace_smooth_bins == 10


def test_patch_rbw_manual_iq_preserves_fft():
    params = SpectrumParams(
        capture_mode="iq",
        sample_rate_hz=2_000_000.0,
        span_hz=2_000_000.0,
        rbw_auto=True,
        fft_size=2048,
    )
    prev_fft = params.fft_size
    updated = patch_rbw_manual(params)
    assert updated.rbw_auto is False
    assert updated.fft_size == prev_fft
    assert abs(updated.effective_rbw_hz() - 2_000_000.0 / 2048) < 1.0


def test_patch_rbw_hz_freezes_swt_and_fft_in_sweep():
    from core.monitor.monitor_bw_sweep_logic import patch_rbw_hz, sync_analysis_chain

    params = SpectrumParams(
        capture_mode="sweep",
        span_hz=20_000_000.0,
        center_freq_hz=98_000_000.0,
        rbw_auto=True,
        fft_auto=True,
        fft_size=2048,
        sweep_auto=True,
    )
    optimize_analyzer_auto_for_span(params)
    prev_fft = params.fft_size
    prev_swt = params.sweep_time_ms
    updated = patch_rbw_hz(params, 300_000.0)
    sync_analysis_chain(updated)
    assert updated.rbw_auto is False
    assert updated.sweep_auto is False
    assert updated.fft_size == prev_fft
    assert updated.fft_auto is True
    assert updated.sweep_time_ms == prev_swt
    assert updated.rbw_hz == 300_000.0


def test_patch_rbw_manual_freezes_swt_in_sweep():
    from core.monitor.monitor_bw_sweep_logic import patch_rbw_manual

    params = SpectrumParams(
        capture_mode="sweep",
        span_hz=20_000_000.0,
        rbw_auto=True,
        sweep_auto=True,
    )
    optimize_analyzer_auto_for_span(params)
    prev_swt = params.sweep_time_ms
    updated = patch_rbw_manual(params)
    assert updated.rbw_auto is False
    assert updated.sweep_auto is False
    assert updated.sweep_time_ms == prev_swt


def test_full_span_auto_rbw_uses_overview_cap():
    from core.monitor.monitor_freq_span_logic import patch_span_mode
    from core.monitor.monitor_mode_profile import refresh_capture_and_span_limits

    params = SpectrumParams(
        operating_mode="spectrum",
        source_id="hackrf",
        span_mode="manual",
        rbw_auto=True,
        trace_smooth_auto=True,
        sweep_auto=True,
    )
    updated = patch_span_mode(params, "full")
    refresh_capture_and_span_limits(updated)
    assert updated.capture_mode == "sweep"
    rbw = updated.effective_rbw_hz()
    assert SWEEP_RBW_MIN_HZ <= rbw <= SWEEP_RBW_MAX_HZ
    assert sweep_bin_width_hz(updated) >= SWEEP_RBW_MIN_HZ
    span = updated.freq_stop_hz() - updated.freq_start_hz()
    bins = span / sweep_bin_width_hz(updated)
    assert 400 <= bins <= 2500
    assert updated.sweep_time_ms >= 10.0


def test_optimize_analyzer_auto_for_narrow_sweep_span():
    params = SpectrumParams(
        capture_mode="sweep",
        span_mode="manual",
        manual_span_hz=10_000_000.0,
        center_freq_hz=100_000_000.0,
        rbw_auto=True,
        trace_smooth_auto=True,
        sweep_auto=True,
    )
    params.apply_span_mode()
    optimize_analyzer_auto_for_span(params)
    rbw = params.effective_rbw_hz()
    assert SWEEP_RBW_MIN_HZ <= rbw <= SWEEP_RBW_MAX_HZ
    span = max(params.span_hz, 1.0)
    assert abs(span / rbw - ANALYZER_AUTO_POINTS) < 80 or rbw >= SWEEP_RBW_MIN_HZ
