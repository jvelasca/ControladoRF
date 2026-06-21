"""Tests de lógica compartida FC/SPAN."""
import pytest

from core.monitor.monitor_freq_span_logic import (
    active_marker_freq_hz,
    clamp_span_hz,
    display_span_hz,
    ensure_marker_visible,
    freq_slider_value,
    patch_center_freq,
    patch_freq_readout,
    patch_freq_start,
    patch_freq_stop,
    patch_manual_span,
    patch_selected_freq,
    patch_span_mode,
    span_min_hz,
    span_zoom_viewport,
    ui_span_min_hz,
)
from core.monitor.monitor_operating_mode import MonitorOperatingMode
from core.monitor.spectrum_params import SpectrumParams


def test_visible_freq_window_matches_marker_span():
    params = SpectrumParams(
        center_freq_hz=98_000_000.0,
        span_mode="manual",
        manual_span_hz=20_000_000.0,
        marker_start_hz=88_000_000.0,
        marker_stop_hz=108_000_000.0,
        capture_mode="sweep",
    )
    from core.monitor.monitor_freq_span_logic import clamp_freq_to_visible_hz, visible_freq_window_hz

    start, stop = visible_freq_window_hz(params)
    assert abs(start - 88_000_000.0) < 1.0
    assert abs(stop - 108_000_000.0) < 1.0
    assert clamp_freq_to_visible_hz(params, 70_000_000.0) == pytest.approx(88_000_000.0)
    assert clamp_freq_to_visible_hz(params, 120_000_000.0) == pytest.approx(108_000_000.0)


def test_patch_selected_freq_clamp_visible_within_window():
    params = SpectrumParams(
        center_freq_hz=98_000_000.0,
        span_mode="manual",
        manual_span_hz=20_000_000.0,
        marker_start_hz=88_000_000.0,
        marker_stop_hz=108_000_000.0,
        freq_readout="f",
        marker_auto_pan=False,
        capture_mode="sweep",
    )
    updated = patch_selected_freq(params, 500_000_000.0, clamp_visible=True)
    assert updated.selected_freq_hz == pytest.approx(108_000_000.0)
    assert updated.center_freq_hz == pytest.approx(98_000_000.0)


def test_freq_slider_value_f_mode_uses_visible_span():
    from core.monitor.monitor_freq_span_logic import freq_slider_value, selected_freq_from_slider_value

    params = SpectrumParams(
        center_freq_hz=98_000_000.0,
        span_mode="manual",
        manual_span_hz=20_000_000.0,
        marker_start_hz=88_000_000.0,
        marker_stop_hz=108_000_000.0,
        freq_readout="f",
        selected_freq_hz=98_000_000.0,
        capture_mode="sweep",
    )
    value = freq_slider_value(params)
    restored = selected_freq_from_slider_value(params, value)
    assert restored == pytest.approx(98_000_000.0, rel=1e-6)


def test_patch_freq_readout_fc_sets_vfo_for_sdr():
    params = SpectrumParams(
        operating_mode="sdr",
        center_freq_hz=100_000_000.0,
        freq_readout="f",
        selected_freq_hz=101_000_000.0,
        vfo_freq_hz=101_000_000.0,
        capture_mode="iq",
        sample_rate_hz=2_000_000.0,
    )
    updated = patch_freq_readout(params, "fc")
    assert updated.vfo_freq_hz == pytest.approx(100_000_000.0)
    updated_f = patch_freq_readout(updated, "f")
    assert updated_f.vfo_freq_hz == pytest.approx(100_000_000.0)


def test_patch_manual_span_clears_freq_window():
    params = SpectrumParams(
        center_freq_hz=98_000_000.0,
        span_mode="manual",
        manual_span_hz=20_000_000.0,
        marker_start_hz=88_000_000.0,
        marker_stop_hz=108_000_000.0,
    )
    assert params.has_freq_window()
    updated = patch_manual_span(params, 10_000_000.0)
    assert not updated.has_freq_window()
    assert updated.center_freq_hz == pytest.approx(98_000_000.0)
    assert updated.manual_span_hz == pytest.approx(10_000_000.0)


def test_patch_freq_readout_fc_to_f_does_not_auto_enable_m1():
    params = SpectrumParams(center_freq_hz=100_000_000.0, freq_readout="fc")
    params.active_marker_id = 4
    for marker in params.markers:
        marker.enabled = False
    updated = patch_freq_readout(params, "f")
    assert updated.freq_readout == "f"
    assert updated.active_marker_id == 4
    assert not any(m.enabled for m in updated.markers)
    assert abs(updated.selected_freq_hz - 100_000_000.0) < 1.0


