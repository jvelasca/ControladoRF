"""Tests perfiles SDR vs analizador."""
from core.monitor.monitor_mode_profile import profile_for_params, refresh_capture_and_span_limits
from core.monitor.monitor_operating_mode import MonitorOperatingMode
from core.monitor.spectrum_params import SpectrumParams


def test_profile_sdr_limited_bandwidth():
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SDR.value,
        source_id="hackrf",
        manual_span_hz=15_000_000.0,
    )
    refresh_capture_and_span_limits(params)
    profile = profile_for_params(params)
    assert profile.capture_mode == "iq"
    assert profile.realtime_fft is True
    assert profile.max_span_hz == 20_000_000.0
    assert profile.demod_enabled is True


def test_profile_analyzer_sweep_when_wide():
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        center_freq_hz=100_000_000.0,
        manual_span_hz=40_000_000.0,
        span_mode="manual",
        source_id="hackrf",
    )
    refresh_capture_and_span_limits(params)
    profile = profile_for_params(params)
    assert profile.capture_mode == "sweep"
    assert profile.realtime_fft is False
    assert profile.max_span_hz > 20_000_000.0
    assert profile.demod_enabled is False
