"""Tests modos de operación del Monitor."""
from core.monitor.demod_branch import DemodBranch
from core.monitor.monitor_operating_mode import (
    MODE_CHOICES,
    MonitorOperatingMode,
    normalize_operating_mode,
)
from core.monitor.spectrum_params import SpectrumParams


def test_operating_mode_normalize():
    assert MonitorOperatingMode.normalize("sdr") is MonitorOperatingMode.SDR
    assert MonitorOperatingMode.normalize("unknown") is MonitorOperatingMode.SPECTRUM


def test_supervision_maps_to_analyzer():
    assert normalize_operating_mode("supervision") is MonitorOperatingMode.SPECTRUM


def test_mode_demod_and_supervision_flags():
    assert MonitorOperatingMode.SDR.demod_enabled()
    assert not MonitorOperatingMode.SPECTRUM.demod_enabled()
    assert MonitorOperatingMode.SPECTRUM.supervision_enabled() is False


def test_spectrum_params_apply_operating_mode_sdr():
    params = SpectrumParams(
        operating_mode="sdr",
        center_freq_hz=658_175_000.0,
        vfo_freq_hz=0.0,
    )
    params.apply_operating_mode()
    assert params.audio_enabled
    assert not params.supervision_enabled
    assert params.demod_enabled()
    assert params.vfo_freq_hz == 658_175_000.0


def test_spectrum_params_apply_operating_mode_spectrum():
    params = SpectrumParams(operating_mode="spectrum")
    params.apply_operating_mode()
    assert params.supervision_enabled
    assert not params.audio_enabled
    assert not params.demod_enabled()


def test_spectrum_params_copy_preserves_mode_fields():
    original = SpectrumParams(
        operating_mode="sdr",
        vfo_freq_hz=500_000_000.0,
        demod_mode="am",
        squelch_db=-70.0,
        freq_readout="f",
        selected_freq_hz=500_000_000.0,
    )
    original.apply_operating_mode()
    copied = original.copy()
    assert copied.operating_mode == "sdr"
    assert copied.freq_readout == "f"
    assert copied.audio_enabled


def test_demod_branch_inactive_in_spectrum_mode():
    branch = DemodBranch()
    params = SpectrumParams(operating_mode="spectrum")
    params.apply_operating_mode()
    branch.process_iq([1, 2, 3], params, sample_rate_hz=2_000_000.0)
    assert branch.last_state is None
    assert branch.status_for_params(params) is None


def test_demod_branch_active_in_sdr_mode():
    import numpy as np

    branch = DemodBranch()
    params = SpectrumParams(operating_mode="sdr", demod_mode="wfm", demod_bandwidth_hz=20_000.0)
    params.apply_operating_mode()
    samples = np.ones(128, dtype=np.complex64)
    branch.process_iq(samples, params, sample_rate_hz=2_000_000.0)
    assert branch.last_state is not None
    assert "WFM" in branch.last_state.status
    assert branch.status_for_params(params) is not None


def test_mode_choices_order():
    assert MODE_CHOICES[0] is MonitorOperatingMode.SPECTRUM
    assert len(MODE_CHOICES) == 2