def test_span_zoom_viewport_scales_width_with_span():
    params = SpectrumParams(
        source_id="hackrf",
        center_freq_hz=100_000_000.0,
        span_mode="manual",
        manual_span_hz=10_000_000.0,
    )
    _, range_hz, _, width_narrow = span_zoom_viewport(params)
    params.manual_span_hz = 20_000_000.0
    _, _, _, width_wide = span_zoom_viewport(params)
    assert width_wide > width_narrow
    assert width_wide <= 1.0
    assert width_narrow > 0.0
    assert width_narrow < 0.01  # 10 MHz of ~6 GHz


def test_span_zoom_viewport_full_span():
    from core.monitor.monitor_mode_profile import full_span_window_hz

    center, span, _start = full_span_window_hz("hackrf")
    params = SpectrumParams(source_id="hackrf", center_freq_hz=center, manual_span_hz=span)
    _, _, center_ratio, width_ratio = span_zoom_viewport(params)
    assert width_ratio == 1.0
    assert abs(center_ratio - 0.5) < 0.01


def test_span_zoom_viewport_sdr_max_bw_full_width():
    params = SpectrumParams(
        source_id="hackrf",
        operating_mode=MonitorOperatingMode.SDR.value,
        center_freq_hz=100_000_000.0,
        span_mode="manual",
        manual_span_hz=20_000_000.0,
        capture_mode="iq",
    )
    min_hz, range_hz, center_ratio, width_ratio = span_zoom_viewport(params)
    assert range_hz == pytest.approx(18_000_000.0, rel=1e-6)
    assert width_ratio == 1.0
    assert abs(center_ratio - 0.5) < 0.01
    params.manual_span_hz = 2_000_000.0
    _, _, _, width_narrow = span_zoom_viewport(params)
    assert width_narrow == pytest.approx(0.0, abs=1e-6)


def test_span_zoom_viewport_sdr_scales_with_bw():
    params = SpectrumParams(
        source_id="hackrf",
        operating_mode=MonitorOperatingMode.SDR.value,
        manual_span_hz=11_000_000.0,
        capture_mode="iq",
    )
    _, _, _, width_mid = span_zoom_viewport(params)
    params.manual_span_hz = 20_000_000.0
    _, _, _, width_max = span_zoom_viewport(params)
    assert 0.0 < width_mid < width_max <= 1.0


def test_center_hz_from_span_zoom_ratio():
    params = SpectrumParams(source_id="hackrf", center_freq_hz=200_000_000.0, manual_span_hz=10_000_000.0)
    from core.monitor.monitor_freq_span_logic import center_hz_from_span_zoom_ratio

    hz = center_hz_from_span_zoom_ratio(params, 0.5)
    assert hz > 0.0

    params_sdr = SpectrumParams(
        source_id="hackrf",
        operating_mode=MonitorOperatingMode.SDR.value,
        center_freq_hz=105_200_000.0,
        manual_span_hz=200_000.0,
        capture_mode="iq",
    )
    assert center_hz_from_span_zoom_ratio(params_sdr, 0.25) == pytest.approx(105_200_000.0)


def test_patch_center_freq_keeps_selected_in_f_mode():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        selected_freq_hz=250_000_000.0,
        freq_readout="f",
        span_mode="manual",
        manual_span_hz=10_000_000.0,
    )
    updated = patch_center_freq(params, 200_000_000.0)
    assert updated.center_freq_hz == 200_000_000.0
    assert updated.selected_freq_hz == 250_000_000.0

def test_patch_center_freq_updates_limits():
    params = SpectrumParams(center_freq_hz=100_000_000.0, manual_span_hz=10_000_000.0)
    updated = patch_center_freq(params, 200_000_000.0)
    assert updated.center_freq_hz == 200_000_000.0
    assert updated.selected_freq_hz == 200_000_000.0
    assert updated.max_span_hz > 0


def test_patch_center_freq_does_not_change_manual_span():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        span_mode="manual",
        manual_span_hz=10_000_000.0,
    )
    updated = patch_center_freq(params, 150_000_000.0)
    assert updated.manual_span_hz == 10_000_000.0
    assert display_span_hz(updated) == 10_000_000.0


def test_patch_manual_span_sets_mode():
    params = SpectrumParams(span_mode="full", manual_span_hz=0.0)
    updated = patch_manual_span(params, 5_000_000.0)
    assert updated.span_mode == "manual"
    assert updated.manual_span_hz == 5_000_000.0


def test_patch_selected_freq_allows_outside_span():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        span_mode="manual",
        manual_span_hz=10_000_000.0,
        freq_readout="f",
        marker_auto_pan=False,
    )
    updated = patch_selected_freq(params, 500_000_000.0)
    assert updated.selected_freq_hz == 500_000_000.0
    assert updated.center_freq_hz == 100_000_000.0


