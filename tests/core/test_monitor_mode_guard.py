"""Tests avisos de restricción Analizador / SDR."""
from core.monitor.monitor_mode_guard import (
    demod_requires_sdr_mode,
    span_mode_requires_analyzer_mode,
    span_requires_analyzer_mode,
    zoom_out_requires_analyzer_mode,
)
from core.monitor.monitor_operating_mode import MonitorOperatingMode
from core.monitor.spectrum_params import SpectrumParams


def test_span_requires_analyzer_in_sdr():
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SDR.value,
        source_id="hackrf",
    )
    notice = span_requires_analyzer_mode(params, 25_000_000.0)
    assert notice is not None
    assert notice.i18n_key == "monitor_mode_warn_span_analyzer"
    assert notice.max_mhz == 20.0


def test_span_ok_in_analyzer():
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        source_id="hackrf",
    )
    assert span_requires_analyzer_mode(params, 50_000_000.0) is None


def test_full_span_mode_in_sdr():
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SDR.value,
        source_id="hackrf",
    )
    notice = span_mode_requires_analyzer_mode(params, "full")
    assert notice is not None
    assert notice.i18n_key == "monitor_mode_warn_full_span_analyzer"


def test_demod_requires_sdr_in_analyzer():
    params = SpectrumParams(operating_mode=MonitorOperatingMode.SPECTRUM.value)
    notice = demod_requires_sdr_mode(params)
    assert notice is not None
    assert notice.i18n_key == "monitor_mode_warn_demod_sdr_only"


def test_zoom_out_blocked_in_sdr():
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SDR.value,
        source_id="hackrf",
        manual_span_hz=20_000_000.0,
        span_mode="manual",
    )
    notice = zoom_out_requires_analyzer_mode(params, 0.5)
    assert notice is not None
