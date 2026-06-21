"""Avisos cuando una acción choca con el modo Analizador o SDR."""
from __future__ import annotations

import math

from dataclasses import dataclass

from core.monitor.monitor_mode_profile import (
    device_full_span_hz,
    instant_span_hz_for_source,
)
from core.monitor.monitor_operating_mode import MonitorOperatingMode
from core.monitor.spectrum_params import SpectrumParams


@dataclass(frozen=True)
class ModeRestriction:
    """Mensaje i18n y valores opcionales para .format()."""

    i18n_key: str
    max_mhz: float | None = None


def instant_span_limit_mhz(source_id: str) -> float:
    return instant_span_hz_for_source(source_id) / 1_000_000.0


def span_requires_analyzer_mode(
    params: SpectrumParams,
    requested_span_hz: float,
) -> ModeRestriction | None:
    """SPAN por encima del BW instantáneo del SDR (p. ej. > 20 MHz en HackRF)."""
    if params.operating_mode_enum() is not MonitorOperatingMode.SDR:
        return None
    limit_hz = instant_span_hz_for_source(params.source_id)
    if float(requested_span_hz) <= limit_hz + 0.5:
        return None
    return ModeRestriction(
        "monitor_mode_warn_span_analyzer",
        max_mhz=limit_hz / 1_000_000.0,
    )


def span_mode_requires_analyzer_mode(
    params: SpectrumParams,
    mode: str,
) -> ModeRestriction | None:
    """Lapso completo u otro modo de barrido amplio en perfil SDR."""
    if params.operating_mode_enum() is not MonitorOperatingMode.SDR:
        return None
    if mode != "full":
        return None
    full_hz = device_full_span_hz(params.source_id)
    instant_hz = instant_span_hz_for_source(params.source_id)
    if full_hz <= instant_hz + 1.0:
        return None
    return ModeRestriction(
        "monitor_mode_warn_full_span_analyzer",
        max_mhz=instant_hz / 1_000_000.0,
    )


def demod_requires_sdr_mode(params: SpectrumParams) -> ModeRestriction | None:
    """Demodulación, audio o recepción DIG."""
    if params.operating_mode_enum() is MonitorOperatingMode.SDR:
        return None
    return ModeRestriction("monitor_mode_warn_demod_sdr_only")


def zoom_out_requires_analyzer_mode(
    params: SpectrumParams,
    factor: float,
) -> ModeRestriction | None:
    """Zoom out del espectro que superaría el SPAN máximo del modo SDR."""
    if factor >= 1.0 or not math.isfinite(factor) or factor <= 0.0:
        return None
    from core.monitor.monitor_freq_span_logic import clamp_span_hz, display_span_hz

    current = display_span_hz(params)
    if current <= 0.0:
        return None
    target = current / factor
    if target <= float(params.max_span_hz) + 0.5:
        return None
    return span_requires_analyzer_mode(params, target)


def applied_span_clamped(
    params: SpectrumParams,
    *,
    requested_span_hz: float,
    applied_span_hz: float,
) -> ModeRestriction | None:
    """Detecta un SPAN solicitado mayor que el aplicado por restricción de modo."""
    if float(requested_span_hz) <= float(applied_span_hz) + 0.5:
        return None
    return span_requires_analyzer_mode(params, requested_span_hz)