def test_patch_span_mode_full_covers_device_range():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        span_mode="manual",
        manual_span_hz=5_000_000.0,
    )
    updated = patch_span_mode(params, "full")
    fmin, fmax = 1_000_000.0, 6_000_000_000.0
    assert updated.span_mode == "full"
    assert abs(updated.center_freq_hz - (fmin + fmax) / 2.0) < 1.0
    assert abs(updated.span_hz - (fmax - fmin)) < 1000.0
    assert abs(updated.freq_start_hz() - fmin) < 1000.0
    assert abs(updated.freq_stop_hz() - fmax) < 1000.0
    assert updated.capture_mode == "sweep"
    assert abs(updated.marker_start_hz - fmin) < 1.0
    assert abs(updated.marker_stop_hz - fmax) < 1.0


def test_full_span_overrides_existing_freq_window():
    params = SpectrumParams(
        operating_mode="spectrum",
        span_mode="manual",
        manual_span_hz=10_000_000.0,
        marker_start_hz=88_000_000.0,
        marker_stop_hz=108_000_000.0,
    )
    updated = patch_span_mode(params, "full")
    fmin, fmax = 1_000_000.0, 6_000_000_000.0
    assert abs(updated.marker_start_hz - fmin) < 1.0
    assert abs(updated.marker_stop_hz - fmax) < 1.0
    assert updated.capture_mode == "sweep"


def test_narrow_span_uses_sweep_mode():
    params = SpectrumParams(
        operating_mode="spectrum",
        span_mode="manual",
        manual_span_hz=500_000.0,
    )
    updated = patch_manual_span(params, 500_000.0)
    assert updated.capture_mode == "sweep"
    assert updated.manual_span_hz == 500_000.0


def test_patch_manual_span_from_iq_ui_not_clamped_to_2mhz():
    params = SpectrumParams(
        operating_mode="spectrum",
        capture_mode="iq",
        span_mode="manual",
        manual_span_hz=2_000_000.0,
    )
    updated = patch_manual_span(params, 500_000.0)
    assert updated.capture_mode == "sweep"
    assert updated.manual_span_hz == 500_000.0


def test_span_min_iq_mode():
    params = SpectrumParams(capture_mode="iq")
    assert span_min_hz(params) == 2_000_000.0
    assert clamp_span_hz(params, 100_000.0) == 2_000_000.0


def test_ui_span_min_analyzer_allows_sweep():
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        capture_mode="iq",
    )
    assert ui_span_min_hz(params) == 100_000.0


def test_patch_freq_start_wide_span_analyzer_uses_sweep():
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        center_freq_hz=500_000_000.0,
        span_mode="manual",
        manual_span_hz=10_000_000.0,
    )
    params = patch_freq_stop(patch_freq_start(params, 495_000_000.0), 505_000_000.0)
    updated = patch_freq_start(params, 470_000_000.0)
    assert abs(updated.freq_start_hz() - 470_000_000.0) < 1.0
    assert abs(updated.freq_stop_hz() - 505_000_000.0) < 1.0
    assert updated.manual_span_hz == pytest.approx(35_000_000.0, rel=1e-6)
    assert display_span_hz(updated) == pytest.approx(35_000_000.0, rel=1e-6)
    assert updated.capture_mode == "sweep"


def test_patch_freq_stop_wide_span_keeps_start():
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        center_freq_hz=100_000_000.0,
        span_mode="manual",
        manual_span_hz=10_000_000.0,
    )
    params = patch_freq_stop(patch_freq_start(params, 95_000_000.0), 105_000_000.0)
    start_before = params.freq_start_hz()
    updated = patch_freq_stop(params, 550_000_000.0)
    assert abs(updated.freq_start_hz() - start_before) < 1.0
    assert abs(updated.freq_stop_hz() - 550_000_000.0) < 1.0
    assert updated.manual_span_hz == pytest.approx(550_000_000.0 - start_before, rel=1e-6)
    assert updated.capture_mode == "sweep"


def test_patch_freq_start_sdr_clamps_span_not_start():
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SDR.value,
        center_freq_hz=500_000_000.0,
        span_mode="manual",
        manual_span_hz=10_000_000.0,
    )
    params = patch_freq_stop(patch_freq_start(params, 495_000_000.0), 505_000_000.0)
    updated = patch_freq_start(params, 470_000_000.0)
    assert abs(updated.freq_start_hz() - 470_000_000.0) < 1.0
    assert updated.manual_span_hz == pytest.approx(20_000_000.0, rel=1e-6)
    assert abs(updated.freq_stop_hz() - 490_000_000.0) < 1.0


def test_patch_freq_start_keeps_stop():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        span_mode="manual",
        manual_span_hz=10_000_000.0,
    )
    stop_before = params.freq_stop_hz()
    updated = patch_freq_start(params, 95_000_000.0)
    assert abs(updated.freq_stop_hz() - stop_before) < 1.0
    assert updated.manual_span_hz == stop_before - 95_000_000.0
    assert abs(updated.center_freq_hz - (95_000_000.0 + stop_before) / 2.0) < 1.0


