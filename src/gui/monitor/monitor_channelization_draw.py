"""Pintado e interacción de la franja de asignaciones RF bajo el eje X."""
from __future__ import annotations

from typing import Sequence

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen

from core.rf.channelization_allocations import AllocationSegment

_SERVICE_COLORS: dict[str, QColor] = {
    "fm": QColor(70, 160, 90, 150),
    "dvb-t": QColor(60, 110, 180, 150),
    "dvb-t2": QColor(60, 110, 180, 150),
    "lte": QColor(200, 120, 40, 150),
    "5g": QColor(140, 70, 180, 150),
    "mobile": QColor(180, 140, 50, 150),
}
_DEFAULT_COLOR = QColor(100, 100, 110, 130)
STRIP_MENU_BTN_WIDTH = 22


def allocation_strip_content_rect(strip_rect: QRect, menu_btn_width: int = STRIP_MENU_BTN_WIDTH) -> QRect:
    if strip_rect.isNull() or menu_btn_width <= 0:
        return strip_rect
    width = min(menu_btn_width, max(0, strip_rect.width() - 40))
    if width <= 0:
        return strip_rect
    return strip_rect.adjusted(0, 0, -width, 0)


def allocation_service_color(service_type: str) -> QColor:
    key = (service_type or "").lower().strip()
    if key in _SERVICE_COLORS:
        return _SERVICE_COLORS[key]
    for prefix in ("dvb-t", "lte", "5g", "fm", "mobile"):
        if key.startswith(prefix):
            return _SERVICE_COLORS.get(prefix, _DEFAULT_COLOR)
    return _DEFAULT_COLOR


def draw_allocation_strip(
    painter: QPainter,
    strip_rect: QRect,
    segments: Sequence[AllocationSegment],
    *,
    plot_start_hz: float,
    plot_stop_hz: float,
    menu_btn_width: int = STRIP_MENU_BTN_WIDTH,
) -> None:
    if strip_rect.width() <= 0 or strip_rect.height() <= 0:
        return

    bg = QColor(18, 22, 28)
    border = QColor(50, 58, 68)
    painter.fillRect(strip_rect, bg)
    painter.setPen(QPen(border, 1))
    painter.drawRect(strip_rect.adjusted(0, 0, -1, -1))

    content_rect = allocation_strip_content_rect(strip_rect, menu_btn_width)
    if menu_btn_width > 0 and strip_rect.width() > menu_btn_width + 8:
        sep_x = content_rect.right()
        painter.setPen(QPen(border, 1))
        painter.drawLine(sep_x, strip_rect.top() + 1, sep_x, strip_rect.bottom() - 1)
        menu_bg = QColor(24, 28, 34)
        painter.fillRect(
            sep_x + 1,
            strip_rect.top() + 1,
            strip_rect.right() - sep_x - 1,
            strip_rect.height() - 2,
            menu_bg,
        )

    if not segments or content_rect.width() <= 0:
        return

    span = plot_stop_hz - plot_start_hz
    if span <= 0 or strip_rect.width() <= 0:
        return

    map_width = float(strip_rect.width())

    label_font = QFont("Segoe UI", 7)
    painter.setFont(label_font)
    metrics = painter.fontMetrics()
    text_color = QColor(220, 225, 230)

    for seg in segments:
        x1 = strip_rect.left() + int(
            (seg.freq_min_hz - plot_start_hz) / span * map_width
        )
        x2 = strip_rect.left() + int(
            (seg.freq_max_hz - plot_start_hz) / span * map_width
        )
        if x2 <= x1:
            x2 = x1 + 1
        block = QRect(x1, content_rect.top() + 1, x2 - x1, content_rect.height() - 2)
        block = block.intersected(content_rect)
        if block.width() <= 0:
            continue

        fill = allocation_service_color(seg.service_type)
        painter.fillRect(block, fill)
        painter.setPen(QPen(border.darker(120), 1))
        painter.drawRect(block)

        if block.width() >= 28:
            label = seg.label
            if metrics.horizontalAdvance(label) > block.width() - 4:
                label = metrics.elidedText(
                    label, Qt.TextElideMode.ElideRight, max(8, block.width() - 4)
                )
            painter.setPen(text_color)
            painter.drawText(
                block.adjusted(2, 0, -2, 0),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )


def allocation_freq_at(
    point: QPoint,
    *,
    strip_rect: QRect,
    segments: Sequence[AllocationSegment],
    plot_start_hz: float,
    plot_stop_hz: float,
) -> float | None:
    segment = allocation_segment_at(
        point,
        strip_rect=strip_rect,
        segments=segments,
        plot_start_hz=plot_start_hz,
        plot_stop_hz=plot_stop_hz,
    )
    return float(segment.center_freq_hz) if segment is not None else None


def allocation_segment_at(
    point: QPoint,
    *,
    strip_rect: QRect,
    segments: Sequence[AllocationSegment],
    plot_start_hz: float,
    plot_stop_hz: float,
) -> AllocationSegment | None:
    if not strip_rect.contains(point) or not segments:
        return None

    span = plot_stop_hz - plot_start_hz
    map_width = float(strip_rect.width())
    if span <= 0 or map_width <= 0:
        return None

    rel_x = (point.x() - strip_rect.left()) / map_width
    freq_hz = plot_start_hz + rel_x * span
    for seg in segments:
        if seg.freq_min_hz <= freq_hz <= seg.freq_max_hz:
            return seg
    return None


def draw_spectrum_exclusion_bands(
    painter: QPainter,
    plot: QRect,
    exclusions: Sequence,
    *,
    plot_start_hz: float,
    plot_stop_hz: float,
) -> None:
    if plot.width() <= 0 or plot.height() <= 0 or not exclusions:
        return
    span = plot_stop_hz - plot_start_hz
    if span <= 0:
        return
    for item in exclusions:
        f_min = float(item.freq_min_hz)
        f_max = float(item.freq_max_hz)
        if f_max < plot_start_hz or f_min > plot_stop_hz:
            continue
        x1 = plot.left() + int((f_min - plot_start_hz) / span * plot.width())
        x2 = plot.left() + int((f_max - plot_start_hz) / span * plot.width())
        if x2 <= x1:
            x2 = x1 + 1
        color = QColor(str(item.color_hex))
        if not color.isValid():
            color = QColor(192, 64, 64, 136)
        painter.fillRect(x1, plot.top(), x2 - x1, plot.height(), color)
