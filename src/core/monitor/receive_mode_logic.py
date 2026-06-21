"""Modo de recepción AM / NFM / WFM / DSB / DIG — configuración unificada SDR."""
from __future__ import annotations

from core.monitor.analog_demod_profiles import (
    ANALOG_RECEIVE_MODES,
    apply_analog_demod_defaults,
    normalize_analog_demod_mode,
)
from core.monitor.digital_signal_profiles import apply_digital_profile_defaults
from core.monitor.spectrum_params import SpectrumParams

RECEIVE_MODES: tuple[str, ...] = (*ANALOG_RECEIVE_MODES, "dig")

DAB_III_FREQ_MIN_HZ = 174_000_000.0
DAB_III_FREQ_MAX_HZ = 240_000_000.0
SHURE_UHF_FREQ_MIN_HZ = 470_000_000.0
SHURE_UHF_FREQ_MAX_HZ = 702_000_000.0


def is_digital_receive_mode(params: SpectrumParams) -> bool:
    return (params.demod_mode or "wfm").lower() == "dig"


def is_analog_receive_mode(params: SpectrumParams) -> bool:
    return normalize_analog_demod_mode(params.demod_mode) in ANALOG_RECEIVE_MODES


def infer_digital_profile_from_freq(freq_hz: float) -> str:
    """Elige perfil digital según la frecuencia (p. ej. 202.928 MHz → DAB Band III)."""
    freq = float(freq_hz)
    if DAB_III_FREQ_MIN_HZ <= freq <= DAB_III_FREQ_MAX_HZ:
        return "dab_iii"
    if SHURE_UHF_FREQ_MIN_HZ <= freq <= SHURE_UHF_FREQ_MAX_HZ:
        return "shure_digital"
    return "custom"


def _active_freq_hz(params: SpectrumParams) -> float:
    if params.vfo_freq_hz > 0:
        return float(params.vfo_freq_hz)
    return float(params.center_freq_hz)


def _center_on_freq(params: SpectrumParams, freq_hz: float) -> None:
    params.vfo_freq_hz = freq_hz
    params.selected_freq_hz = freq_hz
    half = float(params.sample_rate_hz) * 0.5
    if abs(freq_hz - params.center_freq_hz) > half * 0.82:
        params.center_freq_hz = freq_hz


def apply_receive_mode(params: SpectrumParams, mode: str) -> SpectrumParams:
    """Aplica AM/NFM/WFM/DSB/DIG con efectos colaterales (audio, IQ, perfil digital)."""
    normalized = (mode or "wfm").lower()
    if normalized == "fm":
        normalized = "wfm"
    if normalized not in RECEIVE_MODES:
        normalized = "wfm"

    updated = params.copy()
    updated.demod_mode = normalized

    if normalized == "dig":
        updated.audio_enabled = False
        updated.digital_analysis_enabled = True
        updated.capture_mode = "iq"
        if abs(float(updated.vfo_freq_hz) - float(updated.center_freq_hz)) > float(updated.sample_rate_hz) * 0.25:
            updated.vfo_freq_hz = float(updated.center_freq_hz)
            updated.selected_freq_hz = float(updated.center_freq_hz)
        freq = _active_freq_hz(updated)
        profile_id = infer_digital_profile_from_freq(freq)
        updated = apply_digital_profile_defaults(updated, profile_id)
        if freq > 0:
            _center_on_freq(updated, freq)
        updated.sync_iq_display()
        return updated

    updated = apply_analog_demod_defaults(updated, normalized)
    updated.audio_enabled = True
    updated.digital_analysis_enabled = False
    return updated


def refresh_digital_profile_for_vfo(params: SpectrumParams) -> SpectrumParams:
    """En modo DIG, re-infiere perfil al mover el VFO (DAB en Band III, Shure en UHF…)."""
    if not is_digital_receive_mode(params):
        return params
    freq = _active_freq_hz(params)
    if freq <= 0:
        return params
    profile_id = infer_digital_profile_from_freq(freq)
    updated = params.copy()
    if profile_id != updated.digital_profile:
        updated = apply_digital_profile_defaults(updated, profile_id)
    _center_on_freq(updated, freq)
    updated.sync_iq_display()
    return updated