def test_patch_freq_stop_keeps_start():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        span_mode="manual",
        manual_span_hz=10_000_000.0,
    )
    start_before = params.freq_start_hz()
    updated = patch_freq_stop(params, 108_000_000.0)
    assert abs(updated.freq_start_hz() - start_before) < 1.0
    assert updated.manual_span_hz == 108_000_000.0 - start_before
    assert abs(updated.center_freq_hz - (start_before + 108_000_000.0) / 2.0) < 1.0


def test_freq_window_survives_center_pan():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        span_mode="manual",
        manual_span_hz=10_000_000.0,
    )
    windowed = patch_freq_stop(patch_freq_start(params, 88_000_000.0), 108_000_000.0)
    assert windowed.has_freq_window()
    width = windowed.marker_stop_hz - windowed.marker_start_hz
    panned = patch_center_freq(windowed, 200_000_000.0)
    assert panned.has_freq_window()
    assert abs((panned.marker_stop_hz - panned.marker_start_hz) - width) < 1.0
    assert panned.freq_start_hz() < panned.center_freq_hz < panned.freq_stop_hz()


def test_patch_center_freq_does_not_clear_freq_window():
    params = patch_freq_stop(patch_freq_start(SpectrumParams(), 88_000_000.0), 108_000_000.0)
    updated = patch_center_freq(params, params.center_freq_hz)
    assert updated.has_freq_window()
    assert abs(updated.freq_start_hz() - 88_000_000.0) < 1.0
    assert abs(updated.freq_stop_hz() - 108_000_000.0) < 1.0


def test_span_min_sweep_mode():
    params = SpectrumParams(capture_mode="sweep")
    assert span_min_hz(params) == 100_000.0
    assert clamp_span_hz(params, 50_000.0) == 100_000.0


def test_patch_manual_span_preserves_center_fc():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        freq_readout="fc",
        span_mode="manual",
        manual_span_hz=2_000_000.0,
    )
    before = freq_slider_value(params)
    updated = patch_manual_span(params, 10_000_000.0)
    assert updated.center_freq_hz == 100_000_000.0
    assert freq_slider_value(updated) == before


def test_active_marker_freq_hz_fc_and_f():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        selected_freq_hz=250_000_000.0,
        freq_readout="f",
    )
    params.markers[0].enabled = True
    params.markers[0].freq_hz = 250_000_000.0
    assert active_marker_freq_hz(params) == 250_000_000.0
    params.freq_readout = "fc"
    params.markers[0].freq_hz = 100_000_000.0
    assert active_marker_freq_hz(params) == 100_000_000.0


def test_ensure_marker_visible_pans_when_f_offscreen():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        selected_freq_hz=500_000_000.0,
        freq_readout="f",
        span_mode="manual",
        manual_span_hz=10_000_000.0,
        marker_auto_pan=True,
        capture_mode="sweep",
    )
    params.markers[0].enabled = True
    params.markers[0].freq_hz = 500_000_000.0
    updated = ensure_marker_visible(params)
    assert updated.center_freq_hz == 500_000_000.0
    assert updated.selected_freq_hz == 500_000_000.0


def test_ensure_marker_visible_iq_does_not_move_lo():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        selected_freq_hz=500_000_000.0,
        freq_readout="f",
        span_mode="manual",
        manual_span_hz=2_000_000.0,
        marker_auto_pan=True,
        capture_mode="iq",
    )
    updated = ensure_marker_visible(params)
    assert updated.center_freq_hz == 100_000_000.0
    assert updated.selected_freq_hz == 500_000_000.0


def test_ensure_marker_visible_respects_auto_pan_off():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        selected_freq_hz=500_000_000.0,
        freq_readout="f",
        span_mode="manual",
        manual_span_hz=10_000_000.0,
        marker_auto_pan=False,
    )
    updated = ensure_marker_visible(params)
    assert updated.center_freq_hz == 100_000_000.0


def test_patch_selected_freq_auto_pans_in_f_mode():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        freq_readout="f",
        span_mode="manual",
        manual_span_hz=10_000_000.0,
        marker_auto_pan=True,
        capture_mode="sweep",
    )
    updated = patch_selected_freq(params, 500_000_000.0)
    assert updated.selected_freq_hz == 500_000_000.0
    assert updated.center_freq_hz == 500_000_000.0


def test_patch_selected_freq_iq_keeps_lo():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        freq_readout="f",
        span_mode="manual",
        manual_span_hz=2_000_000.0,
        marker_auto_pan=True,
        capture_mode="iq",
    )
    updated = patch_selected_freq(params, 500_000_000.0)
    assert updated.selected_freq_hz == 500_000_000.0
    assert updated.center_freq_hz == 100_000_000.0
