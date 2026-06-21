"""Tests del colormap del espectrograma."""
import numpy as np

from core.monitor.waterfall_colormap import (
    WATERFALL_COLORMAPS,
    apply_colormap,
    compute_history_levels,
    db_to_slider_value,
    power_db_to_rgb,
    resolve_waterfall_levels,
    slider_value_to_db,
)


def test_waterfall_slider_roundtrip():
    for db in (-120.0, -80.0, -40.0, 0.0, 20.0):
        value = db_to_slider_value(db)
        assert abs(slider_value_to_db(value) - db) < 0.2


def test_resolve_link_levels_from_ref():
    bottom, top = resolve_waterfall_levels(
        min_db=-50.0,
        max_db=10.0,
        link_spectrum=True,
        contrast_auto=False,
        ref_level_dbm=0.0,
        ref_range_db=100.0,
    )
    assert top == 0.0
    assert bottom == -100.0


def test_resolve_contrast_auto_from_history():
    history = np.array([[-90.0, -85.0, -50.0]], dtype=np.float32)
    bottom, top = resolve_waterfall_levels(
        min_db=-50.0,
        max_db=10.0,
        link_spectrum=False,
        contrast_auto=True,
        ref_level_dbm=0.0,
        ref_range_db=100.0,
        history_power_db=history,
    )
    assert bottom < -90.0
    assert top > -50.0


def test_compute_history_levels():
    history = np.array([[-80.0, -40.0]], dtype=np.float32)
    bottom, top = compute_history_levels(history, margin_db=3.0)
    assert bottom == -83.0
    assert top == -37.0


def test_power_db_to_rgb_shape_and_colormaps():
    power = np.array([[-100.0, -50.0, 0.0]], dtype=np.float32)
    for cmap in WATERFALL_COLORMAPS:
        rgb = power_db_to_rgb(power, min_db=-100.0, max_db=0.0, colormap=cmap)
        assert rgb.shape == (1, 3, 3)
        assert rgb.dtype == np.uint8
        assert rgb.max() <= 255
        assert rgb.min() >= 0


def test_apply_colormap_greyscale_endpoints():
    t = np.array([[0.0, 1.0]], dtype=np.float32)
    rgb = apply_colormap(t, "greyscale")
    assert rgb[0, 0, 0] == 0
    assert rgb[0, 1, 0] == 255
