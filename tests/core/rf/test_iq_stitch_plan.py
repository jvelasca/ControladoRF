"""Politica lapso vs BW instantaneo (hackrf_sweep si SPAN > 20 MHz)."""
from core.monitor.display_scale import step_span_hz
from core.rf.acquisition.iq_stitch_plan import (
    MAX_STITCH_CAPTURES,
    prefers_hackrf_sweep,
    span_exceeds_instant_bw,
    stitch_capture_count,
    stitch_center_freqs,
)


def test_20mhz_stays_iq():
    assert not span_exceeds_instant_bw(20_000_000.0, 20_000_000.0)
    assert not prefers_hackrf_sweep(20_000_000.0, 20_000_000.0)


def test_21mhz_uses_sweep():
    assert span_exceeds_instant_bw(21_000_000.0, 20_000_000.0)
    assert prefers_hackrf_sweep(21_000_000.0, 20_000_000.0)


def test_31mhz_uses_sweep():
    assert prefers_hackrf_sweep(31_000_000.0, 20_000_000.0)


def test_stitch_centers_legacy_helpers_still_defined():
    """Helpers de stitch IQ (legacy) siguen disponibles para referencia."""
    assert stitch_capture_count(31_000_000.0, 20_000_000.0) <= MAX_STITCH_CAPTURES
    centers = stitch_center_freqs(97.3e6, 31e6, 20e6)
    assert len(centers) >= 2


def test_step_span_30_to_31():
    assert step_span_hz(30_000_000.0, 1) == 31_000_000.0
