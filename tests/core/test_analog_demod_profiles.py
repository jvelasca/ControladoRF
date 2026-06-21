"""Tests perfiles demodulación analógica AM/NFM/WFM/DSB."""
from core.monitor.analog_demod_profiles import (
    ANALOG_DEMOD_DEFAULTS,
    apply_analog_demod_defaults,
    deemphasis_tau_sec,
    normalize_analog_demod_mode,
)
from core.monitor.receive_mode_logic import RECEIVE_MODES, apply_receive_mode, is_analog_receive_mode
from core.monitor.spectrum_params import SpectrumParams


def test_receive_modes_include_analog_variants() -> None:
    assert RECEIVE_MODES == ("am", "nfm", "wfm", "dsb", "dig")


def test_normalize_legacy_fm_to_wfm() -> None:
    assert normalize_analog_demod_mode("fm") == "wfm"


def test_apply_nfm_defaults() -> None:
    updated = apply_analog_demod_defaults(SpectrumParams(), "nfm")
    assert updated.demod_mode == "nfm"
    assert updated.demod_bandwidth_hz == 12_500.0
    assert updated.demod_snap_interval == 2_500.0
    assert updated.demod_deemphasis == "none"


def test_apply_wfm_defaults() -> None:
    updated = apply_analog_demod_defaults(SpectrumParams(), "wfm")
    assert updated.demod_bandwidth_hz == 200_000.0
    assert updated.demod_snap_interval == 100_000.0
    assert updated.demod_deemphasis == "50us"


def test_snap_vfo_freq_hz() -> None:
    from core.monitor.analog_demod_profiles import snap_vfo_freq_hz

    assert snap_vfo_freq_hz(100_325_000.0, 100_000.0) == 100_300_000.0
    assert snap_vfo_freq_hz(100_375_000.0, 100_000.0) == 100_400_000.0


def test_wfm_demod_ui_limits() -> None:
    from core.monitor.analog_demod_profiles import demod_ui_limits

    limits = demod_ui_limits("wfm")
    assert limits.bw_min_hz >= 100_000
    assert limits.snap_step_hz == 25_000


def test_apply_dsb_defaults() -> None:
    updated = apply_analog_demod_defaults(SpectrumParams(), "dsb")
    assert updated.demod_bandwidth_hz == 4_600.0
    assert updated.demod_snap_interval == 100.0
    assert updated.demod_noise_blanker_db == 1.0
    assert updated.demod_agc_attack == 50.0
    assert updated.demod_agc_decay == 5.0


def test_apply_receive_mode_wfm_enables_audio() -> None:
    params = SpectrumParams(demod_mode="dig", digital_analysis_enabled=True, audio_enabled=False)
    updated = apply_receive_mode(params, "wfm")
    assert updated.demod_mode == "wfm"
    assert updated.audio_enabled
    assert not updated.digital_analysis_enabled
    assert updated.demod_bandwidth_hz == ANALOG_DEMOD_DEFAULTS["wfm"].demod_bandwidth_hz


def test_is_analog_receive_mode() -> None:
    assert is_analog_receive_mode(SpectrumParams(demod_mode="dsb"))
    assert not is_analog_receive_mode(SpectrumParams(demod_mode="dig"))


def test_deemphasis_tau() -> None:
    assert deemphasis_tau_sec("none") is None
    assert deemphasis_tau_sec("50us") == 50e-6
