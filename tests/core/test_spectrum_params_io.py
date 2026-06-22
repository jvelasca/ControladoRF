"""Tests de modos SPAN y persistencia SpectrumParams."""
from core.monitor.monitor_operating_mode import MonitorOperatingMode
from core.monitor.spectrum_params import SpectrumParams
from core.monitor.monitor_mode_profile import (
    instant_span_hz_for_source,
    max_span_hz_for_source,
    refresh_capture_and_span_limits,
    sweep_timeout_sec,
)
from core.monitor.spectrum_params_io import params_from_dict, params_to_dict


def test_apply_span_mode_full_and_zero():
    params = SpectrumParams(
        manual_span_hz=5_000_000.0,
        max_span_hz=20_000_000.0,
        capture_mode="iq",
    )
    params.span_mode = "full"
    params.apply_span_mode()
    assert params.span_hz == 20_000_000.0

    params.span_mode = "zero"
    params.apply_span_mode()
    assert params.span_hz == 0.0
    assert params.sample_rate_hz == 2_000_000.0


def test_apply_span_mode_last():
    params = SpectrumParams(
        manual_span_hz=8_000_000.0,
        last_span_hz=12_000_000.0,
        max_span_hz=20_000_000.0,
        capture_mode="iq",
    )
    params.span_mode = "last"
    params.apply_span_mode()
    assert params.span_hz == 12_000_000.0


def test_remember_span_before_mode_change():
    params = SpectrumParams(manual_span_hz=6_000_000.0, span_mode="manual")
    params.apply_span_mode()
    params.remember_span_before_mode_change()
    assert params.last_span_hz == 6_000_000.0


def test_params_roundtrip():
    base = SpectrumParams(
        center_freq_hz=90_900_000.0,
        manual_span_hz=10_000_000.0,
        span_mode="manual",
        lna_gain_db=16,
        freq_readout="fc",
    )
    refresh_capture_and_span_limits(base)
    data = params_to_dict(base)
    restored = params_from_dict(data)
    assert restored.center_freq_hz == 90_900_000.0
    assert restored.manual_span_hz == 10_000_000.0
    assert restored.span_mode == "manual"
    assert restored.lna_gain_db == 16


def test_digital_params_roundtrip():
    base = SpectrumParams(
        demod_mode="dig",
        digital_analysis_enabled=True,
        digital_profile="shure_digital",
        digital_symbol_rate_hz=500_000.0,
        digital_mod_order=4,
    )
    data = params_to_dict(base)
    restored = params_from_dict(data, base=SpectrumParams())
    assert restored.digital_profile == "shure_digital"
    assert restored.digital_symbol_rate_hz == 500_000.0
    assert restored.digital_mod_order == 4
    assert restored.digital_analysis_enabled is True


def test_max_span_sdr_limited_to_instant_bw():
    instant = instant_span_hz_for_source("hackrf")
    assert instant == 20_000_000.0
    sdr_max = max_span_hz_for_source(
        "hackrf",
        operating_mode=MonitorOperatingMode.SDR.value,
        center_freq_hz=100_000_000.0,
    )
    assert sdr_max == 20_000_000.0


def test_max_span_analyzer_wider_at_center():
    analyzer_max = max_span_hz_for_source(
        "hackrf",
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        center_freq_hz=100_000_000.0,
    )
    assert analyzer_max > 20_000_000.0
    assert analyzer_max == 2 * (100_000_000.0 - 1_000_000.0)


def test_refresh_capture_sweep_when_span_exceeds_instant():
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        center_freq_hz=100_000_000.0,
        manual_span_hz=50_000_000.0,
        span_mode="manual",
        source_id="hackrf",
    )
    refresh_capture_and_span_limits(params)
    assert params.capture_mode == "sweep"
    assert params.span_hz == 50_000_000.0


def test_refresh_capture_iq_in_sdr_mode():
    params = SpectrumParams(
        operating_mode=MonitorOperatingMode.SDR.value,
        manual_span_hz=10_000_000.0,
        span_mode="manual",
        source_id="hackrf",
    )
    refresh_capture_and_span_limits(params)
    assert params.capture_mode == "iq"
    assert params.manual_span_hz <= 20_000_000.0


def test_status_strip_default_visibility():
    """Franja inferior (indicadores azules) — valores por defecto de fábrica."""
    p = SpectrumParams()
    assert p.status_show_start is True
    assert p.status_show_center is True
    assert p.status_show_stop is True
    assert p.status_show_step is False
    assert p.status_show_readout is True
    assert p.status_show_span is True
    assert p.status_show_rbw is False
    assert p.status_show_vbw is False
    assert p.status_show_sweep is False
    assert p.status_show_trace is True
    assert p.status_show_detector is True
    assert p.status_show_lna is True
    assert p.status_show_preamp is True
    assert p.status_show_vga is True
    assert p.status_show_capture is False
    assert p.status_show_fps is False


def test_status_strip_visibility_roundtrip():
    base = SpectrumParams(
        status_show_rbw=False,
        status_show_vbw=False,
        status_show_sweep=False,
        status_show_trace=False,
        status_show_detector=False,
        status_show_start=False,
    )
    data = params_to_dict(base)
    restored = params_from_dict(data)
    assert restored.status_show_rbw is False
    assert restored.status_show_vbw is False
    assert restored.status_show_sweep is False
    assert restored.status_show_trace is False
    assert restored.status_show_detector is False
    assert restored.status_show_start is False


def test_sweep_timeout_scales_with_span():
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        manual_span_hz=100_000_000.0,
        span_mode="manual",
        capture_mode="sweep",
    )
    params.apply_span_mode()
    t = sweep_timeout_sec(params)
    assert t >= 12.0


def test_radio_audio_params_roundtrip():
    base = SpectrumParams(
        operating_mode=MonitorOperatingMode.SDR.value,
        audio_muted=True,
        audio_volume=0.42,
        squelch_enabled=True,
        squelch_db=-18.5,
        demod_wfm_stereo=True,
        demod_wfm_rds=False,
        demod_wfm_lowpass=True,
        show_demod_bandwidth=True,
    )
    data = params_to_dict(base)
    restored = params_from_dict(data, base=SpectrumParams())
    assert restored.audio_muted is True
    assert abs(restored.audio_volume - 0.42) < 0.001
    assert restored.squelch_enabled is True
    assert abs(restored.squelch_db - (-18.5)) < 0.01
    assert restored.demod_wfm_stereo is True
    assert restored.demod_wfm_rds is False


def test_analyzer_mode_params_roundtrip():
    base = SpectrumParams(
        operating_mode=MonitorOperatingMode.SPECTRUM.value,
        ref_level_dbm=-30.0,
        lna_gain_db=24,
        vga_gain_db=20,
        span_mode="manual",
        manual_span_hz=40_000_000.0,
    )
    refresh_capture_and_span_limits(base)
    data = params_to_dict(base)
    restored = params_from_dict(data, base=SpectrumParams())
    assert restored.operating_mode == MonitorOperatingMode.SPECTRUM.value
    assert restored.ref_level_dbm == -30.0
    assert restored.lna_gain_db == 24
    assert restored.manual_span_hz == 40_000_000.0
