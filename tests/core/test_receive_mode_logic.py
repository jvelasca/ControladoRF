"""Tests modo recepción FM/AM/DIG."""
from __future__ import annotations

from core.monitor.receive_mode_logic import (
    apply_receive_mode,
    infer_digital_profile_from_freq,
    refresh_digital_profile_for_vfo,
)
from core.monitor.spectrum_params import SpectrumParams


def test_dab_detected_at_202928_mhz() -> None:
    assert infer_digital_profile_from_freq(202_928_000.0) == "dab_iii"


def test_shure_detected_in_uhf() -> None:
    assert infer_digital_profile_from_freq(550_000_000.0) == "shure_digital"


def test_apply_dig_mode_configures_dab() -> None:
    params = SpectrumParams(
        operating_mode="sdr",
        center_freq_hz=202_928_000.0,
        vfo_freq_hz=202_928_000.0,
        demod_mode="fm",
        audio_enabled=True,
    )
    updated = apply_receive_mode(params, "dig")
    assert updated.demod_mode == "dig"
    assert not updated.audio_enabled
    assert updated.digital_analysis_enabled
    assert updated.digital_profile == "dab_iii"
    assert updated.sample_rate_hz >= 2_000_000.0
    assert updated.center_freq_hz == 202_928_000.0


def test_apply_fm_disables_digital() -> None:
    params = SpectrumParams(
        operating_mode="sdr",
        demod_mode="dig",
        digital_analysis_enabled=True,
        audio_enabled=False,
    )
    updated = apply_receive_mode(params, "wfm")
    assert updated.demod_mode == "wfm"
    assert updated.audio_enabled
    assert not updated.digital_analysis_enabled


def test_vfo_change_in_dig_switches_profile() -> None:
    params = apply_receive_mode(
        SpectrumParams(
            operating_mode="sdr",
            vfo_freq_hz=202_928_000.0,
            center_freq_hz=202_928_000.0,
        ),
        "dig",
    )
    assert params.digital_profile == "dab_iii"
    params.vfo_freq_hz = 550_000_000.0
    updated = refresh_digital_profile_for_vfo(params)
    assert updated.digital_profile == "shure_digital"
