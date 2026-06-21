"""Tests de rango del slider SPAN en modo analizador."""
from core.monitor.display_scale import slider_value_to_span, span_to_slider_value
from core.monitor.monitor_freq_span_logic import ui_span_min_hz
from core.monitor.monitor_operating_mode import MonitorOperatingMode
from core.monitor.spectrum_params import SpectrumParams


def test_span_slider_supports_sweep_minimum():
    params = SpectrumParams(operating_mode=MonitorOperatingMode.SPECTRUM.value)
    min_hz = ui_span_min_hz(params)
    assert min_hz == 100_000.0
    value = span_to_slider_value(min_hz, max_span_hz=20_000_000.0, min_span_hz=min_hz)
    back = slider_value_to_span(value, max_span_hz=20_000_000.0, min_span_hz=min_hz)
    assert back < 2_000_000.0
    assert abs(back - min_hz) < 50_000.0
