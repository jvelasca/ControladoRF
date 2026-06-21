"""Tests preset FM broadcast."""
from core.monitor.wfm_broadcast_profile import apply_fm_broadcast_preset
from core.monitor.spectrum_params import SpectrumParams


def test_fm_broadcast_preset_sets_wfm_defaults():
    params = apply_fm_broadcast_preset(SpectrumParams())
    assert params.demod_mode == "wfm"
    assert params.demod_bandwidth_hz == 200_000.0
    assert params.demod_snap_interval == 100_000.0
    assert params.demod_deemphasis == "50us"
    assert params.squelch_db == -81.0
    assert params.demod_wfm_stereo is True
    assert params.demod_wfm_rds is True
    assert params.span_hz == 2_000_000.0
    assert params.operating_mode == "sdr"
    assert params.lna_gain_db == 40
    assert params.vga_gain_db == 18
    assert params.rf_amp_enable is True
    assert params.rf_bias_tee_enable is False
    assert params.demod_iq_correction is False
    assert params.demod_iq_invert is False
    assert params.freq_offset_hz == 0.0
    assert params.demod_snap_interval == 100_000.0
    assert params.demod_noise_blanker_db == 8.0
    assert params.demod_wfm_lowpass is True


def test_fm_broadcast_preset_keeps_current_frequency():
    params = SpectrumParams(
        center_freq_hz=96_500_000.0,
        vfo_freq_hz=96_500_000.0,
        selected_freq_hz=96_500_000.0,
        freq_readout="f",
    )
    updated = apply_fm_broadcast_preset(params)
    assert abs(updated.center_freq_hz - 96_500_000.0) < 1.0
    assert abs(updated.vfo_freq_hz - 96_500_000.0) < 1.0
    assert updated.lna_gain_db == 40
    assert updated.vga_gain_db == 18
