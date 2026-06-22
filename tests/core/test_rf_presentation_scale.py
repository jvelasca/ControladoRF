"""Escala AUTO del pipeline RF (histéresis de rango vertical)."""
import numpy as np

from core.rf.presentation.scale import (
    REF_RANGE_STEPS_DB,
    apply_display_scale,
    stabilize_ref_level_dbm,
    stabilize_ref_range_db,
)
from core.rf.types import AcquisitionMode, DisplayConfig, FrameMetadata, SpectrumFrame


def test_stabilize_ref_range_holds_step_until_midpoint():
    prev = 80.0
    assert stabilize_ref_range_db(89.0, prev) == 80.0
    assert stabilize_ref_range_db(91.0, prev) == 100.0


def test_stabilize_ref_range_steps_down_with_hysteresis():
    prev = 100.0
    assert stabilize_ref_range_db(91.0, prev) == 100.0
    assert stabilize_ref_range_db(89.0, prev) == 80.0


def test_stabilize_ref_level_holds_within_deadband():
    assert stabilize_ref_level_dbm(-20.0, -21.0, deadband_db=2.0) == -21.0
    assert stabilize_ref_level_dbm(-30.0, -21.0, deadband_db=2.0) != -21.0


def test_apply_display_scale_uses_discrete_range_steps():
    n = 1024
    freqs = np.linspace(89e6, 107e6, n)
    power = np.linspace(-95.0, -40.0, n)
    frame = SpectrumFrame(
        freqs_hz=freqs,
        power_db=power,
        metadata=FrameMetadata(
            acquisition_mode=AcquisitionMode.IQ_STREAM,
            device_id="mock",
            rbw_hz=18_000_000.0 / n,
        ),
    )
    cfg = DisplayConfig(ref_auto=True, ref_level_dbm=0.0, ref_range_db=100.0)
    out = apply_display_scale(frame, cfg)
    assert out.ref_range_db in REF_RANGE_STEPS_DB
