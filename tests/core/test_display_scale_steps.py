"""Tests de pasos discretos para sliders RF y resolución vertical."""
from core.monitor.display_scale import (
    REF_RANGE_STEPS_DB,
    lna_gain_from_step_index,
    lna_step_index,
    ref_range_from_step_index,
    ref_range_step_index,
    ref_range_to_slider_value,
    slider_value_to_ref_range,
    vga_gain_from_step_index,
    vga_step_index,
)


def test_ref_range_step_roundtrip():
    for step_db in REF_RANGE_STEPS_DB:
        idx = ref_range_step_index(step_db)
        assert ref_range_from_step_index(idx) == step_db
        assert slider_value_to_ref_range(ref_range_to_slider_value(step_db)) == step_db


def test_lna_steps():
    for gain in (0, 8, 16, 24, 32, 40):
        assert lna_gain_from_step_index(lna_step_index(gain)) == gain


def test_vga_steps():
    for gain in range(0, 64, 2):
        assert vga_gain_from_step_index(vga_step_index(gain)) == gain
