"""Colores de visualización del Monitor (overlay SPAN, traza, etc.)."""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QColor

from core.monitor.monitor_operating_mode import MonitorOperatingMode
from core.monitor.spectrum_params import SpectrumParams

# Analizador / espectro (tema verde coherente)
DEFAULT_SPAN_VIEWPORT_COLOR = "#186038"
DEFAULT_SPAN_VIEWPORT_HI_COLOR = "#30B068"
DEFAULT_SPAN_TRACK_COLOR = "#10161E"
DEFAULT_SPAN_HANDLE_COLOR = "#5ADC8C"
DEFAULT_TRACE_COLOR = "#00DC78"

# Modo SDR (BW ≤ 20 MHz, tema azul)
DEFAULT_SDR_SPAN_VIEWPORT_COLOR = "#1A58A0"
DEFAULT_SDR_SPAN_VIEWPORT_HI_COLOR = "#2A78C8"
DEFAULT_SDR_SPAN_TRACK_COLOR = "#121C2C"
DEFAULT_SDR_SPAN_HANDLE_COLOR = "#48C8FF"
DEFAULT_SDR_TRACE_COLOR = "#00C8FF"

DEFAULT_SPAN_VIEWPORT_ALPHA = 190
DEFAULT_SPAN_VIEWPORT_HI_ALPHA = 150


@dataclass(frozen=True)
class SpanSliderColors:
    track: QColor
    viewport_shadow: QColor
    viewport_shadow_hi: QColor
    handle: QColor


def is_sdr_display_mode(params: SpectrumParams) -> bool:
    return params.operating_mode_enum() is MonitorOperatingMode.SDR


def _parse_hex_rgb(value: str, fallback: str) -> QColor:
    raw = str(value or "").strip()
    color = QColor(raw if raw.startswith("#") else f"#{raw}")
    if not color.isValid():
        color = QColor(fallback)
    return QColor(color.red(), color.green(), color.blue())


def _with_alpha(color: QColor, alpha: int) -> QColor:
    c = QColor(color)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


def _span_color_fields(params: SpectrumParams) -> tuple[str, str, str, str, str, str]:
    if is_sdr_display_mode(params):
        return (
            params.display_sdr_span_viewport_color,
            params.display_sdr_span_viewport_hi_color,
            params.display_sdr_span_track_color,
            params.display_sdr_span_handle_color,
            DEFAULT_SDR_SPAN_VIEWPORT_COLOR,
            DEFAULT_SDR_SPAN_VIEWPORT_HI_COLOR,
        )
    return (
        params.display_span_viewport_color,
        params.display_span_viewport_hi_color,
        params.display_span_track_color,
        params.display_span_handle_color,
        DEFAULT_SPAN_VIEWPORT_COLOR,
        DEFAULT_SPAN_VIEWPORT_HI_COLOR,
    )


def span_slider_colors(params: SpectrumParams) -> SpanSliderColors:
    viewport, viewport_hi, track, handle, fb_viewport, fb_hi = _span_color_fields(params)
    track_fb = (
        DEFAULT_SDR_SPAN_TRACK_COLOR if is_sdr_display_mode(params) else DEFAULT_SPAN_TRACK_COLOR
    )
    handle_fb = (
        DEFAULT_SDR_SPAN_HANDLE_COLOR if is_sdr_display_mode(params) else DEFAULT_SPAN_HANDLE_COLOR
    )
    shadow = _with_alpha(_parse_hex_rgb(viewport, fb_viewport), DEFAULT_SPAN_VIEWPORT_ALPHA)
    shadow_hi = _with_alpha(_parse_hex_rgb(viewport_hi, fb_hi), DEFAULT_SPAN_VIEWPORT_HI_ALPHA)
    return SpanSliderColors(
        track=_parse_hex_rgb(track, track_fb),
        viewport_shadow=shadow,
        viewport_shadow_hi=shadow_hi,
        handle=_parse_hex_rgb(handle, handle_fb),
    )


def spectrum_trace_color(params: SpectrumParams) -> QColor:
    if is_sdr_display_mode(params):
        return _parse_hex_rgb(params.display_sdr_trace_color, DEFAULT_SDR_TRACE_COLOR)
    return _parse_hex_rgb(params.display_trace_color, DEFAULT_TRACE_COLOR)


def spectrum_trace_fill_color(params: SpectrumParams, *, alpha: int = 52) -> QColor:
    base = spectrum_trace_color(params)
    return _with_alpha(base, alpha)


def apply_display_color_defaults(params: SpectrumParams) -> SpectrumParams:
    updated = params.copy()
    updated.display_span_viewport_color = DEFAULT_SPAN_VIEWPORT_COLOR
    updated.display_span_viewport_hi_color = DEFAULT_SPAN_VIEWPORT_HI_COLOR
    updated.display_span_track_color = DEFAULT_SPAN_TRACK_COLOR
    updated.display_span_handle_color = DEFAULT_SPAN_HANDLE_COLOR
    updated.display_trace_color = DEFAULT_TRACE_COLOR
    return updated


def apply_display_sdr_color_defaults(params: SpectrumParams) -> SpectrumParams:
    updated = params.copy()
    updated.display_sdr_span_viewport_color = DEFAULT_SDR_SPAN_VIEWPORT_COLOR
    updated.display_sdr_span_viewport_hi_color = DEFAULT_SDR_SPAN_VIEWPORT_HI_COLOR
    updated.display_sdr_span_track_color = DEFAULT_SDR_SPAN_TRACK_COLOR
    updated.display_sdr_span_handle_color = DEFAULT_SDR_SPAN_HANDLE_COLOR
    updated.display_sdr_trace_color = DEFAULT_SDR_TRACE_COLOR
    return updated
