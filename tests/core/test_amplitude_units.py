"""Tests de conversión de unidades y sliders de escala."""
import math

from core.monitor.amplitude_units import dbm_to_display, display_to_dbm
from core.monitor.display_scale import (
    freq_to_slider_value,
    slider_value_to_freq,
    slider_value_to_span,
    span_to_slider_value,
)


def test_dbm_to_dbmv():
    assert dbm_to_display(0.0, "dBmV") == 47.0


def test_dbm_to_dbuv():
    assert dbm_to_display(0.0, "dBuV") == 107.0


def test_display_roundtrip_dbuv():
    dbm = -45.5
    disp = dbm_to_display(dbm, "dBuV")
    back = display_to_dbm(disp, "dBuV")
    assert abs(back - dbm) < 1e-6


def test_display_roundtrip_dbm():
    dbm = -45.5
    disp = dbm_to_display(dbm, "dBm")
    back = display_to_dbm(disp, "dBm")
    assert abs(back - dbm) < 1e-6


def test_freq_slider_roundtrip():
    freq = 90_900_000.0
    value = freq_to_slider_value(freq)
    back = slider_value_to_freq(value)
    assert abs(back - freq) / freq < 0.001


def test_span_slider_roundtrip():
    span = 10_000_000.0
    value = span_to_slider_value(span, max_span_hz=20_000_000.0)
    back = slider_value_to_span(value, max_span_hz=20_000_000.0)
    assert abs(back - span) / span < 0.01


def test_freq_in_span_slider():
    from core.monitor.display_scale import freq_in_span_to_slider, slider_to_freq_in_span

    start = 95_000_000.0
    stop = 105_000_000.0
    freq = 100_000_000.0
    value = freq_in_span_to_slider(freq, start, stop)
    back = slider_to_freq_in_span(value, start, stop)
    assert abs(back - freq) < 1.0


def test_v_unit_is_log():
    dbm = 0.0
    disp = dbm_to_display(dbm, "V")
    assert math.isfinite(disp)
