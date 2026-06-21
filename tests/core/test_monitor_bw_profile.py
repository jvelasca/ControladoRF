"""Perfil resolución vs suavizado."""
from core.monitor.monitor_bw_profile import (
    format_resolution_status,
    format_smoothing_status,
    resolution_preset_selected,
    resolution_title_key,
    smooth_preset_selected,
    trace_smoothing_bins,
)
from core.monitor.monitor_bw_sweep_logic import patch_trace_smooth_auto
from core.monitor.spectrum_params import SpectrumParams


def test_resolution_and_smooth_labels_differ_in_iq_auto():
    params = SpectrumParams(capture_mode="iq", rbw_auto=True, trace_smooth_auto=True, fft_size=2048)
    res = format_resolution_status(params)
    smooth = format_smoothing_status(params)
    assert "FFT" in res
    assert smooth == "SUAV OFF"
    assert res != smooth


def test_iq_uses_fft_title():
    params = SpectrumParams(capture_mode="iq")
    assert resolution_title_key(params) == "monitor_lcd_fft"


def test_sweep_uses_rbw_title():
    params = SpectrumParams(capture_mode="sweep")
    assert resolution_title_key(params) == "monitor_lcd_rbw"


def test_smooth_bins_from_manual_setting():
    params = SpectrumParams(
        capture_mode="iq",
        rbw_auto=False,
        rbw_hz=10_000.0,
        fft_size=2048,
        sample_rate_hz=2_000_000.0,
        trace_smooth_auto=False,
        trace_smooth_bins=5,
    )
    assert trace_smoothing_bins(params) == 5


def test_trace_smooth_auto_is_off_not_equal_rbw():
    params = SpectrumParams(trace_smooth_auto=True, rbw_auto=True, fft_size=2048, sample_rate_hz=2_000_000.0)
    updated = patch_trace_smooth_auto(params, enabled=True)
    assert updated.trace_smooth_auto is True
    assert format_smoothing_status(updated) == "SUAV OFF"


def test_resolution_preset_selected_iq():
    params = SpectrumParams(capture_mode="iq", rbw_auto=True, fft_size=2048)
    assert resolution_preset_selected(params, fft_size=2048) is True
    assert resolution_preset_selected(params, fft_size=1024) is False


def test_resolution_preset_selected_sweep_auto():
    params = SpectrumParams(capture_mode="sweep", rbw_auto=True, span_hz=20_000_000.0)
    eff = params.effective_rbw_hz()
    assert resolution_preset_selected(params, rbw_hz=eff) is True


def test_smooth_preset_selected():
    off = SpectrumParams(trace_smooth_auto=True)
    assert smooth_preset_selected(off, 5) is False
    manual = SpectrumParams(trace_smooth_auto=False, trace_smooth_bins=5)
    assert smooth_preset_selected(manual, 5) is True
    assert smooth_preset_selected(manual, 11) is False
