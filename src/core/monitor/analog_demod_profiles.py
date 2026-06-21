"""Perfiles de demodulación analógica AM / NFM / WFM / DSB (valores por defecto editables)."""
from __future__ import annotations

from dataclasses import dataclass

from core.monitor.spectrum_params import SpectrumParams

ANALOG_RECEIVE_MODES: tuple[str, ...] = ("am", "nfm", "wfm", "dsb")
DEEMPHASIS_CHOICES: tuple[str, ...] = ("none", "50us", "75us")


@dataclass(frozen=True)
class AnalogDemodDefaults:
    demod_bandwidth_hz: float
    demod_snap_interval: float
    demod_deemphasis: str = "none"
    demod_noise_blanker_db: float = 0.0
    demod_agc_attack: float = 50.0
    demod_agc_decay: float = 5.0


ANALOG_DEMOD_DEFAULTS: dict[str, AnalogDemodDefaults] = {
    "am": AnalogDemodDefaults(demod_bandwidth_hz=1_000.0, demod_snap_interval=1_000.0),
    "nfm": AnalogDemodDefaults(
        demod_bandwidth_hz=12_500.0,
        demod_snap_interval=2_500.0,
        demod_deemphasis="none",
    ),
    "wfm": AnalogDemodDefaults(
        demod_bandwidth_hz=200_000.0,
        demod_snap_interval=100_000.0,
        demod_deemphasis="50us",
        demod_noise_blanker_db=8.0,
    ),
    "dsb": AnalogDemodDefaults(
        demod_bandwidth_hz=4_600.0,
        demod_snap_interval=100.0,
        demod_noise_blanker_db=1.0,
        demod_agc_attack=50.0,
        demod_agc_decay=5.0,
    ),
}


def normalize_analog_demod_mode(mode: str | None) -> str:
    """Normaliza modo de recepción; ``fm`` legacy → ``wfm``."""
    normalized = (mode or "wfm").lower()
    if normalized == "fm":
        return "wfm"
    return normalized


def deemphasis_tau_sec(choice: str | None) -> float | None:
    key = (choice or "none").lower()
    if key == "50us":
        return 50e-6
    if key == "75us":
        return 75e-6
    return None


def apply_analog_demod_defaults(params: SpectrumParams, mode: str) -> SpectrumParams:
    """Aplica valores predefinidos del perfil (bandwidth, snap, de-emphasis, AGC…)."""
    key = normalize_analog_demod_mode(mode)
    defaults = ANALOG_DEMOD_DEFAULTS.get(key)
    if defaults is None:
        return params.copy()
    updated = params.copy()
    updated.demod_mode = key
    updated.demod_bandwidth_hz = defaults.demod_bandwidth_hz
    updated.demod_snap_interval = defaults.demod_snap_interval
    updated.demod_deemphasis = defaults.demod_deemphasis
    updated.demod_noise_blanker_db = defaults.demod_noise_blanker_db
    updated.demod_agc_attack = defaults.demod_agc_attack
    updated.demod_agc_decay = defaults.demod_agc_decay
    return updated


def mode_shows_deemphasis(mode: str) -> bool:
    return normalize_analog_demod_mode(mode) in ("nfm", "wfm")


def mode_shows_dsb_controls(mode: str) -> bool:
    return normalize_analog_demod_mode(mode) == "dsb"


def mode_shows_wfm_if_controls(mode: str) -> bool:
    return normalize_analog_demod_mode(mode) == "wfm"


def snap_vfo_freq_hz(freq_hz: float, interval_hz: float) -> float:
    """Alinea el VFO a la rejilla de paso (Snap) en Hz."""
    interval = max(1.0, float(interval_hz))
    return round(float(freq_hz) / interval) * interval


@dataclass(frozen=True)
class DemodUiLimits:
    bw_min_hz: int
    bw_max_hz: int
    bw_step_hz: int
    snap_min_hz: int
    snap_max_hz: int
    snap_step_hz: int


def demod_ui_limits(mode: str) -> DemodUiLimits:
    """Rangos y pasos del panel RADIO según modo de recepción."""
    key = normalize_analog_demod_mode(mode)
    if key == "wfm":
        return DemodUiLimits(
            bw_min_hz=100_000,
            bw_max_hz=250_000,
            bw_step_hz=25_000,
            snap_min_hz=25_000,
            snap_max_hz=200_000,
            snap_step_hz=25_000,
        )
    if key == "nfm":
        return DemodUiLimits(
            bw_min_hz=6_000,
            bw_max_hz=25_000,
            bw_step_hz=1_000,
            snap_min_hz=1_000,
            snap_max_hz=25_000,
            snap_step_hz=1_000,
        )
    if key == "am":
        return DemodUiLimits(
            bw_min_hz=3_000,
            bw_max_hz=10_000,
            bw_step_hz=500,
            snap_min_hz=500,
            snap_max_hz=10_000,
            snap_step_hz=500,
        )
    return DemodUiLimits(
        bw_min_hz=1_000,
        bw_max_hz=10_000,
        bw_step_hz=100,
        snap_min_hz=50,
        snap_max_hz=1_000,
        snap_step_hz=50,
    )
