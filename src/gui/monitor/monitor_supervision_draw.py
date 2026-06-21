"""Dibujo de marcas de inventario (banda ±BW/2) en espectro y waterfall."""
from __future__ import annotations

from typing import Callable, Dict, Optional, Sequence

from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygon

from core.monitor.supervision.supervision_models import ResolvedSupervisionTarget


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def draw_supervision_targets_on_plot(
    painter: QPainter,
    plot: QRect,
    targets: Sequence[ResolvedSupervisionTarget],
    *,
    freq_to_x: Callable[[float, QRect], int],
    draw_labels: bool = True,
    alarm_states: Optional[Dict[str, str]] = None,
    highlight_keys: Optional[set[str]] = None,
    highlight_pulse: bool = False,
    pulse_targets: Optional[Sequence[ResolvedSupervisionTarget]] = None,
) -> None:
    alarm_states = alarm_states or {}
    highlight_keys = highlight_keys or set()
    pulse_targets = pulse_targets or []
    if not targets or plot.width() <= 0:
        if not pulse_targets or not highlight_keys:
            return
    drawn_keys: set[str] = set()
    for target in targets:
        if not target.enabled or target.frequency_hz <= 0.0:
            continue
        drawn_keys.add(target.channel_key)
        state = alarm_states.get(target.channel_key, "ok")
        base = _color_for_alarm_state(target.color, state)
        half = target.half_bandwidth_hz
        low_hz = target.frequency_hz - half
        high_hz = target.frequency_hz + half
        x1 = freq_to_x(low_hz, plot)
        x2 = freq_to_x(high_hz, plot)
        if x2 < plot.left() or x1 > plot.right():
            continue
        x1 = max(plot.left(), min(plot.right(), x1))
        x2 = max(plot.left(), min(plot.right(), x2))
        if x2 <= x1:
            x2 = x1 + 1
        fill = QColor(base)
        fill.setAlpha(38)
        painter.fillRect(x1, plot.top(), x2 - x1, plot.height(), fill)
        center_x = freq_to_x(target.frequency_hz, plot)
        line = QPen(base.lighter(120), 1, Qt.PenStyle.SolidLine)
        painter.setPen(line)
        painter.drawLine(center_x, plot.top(), center_x, plot.bottom())
        edge = QPen(base.darker(115), 1, Qt.PenStyle.DotLine)
        painter.setPen(edge)
        painter.drawLine(x1, plot.top(), x1, plot.bottom())
        painter.drawLine(x2, plot.top(), x2, plot.bottom())
        if target.channel_key in highlight_keys and highlight_pulse:
            _draw_supervision_pulse(painter, plot, x1, x2, base)
        if draw_labels and plot.width() > 80:
            _draw_target_label(painter, plot, target, center_x, base)

    for target in pulse_targets:
        if target.channel_key in drawn_keys or target.frequency_hz <= 0.0:
            continue
        if target.channel_key not in highlight_keys or not highlight_pulse:
            continue
        base = _color_for_alarm_state(target.color, alarm_states.get(target.channel_key, "ok"))
        half = target.half_bandwidth_hz
        low_hz = target.frequency_hz - half
        high_hz = target.frequency_hz + half
        x1 = freq_to_x(low_hz, plot)
        x2 = freq_to_x(high_hz, plot)
        if x2 < plot.left() or x1 > plot.right():
            center_x = freq_to_x(target.frequency_hz, plot)
            if center_x < plot.left() or center_x > plot.right():
                continue
            x1 = max(plot.left(), center_x - 2)
            x2 = min(plot.right(), center_x + 2)
        else:
            x1 = max(plot.left(), min(plot.right(), x1))
            x2 = max(plot.left(), min(plot.right(), x2))
            if x2 <= x1:
                x2 = x1 + 1
        _draw_supervision_pulse(painter, plot, x1, x2, base)


def _draw_supervision_pulse(painter: QPainter, plot: QRect, x1: int, x2: int, base: QColor) -> None:
    pulse = QPen(QColor(255, 255, 255), 2, Qt.PenStyle.SolidLine)
    painter.setPen(pulse)
    painter.drawRect(x1 - 1, plot.top(), x2 - x1 + 2, plot.height())
    pulse_color = QColor(base)
    pulse_color.setAlpha(90)
    painter.fillRect(x1, plot.top(), x2 - x1, plot.height(), pulse_color)


def _color_for_alarm_state(default_hex: str, state: str) -> QColor:
    overrides = {
        "warning": "#FFCC00",
        "critical": "#FF3344",
        "warning_latched": "#CC9900",
        "critical_latched": "#CC2233",
    }
    hex_color = overrides.get(state, default_hex)
    color = QColor(hex_color)
    return color if color.isValid() else QColor(default_hex)


