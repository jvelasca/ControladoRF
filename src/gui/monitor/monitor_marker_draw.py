"""Dibujo compartido de marcadores M1–M10 en espectro y waterfall."""
from __future__ import annotations

from typing import Callable, Optional

import numpy as np
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QFont, QPainter, QPen

from core.monitor.amplitude_units import dbm_to_display, format_amplitude_value
from core.monitor.marker_analysis import estimate_snr_db, interpolate_power_db
from core.monitor.marker_bank import (
    iter_drawable_markers,
    normalize_marker_mode,
    resolve_marker_delta,
)
from core.monitor.spectrum_params import SpectrumParams


def _format_freq_hz(freq_hz: float) -> str:
    if abs(freq_hz) >= 1_000_000_000:
        return f"{freq_hz / 1_000_000_000:.3f} GHz"
    if abs(freq_hz) >= 1_000_000:
        return f"{freq_hz / 1_000_000:.3f} MHz"
    if abs(freq_hz) >= 1_000:
        return f"{freq_hz / 1_000:.1f} kHz"
    return f"{freq_hz:.0f} Hz"


def _format_freq_label_fixed(freq_hz: float) -> str:
    """Ancho estable para que la caja no se mueva al cambiar dígitos."""
    if abs(freq_hz) >= 1_000_000_000:
        return f"{freq_hz / 1_000_000_000:9.3f} GHz"
    if abs(freq_hz) >= 1_000_000:
        return f"{freq_hz / 1_000_000:9.6f} MHz"
    if abs(freq_hz) >= 1_000:
        return f"{freq_hz / 1_000:8.1f} kHz"
    return f"{freq_hz:8.0f} Hz"


def _format_level_label_fixed(level_disp: float, unit: str) -> str:
    normalized = (unit or "dBm").strip()
    if normalized in ("dBm", "dBmV"):
        return f"{level_disp:+6.0f} {normalized}"
    return f"{format_amplitude_value(level_disp, unit):>8} {normalized}"


def _marker_color(marker_color: str) -> QColor:
    color = QColor(str(marker_color))
    return color if color.isValid() else QColor("#FFC850")


