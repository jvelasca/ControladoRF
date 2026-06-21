"""Tests de escala vertical AUTO y mapeo Y."""
import numpy as np

from core.monitor.display_scale import (
    apply_auto_vertical_scale,
    level_to_normalized_y,
    ref_range_to_slider_value,
    slider_value_to_ref_range,
)
from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams


def test_level_to_normalized_y_top_and_bottom():
    assert level_to_normalized_y(0.0, 0.0, -100.0) == 0.0
    assert level_to_normalized_y(-100.0, 0.0, -100.0) == 1.0
    assert level_to_normalized_y(-50.0, 0.0, -100.0) == 0.5


def test_apply_auto_vertical_scale_fits_peak():
    n = 512
    power = np.full(n, -90.0)
    power[200:220] = -45.0
    frame = SpectrumFrame(
        power_db=power,
        center_freq_hz=100e6,
        span_hz=2e6,
        ref_level_dbm=0.0,
        ref_range_db=100.0,
    )
    params = SpectrumParams(ref_scale_auto=True)
    scaled = apply_auto_vertical_scale(frame, params)
    assert scaled.ref_level_dbm > -45.0
    assert scaled.ref_level_dbm - (-45.0) <= scaled.ref_range_db + 5.0
    bottom = scaled.ref_level_dbm - scaled.ref_range_db
    assert bottom < -90.0


def test_ref_range_slider_roundtrip():
    for db in (40.0, 50.0, 60.0, 80.0, 100.0, 120.0):
        value = ref_range_to_slider_value(db)
        assert slider_value_to_ref_range(value) == db
