"""Tests transición ANALIZADOR ↔ SDR con SPAN amplio."""
from __future__ import annotations

from core.monitor.monitor_mode_profile import (
    refresh_capture_and_span_limits,
    transition_operating_mode,
)
from core.monitor.monitor_operating_mode import MonitorOperatingMode
from core.monitor.spectrum_params import SpectrumParams


def test_analyzer_to_sdr_saves_wide_span_and_clamps_iq() -> None:
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        center_freq_hz=500_000_000.0,
        manual_span_hz=80_000_000.0,
        span_mode="manual",
        source_id="hackrf",
    )
    refresh_capture_and_span_limits(params)
    assert params.capture_mode == "sweep"

    clamped = transition_operating_mode(
        params,
        previous_mode=MonitorOperatingMode.SPECTRUM,
        new_mode=MonitorOperatingMode.SDR,
    )
    assert clamped is True
    assert params.analyzer_span_hz == 80_000_000.0
    assert params.analyzer_span_mode == "manual"
    assert params.last_span_hz == 80_000_000.0
    params.operating_mode = MonitorOperatingMode.SDR.value
    refresh_capture_and_span_limits(params)
    assert params.capture_mode == "iq"
    assert params.manual_span_hz <= 20_000_000.0
    assert params.span_hz <= 20_000_000.0


def test_sdr_to_analyzer_restores_wide_span_and_sweep() -> None:
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SDR.value,
        center_freq_hz=500_000_000.0,
        manual_span_hz=20_000_000.0,
        analyzer_span_hz=80_000_000.0,
        analyzer_span_mode="manual",
        span_mode="manual",
        source_id="hackrf",
    )
    transition_operating_mode(
        params,
        previous_mode=MonitorOperatingMode.SDR,
        new_mode=MonitorOperatingMode.SPECTRUM,
    )
    assert params.analyzer_span_hz == 0.0
    assert params.manual_span_hz == 80_000_000.0
    params.operating_mode = MonitorOperatingMode.SPECTRUM.value
    refresh_capture_and_span_limits(params)
    assert params.capture_mode == "sweep"
    assert params.span_hz == 80_000_000.0


def test_sdr_does_not_clobber_last_span() -> None:
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        manual_span_hz=50_000_000.0,
        last_span_hz=12_000_000.0,
        span_mode="manual",
        source_id="hackrf",
    )
    transition_operating_mode(
        params,
        previous_mode=MonitorOperatingMode.SPECTRUM,
        new_mode=MonitorOperatingMode.SDR,
    )
    assert params.last_span_hz == 50_000_000.0


def test_analyzer_to_sdr_keeps_narrow_span_without_forcing_max() -> None:
    """Convención A: 10 MHz en analizador → 10 MHz en SDR (no ampliar a 20 MHz)."""
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        center_freq_hz=500_000_000.0,
        manual_span_hz=10_000_000.0,
        span_mode="manual",
        source_id="hackrf",
    )
    refresh_capture_and_span_limits(params)
    clamped = transition_operating_mode(
        params,
        previous_mode=MonitorOperatingMode.SPECTRUM,
        new_mode=MonitorOperatingMode.SDR,
    )
    assert clamped is False
    assert params.analyzer_span_hz == 10_000_000.0
    assert params.manual_span_hz == 10_000_000.0
    params.operating_mode = MonitorOperatingMode.SDR.value
    refresh_capture_and_span_limits(params)
    assert params.span_hz == 10_000_000.0

    transition_operating_mode(
        params,
        previous_mode=MonitorOperatingMode.SDR,
        new_mode=MonitorOperatingMode.SPECTRUM,
    )
    assert params.manual_span_hz == 10_000_000.0


def test_analyzer_100mhz_round_trip() -> None:
    fc = 500_000_000.0
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        center_freq_hz=fc,
        manual_span_hz=100_000_000.0,
        span_mode="manual",
        source_id="hackrf",
    )
    refresh_capture_and_span_limits(params)
    transition_operating_mode(
        params,
        previous_mode=MonitorOperatingMode.SPECTRUM,
        new_mode=MonitorOperatingMode.SDR,
    )
    assert params.center_freq_hz == fc
    assert params.manual_span_hz == 20_000_000.0
    assert params.analyzer_span_hz == 100_000_000.0

    transition_operating_mode(
        params,
        previous_mode=MonitorOperatingMode.SDR,
        new_mode=MonitorOperatingMode.SPECTRUM,
    )
    params.operating_mode = MonitorOperatingMode.SPECTRUM.value
    refresh_capture_and_span_limits(params)
    assert params.center_freq_hz == fc
    assert params.manual_span_hz == 100_000_000.0
    assert params.capture_mode == "sweep"
    assert params.span_hz == 100_000_000.0