def _label_bg(color: QColor) -> QColor:
    return QColor(
        max(20, color.red() // 3),
        max(20, color.green() // 3),
        max(20, color.blue() // 3),
        230,
    )


def _label_border(color: QColor) -> QColor:
    return QColor(
        min(255, color.red() // 2 + 40),
        min(255, color.green() // 2 + 40),
        min(255, color.blue() // 2 + 40),
    )


def build_marker_label(
    params: SpectrumParams,
    marker_id: int,
    marker,
    freq_hz: float,
    *,
    freqs: np.ndarray | None,
    power: np.ndarray | None,
    live_measurements: bool = True,
) -> str:
    unit = params.amplitude_unit
    parts: list[str] = [f"M{marker_id}"]
    level_db: float | None = None
    if live_measurements and freqs is not None and power is not None:
        level_db = interpolate_power_db(freqs, power, freq_hz)
    mode = normalize_marker_mode(marker.mode)
    if mode == "delta":
        parts.append(f"Δ→M{int(marker.ref_marker_id)}")
    if marker.show_freq:
        if mode == "delta":
            parts.append(f"Δ {_format_freq_label_fixed(float(marker.freq_hz))}")
        else:
            parts.append(_format_freq_label_fixed(freq_hz))
    if live_measurements and marker.show_level and level_db is not None:
        level_disp = dbm_to_display(level_db, unit, ref_offset_db=params.ref_offset_db)
        parts.append(_format_level_label_fixed(level_disp, unit))
    if live_measurements and marker.show_snr and level_db is not None and power is not None:
        snr = estimate_snr_db(power, level_db)
        if snr is not None:
            parts.append(f"S/R {snr:+5.1f} dB")
    if live_measurements and mode == "delta":
        delta_f, delta_level = resolve_marker_delta(
            params,
            marker_id,
            freqs=freqs,
            power=power,
        )
        if delta_f is not None:
            parts.append(f"ΔF {_format_freq_label_fixed(delta_f)}")
        if delta_level is not None:
            parts.append(f"Δ {delta_level:+6.1f} dB")
    return " · ".join(parts)


_MARKER_DRAG_HANDLE_W = 16


def _draw_drag_handle(
    painter: QPainter,
    handle: QRect,
    color: QColor,
    *,
    active: bool,
) -> None:
    """Icono de agarre (⇔) en el borde de la etiqueta — indica arrastre horizontal."""
    bg = QColor(
        min(255, color.red() // 2 + 30),
        min(255, color.green() // 2 + 30),
        min(255, color.blue() // 2 + 30),
        200 if active else 160,
    )
    painter.fillRect(handle, bg)
    painter.setPen(QPen(_label_border(color), 1))
    painter.drawRect(handle)
    icon_color = color.lighter(145 if active else 125)
    painter.setPen(QPen(icon_color, 1))
    painter.setFont(QFont("Segoe UI Symbol", 9, QFont.Weight.Bold if active else QFont.Weight.Normal))
    painter.drawText(handle, Qt.AlignmentFlag.AlignCenter, "⇔")


def draw_f_tune_indicator(
    painter: QPainter,
    plot: QRect,
    params: SpectrumParams,
    *,
    freqs: np.ndarray | None = None,
    power: np.ndarray | None = None,
    freq_to_x: Callable[[float, QRect], int],
) -> None:
    """Línea F móvil en el espectro (modo sintonía — naranja)."""
    if params.freq_readout != "f":
        return
    tune_hz = float(params.selected_freq_hz)
    if tune_hz <= 0.0:
        return
    fx = freq_to_x(tune_hz, plot)
    color = QColor(255, 170, 70)
    painter.setPen(QPen(color, 2))
    painter.drawLine(fx, plot.top(), fx, plot.bottom())

    unit = params.amplitude_unit
    parts = ["F", _format_freq_hz(tune_hz)]
    if freqs is not None and power is not None:
        level_db = interpolate_power_db(freqs, power, tune_hz)
        if level_db is not None:
            level_disp = dbm_to_display(level_db, unit, ref_offset_db=params.ref_offset_db)
            parts.append(format_amplitude_value(level_disp, unit))

    label = " · ".join(parts)
    painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
    fm = painter.fontMetrics()
    text_w = fm.horizontalAdvance(label)
    text_h = fm.height()
    label_x = max(plot.left() + 2, min(fx - text_w // 2, plot.right() - text_w - 2))
    label_y = plot.top() + text_h + 4
    rect = QRect(label_x - 5, label_y - text_h - 2, text_w + 10, text_h + 6)
    painter.fillRect(rect, QColor(96, 56, 24, 230))
    painter.setPen(QPen(QColor(180, 110, 50), 1))
    painter.drawRect(rect)
    painter.setPen(color.lighter(120))
    painter.drawText(label_x, label_y, label)


def draw_fc_center_indicator(
    painter: QPainter,
    plot: QRect,
    params: SpectrumParams,
    *,
    freqs: np.ndarray | None = None,
    power: np.ndarray | None = None,
) -> None:
    """Línea FC fija en el centro del gráfico (modo centro — el espectro se desplaza)."""
    if params.freq_readout != "fc":
        return
    fx = plot.left() + plot.width() // 2
    color = QColor(100, 190, 255)
    painter.setPen(QPen(color, 2))
    painter.drawLine(fx, plot.top(), fx, plot.bottom())

    center_hz = float(params.center_freq_hz)
    unit = params.amplitude_unit
    parts = ["FC", _format_freq_hz(center_hz)]
    if freqs is not None and power is not None:
        level_db = interpolate_power_db(freqs, power, center_hz)
        if level_db is not None:
            level_disp = dbm_to_display(level_db, unit, ref_offset_db=params.ref_offset_db)
            parts.append(format_amplitude_value(level_disp, unit))

    label = " · ".join(parts)
    painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
    fm = painter.fontMetrics()
    text_w = fm.horizontalAdvance(label)
    text_h = fm.height()
    label_x = max(plot.left() + 2, min(fx - text_w // 2, plot.right() - text_w - 2))
    label_y = plot.top() + text_h + 4
    rect = QRect(label_x - 5, label_y - text_h - 2, text_w + 10, text_h + 6)
    painter.fillRect(rect, QColor(30, 64, 96, 230))
    painter.setPen(QPen(QColor(58, 112, 144), 1))
    painter.drawRect(rect)
    painter.setPen(color.lighter(120))
    painter.drawText(label_x, label_y, label)


def draw_markers_on_plot(
    painter: QPainter,
    plot: QRect,
    params: SpectrumParams,
    *,
    freqs: np.ndarray | None,
    power: np.ndarray | None,
    freq_to_x: Callable[[float, QRect], int],
    draw_labels: bool = True,
    active_label_rect: Optional[list[QRect | None]] = None,
    label_hit_regions: Optional[list[tuple[int, QRect, QRect]]] = None,
    show_drag_handles: bool = False,
    live_measurements: bool = True,
    allow_peak_search: bool = True,
) -> None:
    """Pinta líneas verticales y etiquetas del banco de marcadores."""
    if active_label_rect is not None:
        active_label_rect.clear()
        active_label_rect.append(None)
    if label_hit_regions is not None:
        label_hit_regions.clear()

    start, stop = plot.left(), plot.right()
    plot_start_hz = None
    plot_stop_hz = None
    if freqs is not None and len(freqs) >= 2:
        from core.monitor.spectrum_plot_mapping import plot_freq_bounds

        plot_start_hz, plot_stop_hz = plot_freq_bounds(params, freqs)

    markers = list(
        iter_drawable_markers(
            params,
            freqs=freqs,
            power=power,
            allow_peak_search=allow_peak_search,
        )
    )
    active_id = int(params.active_marker_id)
    marker_positions: dict[int, tuple[int, QColor]] = {}

    for marker_id, marker, freq_hz in markers:
        color = _marker_color(marker.color)
        if plot_start_hz is not None and plot_stop_hz is not None:
            if freq_hz < plot_start_hz - 1.0 or freq_hz > plot_stop_hz + 1.0:
                continue
        fx = freq_to_x(freq_hz, plot)
        if fx < start or fx > stop:
            continue
        marker_positions[marker_id] = (fx, _marker_color(marker.color))
        width = 2 if marker_id == active_id else 1
        if marker.show_line:
            painter.setPen(QPen(color, width))
            painter.drawLine(fx, plot.top(), fx, plot.bottom())
        if not draw_labels:
            continue
        label = build_marker_label(
            params,
            marker_id,
            marker,
            freq_hz,
            freqs=freqs,
            power=power,
            live_measurements=live_measurements,
        )
        if not label:
            continue
        painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold if marker_id == active_id else QFont.Weight.Normal))
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(label)
        text_h = fm.height()
        row = (marker_id - 1) % 3
        label_y = plot.top() + text_h + 4 + row * (text_h + 4)
        pad_x = 5
        pad_y = 2
        body_w = text_w + pad_x * 2
        body_h = text_h + pad_y * 2
        handle_w = _MARKER_DRAG_HANDLE_W if show_drag_handles else 0
        total_w = body_w + handle_w
        # Anclar borde izquierdo en la línea del marcador (no centrar — evita vibración).
        label_x = min(max(fx + 3, plot.left() + 2), plot.right() - total_w - 2)
        rect = QRect(label_x, label_y - text_h - pad_y, total_w, body_h)
        handle_rect = QRect(rect.left(), rect.top(), handle_w, rect.height()) if handle_w else QRect()
        body_rect = QRect(rect.left() + handle_w, rect.top(), body_w, rect.height())
        if show_drag_handles and handle_w > 0:
            _draw_drag_handle(painter, handle_rect, color, active=marker_id == active_id)
        painter.fillRect(body_rect, _label_bg(color))
        painter.setPen(QPen(_label_border(color), 1))
        if handle_w > 0:
            painter.drawRect(body_rect)
            painter.drawLine(body_rect.left(), body_rect.top(), body_rect.left(), body_rect.bottom())
        else:
            painter.drawRect(rect)
        painter.setPen(color.lighter(120))
        painter.drawText(body_rect.left() + pad_x, label_y, label)
        if label_hit_regions is not None:
            label_hit_regions.append((marker_id, rect, handle_rect if handle_w else body_rect))
        if marker_id == active_id and active_label_rect is not None:
            active_label_rect[0] = body_rect if handle_w else rect

    link_y = plot.top() + int(plot.height() * 0.72)
    for marker_id, marker, _freq_hz in markers:
        if normalize_marker_mode(marker.mode) != "delta":
            continue
        ref_id = int(marker.ref_marker_id)
        if ref_id == marker_id:
            continue
        ref_pos = marker_positions.get(ref_id)
        delta_pos = marker_positions.get(marker_id)
        if ref_pos is None or delta_pos is None:
            continue
        ref_x, ref_color = ref_pos
        delta_x, delta_color = delta_pos
        link_color = QColor(
            (ref_color.red() + delta_color.red()) // 2,
            (ref_color.green() + delta_color.green()) // 2,
            (ref_color.blue() + delta_color.blue()) // 2,
            180,
        )
        painter.setPen(QPen(link_color, 1, Qt.PenStyle.DashLine))
        painter.drawLine(ref_x, link_y, delta_x, link_y)
