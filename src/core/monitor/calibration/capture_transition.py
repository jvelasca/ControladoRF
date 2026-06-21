"""Perfiles al cruzar IQ <-> barrido (solo para tests/calibracion legacy).

Ya no se aplican en ``prepare_params_for_capture``: el operador conserva RBW/SWT
manual al cambiar de modo. SPAN > BW instantaneo → hackrf_sweep (``iq_stitch_plan``).
"""
from __future__ import annotations

from dataclasses import dataclass

from core.monitor.spectrum_params import SpectrumParams


@dataclass
class _ModeProfile:
    fft_size: int
    fft_auto: bool
    rbw_hz: float
    rbw_auto: bool
    sweep_time_ms: float
    sweep_auto: bool


_iq_profile: _ModeProfile | None = None
_sweep_profile: _ModeProfile | None = None


def _snapshot_from_params(params: SpectrumParams) -> _ModeProfile:
    return _ModeProfile(
        fft_size=int(params.fft_size),
        fft_auto=bool(params.fft_auto),
        rbw_hz=float(params.rbw_hz),
        rbw_auto=bool(params.rbw_auto),
        sweep_time_ms=float(params.sweep_time_ms),
        sweep_auto=bool(params.sweep_auto),
    )


def _apply_profile(params: SpectrumParams, profile: _ModeProfile) -> None:
    params.fft_size = profile.fft_size
    params.fft_auto = profile.fft_auto
    params.rbw_hz = profile.rbw_hz
    params.rbw_auto = profile.rbw_auto
    params.sweep_time_ms = profile.sweep_time_ms
    params.sweep_auto = profile.sweep_auto


def reset_capture_profiles() -> None:
    global _iq_profile, _sweep_profile
    _iq_profile = None
    _sweep_profile = None


def snapshot_mode_profile(params: SpectrumParams, mode: str) -> None:
    global _iq_profile, _sweep_profile
    snap = _snapshot_from_params(params)
    if mode == "iq":
        _iq_profile = snap
    elif mode == "sweep":
        _sweep_profile = snap


def apply_capture_mode_profile(params: SpectrumParams, mode: str) -> None:
    """No-op en runtime: no sobrescribir RBW/SWT/FFT del operador."""
    del params, mode


def apply_capture_mode_transition(
    params: SpectrumParams,
    prev_mode: str,
    new_mode: str,
) -> None:
    if prev_mode == new_mode:
        return
    snapshot_mode_profile(params, prev_mode)
