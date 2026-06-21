"""Parches SDR — ganancia RF sin alterar SPAN."""
from core.monitor.monitor_flow_log import is_sdr_rf_gain_only_patch
from core.monitor.monitor_freq_span_logic import patch_hackrf_amp
from core.monitor.spectrum_params import SpectrumParams


def _sdr_iq_params() -> SpectrumParams:
    return SpectrumParams(
        operating_mode="sdr",
        capture_mode="iq",
        span_mode="manual",
        manual_span_hz=2_500_000.0,
        span_hz=2_500_000.0,
        sample_rate_hz=2_500_000.0,
        center_freq_hz=98_000_000.0,
        lna_gain_db=32,
        vga_gain_db=40,
        rf_amp_enable=False,
    )


def test_gain_only_detects_preamp_toggle():
    prev = _sdr_iq_params()
    updated = patch_hackrf_amp(prev, enabled=True)
    assert is_sdr_rf_gain_only_patch(prev, updated) is True


def test_gain_only_rejects_span_change():
    prev = _sdr_iq_params()
    updated = prev.copy()
    updated.manual_span_hz = 5_000_000.0
    updated.rf_amp_enable = True
    assert is_sdr_rf_gain_only_patch(prev, updated) is False