def test_sdr_display_span_ignores_stale_freq_window() -> None:
    """Slider/toolbar: en SDR debe mostrar manual_span, no la ventana FI/FF del analizador."""
    from core.monitor.monitor_freq_span_logic import display_span_hz

    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SDR.value,
        center_freq_hz=500_000_000.0,
        manual_span_hz=20_000_000.0,
        span_hz=20_000_000.0,
        span_mode="manual",
        marker_start_hz=450_000_000.0,
        marker_stop_hz=550_000_000.0,
        source_id="hackrf",
    )
    assert params.has_freq_window()
    assert display_span_hz(params) == 20_000_000.0


def test_transition_clears_freq_window() -> None:
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        center_freq_hz=500_000_000.0,
        manual_span_hz=100_000_000.0,
        span_mode="manual",
        marker_start_hz=450_000_000.0,
        marker_stop_hz=550_000_000.0,
        source_id="hackrf",
    )
    assert params.has_freq_window()
    transition_operating_mode(
        params,
        previous_mode=MonitorOperatingMode.SPECTRUM,
        new_mode=MonitorOperatingMode.SDR,
    )
    assert not params.has_freq_window()

    params.analyzer_span_hz = 100_000_000.0
    params.analyzer_span_mode = "manual"
    params.operating_mode = MonitorOperatingMode.SDR.value
    transition_operating_mode(
        params,
        previous_mode=MonitorOperatingMode.SDR,
        new_mode=MonitorOperatingMode.SPECTRUM,
    )
    assert not params.has_freq_window()
    assert params.manual_span_hz == 100_000_000.0


def test_analyzer_display_span_prefers_manual_over_stale_window() -> None:
    from core.monitor.monitor_freq_span_logic import display_span_hz

    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        manual_span_hz=50_000_000.0,
        span_mode="manual",
        marker_start_hz=495_000_000.0,
        marker_stop_hz=505_000_000.0,
        source_id="hackrf",
    )
    assert params.has_freq_window()
    assert display_span_hz(params) == 50_000_000.0


def test_wide_span_uses_sweep_above_20mhz() -> None:
    """21 MHz+: hackrf_sweep; <=20 MHz: IQ fluido."""
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        center_freq_hz=500_000_000.0,
        manual_span_hz=50_000_000.0,
        span_mode="manual",
        source_id="hackrf",
    )
    refresh_capture_and_span_limits(params)
    assert params.capture_mode == "sweep"

    params.manual_span_hz = 21_000_000.0
    refresh_capture_and_span_limits(params)
    assert params.capture_mode == "sweep"

    params.manual_span_hz = 20_000_000.0
    refresh_capture_and_span_limits(params)
    assert params.capture_mode == "iq"


def test_sync_span_geometry_resizes_stale_window() -> None:
    from core.monitor.monitor_freq_span_logic import sync_span_geometry

    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        center_freq_hz=500_000_000.0,
        manual_span_hz=50_000_000.0,
        span_hz=50_000_000.0,
        span_mode="manual",
        capture_mode="sweep",
        marker_start_hz=495_000_000.0,
        marker_stop_hz=505_000_000.0,
        source_id="hackrf",
    )
    sync_span_geometry(params)
    assert abs((params.marker_stop_hz - params.marker_start_hz) - 50_000_000.0) < 1.0


def test_sweep_uses_manual_span_not_stale_markers() -> None:
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        center_freq_hz=500_000_000.0,
        manual_span_hz=50_000_000.0,
        span_hz=50_000_000.0,
        span_mode="manual",
        capture_mode="sweep",
        marker_start_hz=495_000_000.0,
        marker_stop_hz=505_000_000.0,
        source_id="hackrf",
    )
    assert params.freq_stop_hz() - params.freq_start_hz() == 50_000_000.0


def test_sdr_iq_freq_window_uses_center_passband() -> None:
    from core.monitor.monitor_freq_span_logic import sync_span_geometry

    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SDR.value,
        center_freq_hz=500_000_000.0,
        manual_span_hz=20_000_000.0,
        sample_rate_hz=20_000_000.0,
        span_hz=20_000_000.0,
        span_mode="manual",
        capture_mode="iq",
        marker_start_hz=450_000_000.0,
        marker_stop_hz=550_000_000.0,
        source_id="hackrf",
    )
    sync_span_geometry(params)
    assert not params.has_freq_window()
    assert params.freq_start_hz() == 490_000_000.0
    assert params.freq_stop_hz() == 510_000_000.0
