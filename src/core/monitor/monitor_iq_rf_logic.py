"""Parches RF modo IQ — sample rate (Bandwidth) y filtro FI HackRF (SDR++)."""
from __future__ import annotations

from core.monitor.hackrf_baseband import (
    default_baseband_filter_for_sample_rate,
    snap_hackrf_baseband_filter_bw,
)
from core.monitor.spectrum_params import SpectrumParams


def patch_baseband_filter_auto(params: SpectrumParams, *, enabled: bool) -> SpectrumParams:
    updated = params.copy()
    updated.baseband_filter_auto = bool(enabled)
    if updated.baseband_filter_auto:
        updated.sync_baseband_filter_bw()
    return updated


def patch_baseband_filter_hz(params: SpectrumParams, bandwidth_hz: float) -> SpectrumParams:
    updated = params.copy()
    updated.baseband_filter_auto = False
    updated.baseband_filter_bw_hz = float(snap_hackrf_baseband_filter_bw(bandwidth_hz))
    return updated


def ensure_baseband_filter_valid(params: SpectrumParams) -> None:
    """Tras cambiar SR, acota filtro manual al sample rate."""
    if params.baseband_filter_auto:
        params.baseband_filter_bw_hz = float(
            default_baseband_filter_for_sample_rate(params.sample_rate_hz)
        )
        return
    snapped = float(snap_hackrf_baseband_filter_bw(params.baseband_filter_bw_hz))
    max_bb = float(default_baseband_filter_for_sample_rate(params.sample_rate_hz))
    if snapped > max_bb:
        snapped = max_bb
    params.baseband_filter_bw_hz = snapped
