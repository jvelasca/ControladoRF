"""Tests IQ compuesto (fusion de trazos)."""
from core.rf.acquisition.iq_stitch_plan import stitch_center_freqs
from core.rf.devices.hackrf.iq_stitch import merge_spectrum_frames
from core.rf.types import AcquisitionMode, FrameMetadata, SpectrumFrame
import numpy as np


def test_stitch_centers_two_offsets_for_21mhz():
    centers = stitch_center_freqs(97.3e6, 21e6, 20e6)
    assert len(centers) >= 2


def test_stitch_centers_single_for_20mhz():
    centers = stitch_center_freqs(97.3e6, 20e6, 20e6)
    assert centers == [97.3e6]


def test_merge_spectrum_frames_max_hold():
    f1 = np.linspace(90e6, 100e6, 11)
    f2 = np.linspace(95e6, 105e6, 11)
    meta = FrameMetadata(
        acquisition_mode=AcquisitionMode.IQ_STREAM,
        device_id="hackrf",
        rbw_hz=10_000.0,
    )
    a = SpectrumFrame(freqs_hz=f1, power_db=np.full(11, -30.0), metadata=meta)
    b = SpectrumFrame(
        freqs_hz=f2,
        power_db=np.full(11, -50.0),
        metadata=meta,
    )
    merged = merge_spectrum_frames([a, b])
    assert merged.freqs_hz.size >= 11
    assert float(np.max(merged.power_db)) == -30.0
