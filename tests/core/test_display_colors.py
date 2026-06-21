"""Tests de colores DISPLAY del Monitor."""
from core.monitor.display_colors import (
    DEFAULT_SDR_TRACE_COLOR,
    DEFAULT_SPAN_VIEWPORT_COLOR,
    DEFAULT_TRACE_COLOR,
    apply_display_color_defaults,
    apply_display_sdr_color_defaults,
    is_sdr_display_mode,
    span_slider_colors,
    spectrum_trace_color,
)
from core.monitor.monitor_mode_profile import ui_max_span_hz
from core.monitor.monitor_operating_mode import MonitorOperatingMode
from core.monitor.spectrum_params import SpectrumParams
from core.monitor.spectrum_params_io import params_from_dict, params_to_dict


def test_span_slider_colors_default_more_opaque_than_legacy():
    colors = span_slider_colors(SpectrumParams())
    assert colors.viewport_shadow.alpha() >= 180
    assert colors.viewport_shadow.green() >= colors.viewport_shadow.red()


def test_sdr_mode_uses_sdr_palette():
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SDR.value,
        display_sdr_span_handle_color="#FF00FF",
    )
    assert is_sdr_display_mode(params)
    colors = span_slider_colors(params)
    assert colors.handle.red() == 255
    assert colors.handle.blue() == 255


def test_spectrum_trace_color_by_mode():
    analyzer = SpectrumParams(display_trace_color="#112233")
    sdr = SpectrumParams(
        operating_mode=MonitorOperatingMode.SDR.value,
        display_sdr_trace_color="#AABBCC",
    )
    assert spectrum_trace_color(analyzer).red() == 0x11
    assert spectrum_trace_color(sdr).red() == 0xAA


def test_ui_max_span_sdr_is_instant_bandwidth():
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SDR.value,
        source_id="hackrf",
    )
    assert ui_max_span_hz(params) == 20_000_000.0


def test_apply_display_color_defaults():
    params = SpectrumParams(display_span_viewport_color="#ABCDEF")
    restored = apply_display_color_defaults(params)
    assert restored.display_span_viewport_color == DEFAULT_SPAN_VIEWPORT_COLOR
    assert restored.display_trace_color == DEFAULT_TRACE_COLOR


def test_apply_display_sdr_color_defaults():
    params = SpectrumParams(display_sdr_trace_color="#ABCDEF")
    restored = apply_display_sdr_color_defaults(params)
    assert restored.display_sdr_trace_color == DEFAULT_SDR_TRACE_COLOR


def test_display_colors_persist_roundtrip():
    params = SpectrumParams(
        display_span_viewport_color="#112233",
        display_trace_color="#445566",
        display_sdr_trace_color="#778899",
    )
    data = params_to_dict(params)
    loaded = params_from_dict(data)
    assert loaded.display_span_viewport_color == "#112233"
    assert loaded.display_trace_color == "#445566"
    assert loaded.display_sdr_trace_color == "#778899"