def _draw_target_label(
    painter: QPainter,
    plot: QRect,
    target: ResolvedSupervisionTarget,
    center_x: int,
    color: QColor,
) -> None:
    text = target.label.strip()
    if not text:
        return
    font = QFont("Segoe UI", 7)
    font.setBold(True)
    painter.setFont(font)
    metrics = painter.fontMetrics()
    pad_x, pad_y = 4, 2
    text_w = metrics.horizontalAdvance(text)
    box_w = min(text_w + pad_x * 2, max(48, plot.width() // 4))
    box_h = metrics.height() + pad_y * 2
    rel = _clamp01((center_x - plot.left()) / max(plot.width(), 1))
    box_x = center_x + 4
    if rel > 0.72:
        box_x = center_x - box_w - 4
    box_x = max(plot.left() + 2, min(plot.right() - box_w - 2, box_x))
    box_y = plot.top() + 4
    bg = QColor(16, 20, 28, 210)
    painter.fillRect(box_x, box_y, box_w, box_h, bg)
    painter.setPen(QPen(color, 1))
    painter.drawRect(box_x, box_y, box_w, box_h)
    painter.setPen(color.lighter(130))
    painter.drawText(
        box_x + pad_x,
        box_y + pad_y + metrics.ascent(),
        metrics.elidedText(text, Qt.TextElideMode.ElideRight, box_w - pad_x * 2),
    )


def draw_supervision_offscreen_indicators(
    painter: QPainter,
    plot: QRect,
    targets: Sequence[ResolvedSupervisionTarget],
    *,
    plot_start_hz: float,
    plot_stop_hz: float,
    highlight_keys: set[str],
    highlight_pulse: bool,
    alarm_states: Optional[Dict[str, str]] = None,
    hint_text: str = "",
) -> None:
    """Flechas parpadeantes en el borde cuando el canal resaltado queda fuera del span."""
    if not highlight_pulse or not highlight_keys or plot.width() <= 0:
        return
    alarm_states = alarm_states or {}
    left_targets: list[ResolvedSupervisionTarget] = []
    right_targets: list[ResolvedSupervisionTarget] = []
    for target in targets:
        if target.channel_key not in highlight_keys:
            continue
        if not target.enabled or target.frequency_hz <= 0.0:
            continue
        half = target.half_bandwidth_hz
        low_hz = target.frequency_hz - half
        high_hz = target.frequency_hz + half
        if high_hz < plot_start_hz:
            left_targets.append(target)
        elif low_hz > plot_stop_hz:
            right_targets.append(target)
    if left_targets:
        _draw_supervision_offscreen_arrow(
            painter,
            plot,
            left=True,
            targets=left_targets,
            alarm_states=alarm_states,
            hint_text=hint_text,
        )
    if right_targets:
        _draw_supervision_offscreen_arrow(
            painter,
            plot,
            left=False,
            targets=right_targets,
            alarm_states=alarm_states,
            hint_text=hint_text,
        )


def _draw_supervision_offscreen_arrow(
    painter: QPainter,
    plot: QRect,
    *,
    left: bool,
    targets: Sequence[ResolvedSupervisionTarget],
    alarm_states: Dict[str, str],
    hint_text: str,
) -> None:
    if not targets:
        return
    primary = targets[0]
    state = alarm_states.get(primary.channel_key, "ok")
    color = _color_for_alarm_state(primary.color, state)
    mid_y = (plot.top() + plot.bottom()) // 2
    tip_x = plot.left() + 8 if left else plot.right() - 8
    base_x = plot.left() + 24 if left else plot.right() - 24
    painter.setPen(QPen(color.lighter(120), 2))
    painter.setBrush(color)
    if left:
        tri = QPolygon(
            [
                QPoint(tip_x, mid_y),
                QPoint(base_x, mid_y - 12),
                QPoint(base_x, mid_y + 12),
            ]
        )
    else:
        tri = QPolygon(
            [
                QPoint(tip_x, mid_y),
                QPoint(base_x, mid_y - 12),
                QPoint(base_x, mid_y + 12),
            ]
        )
    painter.drawPolygon(tri)
    freq_mhz = primary.frequency_hz / 1e6
    label = primary.label.strip() or f"{freq_mhz:.3f} MHz"
    if len(targets) > 1:
        label = f"{label} +{len(targets) - 1}"
    painter.setPen(color.lighter(140))
    painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
    text_x = plot.left() + 28 if left else plot.right() - 132
    painter.drawText(text_x, mid_y - 4, label)
    if hint_text:
        painter.setFont(QFont("Segoe UI", 7))
        painter.setPen(QColor(255, 210, 120))
        hint_x = plot.left() + 28 if left else plot.right() - 148
        painter.drawText(hint_x, mid_y + 12, hint_text)
