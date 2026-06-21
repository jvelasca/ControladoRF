"""Tests puente legacy ↔ motor v2."""
from core.monitor.spectrum_params import SpectrumParams
from core.rf.bridge import (
    frequency_window_from_params,
    operator_intent_from_params,
    sync_params_capture_mode_from_v2,
)
from core.rf.types import OperatingMode


def test_operator_intent_from_fm_params():
    params = SpectrumParams(
        operating_mode="spectrum",
        source_id="hackrf",
        center_freq_hz=98_000_000.0,
        manual_span_hz=20_000_000.0,
        span_hz=20_000_000.0,
        span_mode="manual",
        marker_start_hz=88_000_000.0,
        marker_stop_hz=108_000_000.0,
        capture_mode="sweep",
    )
    intent = operator_intent_from_params(params)
    assert intent.operating_mode is OperatingMode.SPECTRUM
    assert intent.source_id == "hackrf"
    assert abs(intent.window.span_hz - 20_000_000.0) < 1.0


def test_frequency_window_uses_fi_ff_when_coherent():
    params = SpectrumParams(
        operating_mode="spectrum",
        capture_mode="sweep",
        center_freq_hz=98_000_000.0,
        manual_span_hz=20_000_000.0,
        span_mode="manual",
        marker_start_hz=88_000_000.0,
        marker_stop_hz=108_000_000.0,
    )
    w = frequency_window_from_params(params)
    assert abs(w.start_hz - 88_000_000.0) < 1.0
    assert abs(w.stop_hz - 108_000_000.0) < 1.0


def test_sync_capture_mode_iq_for_fm_span():
    params = SpectrumParams(
        operating_mode="spectrum",
        source_id="hackrf",
        center_freq_hz=98_000_000.0,
        manual_span_hz=20_000_000.0,
        span_mode="manual",
        capture_mode="sweep",
    )
    sync_params_capture_mode_from_v2(params)
    assert params.capture_mode == "iq"
