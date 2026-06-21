"""Iconos compactos del árbol de supervisión — glifo + color de estado."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF

from core.inventory_catalog import DEVICE_TYPE_OTHER
from core.monitor.supervision.supervision_tree import SupervisionRollup, TreeIconTone

ROLLUP_COLORS: dict[str, QColor] = {
    "ok": QColor("#22C55E"),
    "warning_latched": QColor("#EAB308"),
    "warning": QColor("#CA8A04"),
    "critical": QColor("#EF4444"),
}

TONE_COLORS: dict[TreeIconTone, QColor] = {
    "ok": QColor("#22C55E"),
    "comentario": QColor("#92400E"),
    "critical_pending": QColor("#EF4444"),
    "warning_pending": QColor("#EAB308"),
    "acknowledged": QColor("#CA8A04"),
    "latched_critical": QColor("#F97316"),
    "latched_warning": QColor("#EAB308"),
}

_GLYPH = QColor("#FFFFFF")
_BLINK_DIM_ALPHA = 0.35


def rollup_color(rollup: SupervisionRollup) -> QColor:
    return ROLLUP_COLORS.get(rollup, ROLLUP_COLORS["ok"])


def tone_color(tone: TreeIconTone) -> QColor:
    return TONE_COLORS.get(tone, TONE_COLORS["ok"])


def _resolve_fill(tone_or_rollup: str, *, enabled: bool, blink_dim: bool) -> QColor:
    if not enabled:
        return QColor("#9CA3AF")
    if tone_or_rollup in TONE_COLORS:
        fill = tone_color(tone_or_rollup)  # type: ignore[arg-type]
    else:
        fill = rollup_color(tone_or_rollup)  # type: ignore[arg-type]
    if blink_dim:
        fill = QColor(fill)
        fill.setAlphaF(_BLINK_DIM_ALPHA)
    return fill


@lru_cache(maxsize=1024)
def supervision_tree_icon(
    device_type: Optional[str],
    tone_or_rollup: str,
    *,
    is_group: bool = False,
    size: int = 16,
    enabled: bool = True,
    blink_dim: bool = False,
) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    fill = _resolve_fill(tone_or_rollup, enabled=enabled, blink_dim=blink_dim)
    margin = 1.0
    circle = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(fill))
    painter.drawEllipse(circle)

    inner = circle.adjusted(3.0, 3.0, -3.0, -3.0)
    painter.setPen(QPen(_GLYPH, 1.15, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if is_group:
        _draw_group_glyph(painter, inner)
    else:
        _draw_device_glyph(painter, device_type or DEVICE_TYPE_OTHER, inner)
    painter.end()
    return QIcon(pixmap)


def _draw_group_glyph(painter: QPainter, rect: QRectF) -> None:
    """Tres líneas — agrupación genérica."""
    y1 = rect.top() + rect.height() * 0.28
    y2 = rect.top() + rect.height() * 0.52
    y3 = rect.top() + rect.height() * 0.76
    x1 = rect.left() + rect.width() * 0.15
    x2 = rect.right() - rect.width() * 0.15
    for y in (y1, y2, y3):
        painter.drawLine(int(x1), int(y), int(x2), int(y))


def _draw_device_glyph(painter: QPainter, device_type: str, rect: QRectF) -> None:
    drawers = {
        "microphone": _glyph_microphone,
        "iem": _glyph_iem,
        "spectrum_manager": _glyph_spectrum,
        "antenna_accessory": _glyph_antenna,
        "charger": _glyph_charger,
        "intercom": _glyph_intercom,
    }
    drawer = drawers.get(device_type, _glyph_other)
    drawer(painter, rect)


def _glyph_microphone(painter: QPainter, rect: QRectF) -> None:
    cx = rect.center().x()
    body_w = rect.width() * 0.42
    body_h = rect.height() * 0.52
    body = QRectF(cx - body_w / 2, rect.top() + rect.height() * 0.08, body_w, body_h)
    painter.setBrush(QBrush(_GLYPH))
    painter.drawRoundedRect(body, body_w * 0.45, body_w * 0.45)
    stem_y = body.bottom()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawLine(int(cx), int(stem_y), int(cx), int(rect.bottom() - rect.height() * 0.08))
    base_w = rect.width() * 0.55
    painter.drawLine(
        int(cx - base_w / 2),
        int(rect.bottom() - rect.height() * 0.08),
        int(cx + base_w / 2),
        int(rect.bottom() - rect.height() * 0.08),
    )


def _glyph_iem(painter: QPainter, rect: QRectF) -> None:
    painter.setBrush(QBrush(_GLYPH))
    ear_r = rect.width() * 0.18
    left = QRectF(rect.left(), rect.center().y() - ear_r, ear_r * 2, ear_r * 2)
    right = QRectF(rect.right() - ear_r * 2, rect.center().y() - ear_r, ear_r * 2, ear_r * 2)
    painter.drawEllipse(left)
    painter.drawEllipse(right)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(
        QRectF(rect.left() + ear_r, rect.top(), rect.width() - ear_r * 2, rect.height() * 0.75),
        0,
        180 * 16,
    )


def _glyph_spectrum(painter: QPainter, rect: QRectF) -> None:
    painter.setBrush(QBrush(_GLYPH))
    bar_w = max(1.0, rect.width() * 0.16)
    gaps = [0.12, 0.38, 0.64]
    heights = [0.35, 0.75, 0.5]
    for offset, height in zip(gaps, heights):
        x = rect.left() + rect.width() * offset
        h = rect.height() * height
        painter.drawRect(QRectF(x, rect.bottom() - h, bar_w, h))


def _glyph_antenna(painter: QPainter, rect: QRectF) -> None:
    cx = rect.center().x()
    top_y = rect.top() + rect.height() * 0.12
    base_y = rect.bottom() - rect.height() * 0.1
    painter.drawLine(int(cx), int(base_y), int(cx), int(top_y + rect.height() * 0.22))
    tip = rect.width() * 0.34
    mid_y = top_y + rect.height() * 0.22
    painter.setBrush(QBrush(_GLYPH))
    triangle = QPolygonF(
        [
            QPointF(cx, top_y),
            QPointF(cx - tip / 2, mid_y),
            QPointF(cx + tip / 2, mid_y),
        ]
    )
    painter.drawPolygon(triangle)


def _glyph_charger(painter: QPainter, rect: QRectF) -> None:
    painter.setBrush(QBrush(_GLYPH))
    body = rect.adjusted(rect.width() * 0.22, rect.height() * 0.12, -rect.width() * 0.22, -rect.height() * 0.12)
    painter.drawRoundedRect(body, 1.5, 1.5)
    nub = QRectF(body.right() - 1.5, body.center().y() - body.height() * 0.18, body.width() * 0.18, body.height() * 0.36)
    painter.drawRect(nub)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    bolt_x = body.center().x()
    y0 = body.top() + body.height() * 0.2
    y1 = body.center().y()
    y2 = body.bottom() - body.height() * 0.2
    painter.drawLine(int(bolt_x + 1), int(y0), int(bolt_x - 2), int(y1))
    painter.drawLine(int(bolt_x - 2), int(y1), int(bolt_x + 1), int(y1))
    painter.drawLine(int(bolt_x + 1), int(y1), int(bolt_x - 2), int(y2))


def _glyph_intercom(painter: QPainter, rect: QRectF) -> None:
    painter.setBrush(QBrush(_GLYPH))
    body = rect.adjusted(rect.width() * 0.18, rect.height() * 0.18, -rect.width() * 0.18, -rect.height() * 0.28)
    painter.drawRoundedRect(body, 2.0, 2.0)
    ant_h = rect.height() * 0.18
    ant_w = body.width() * 0.12
    painter.drawRect(
        QRectF(body.center().x() - ant_w / 2, body.top() - ant_h, ant_w, ant_h)
    )


def _glyph_other(painter: QPainter, rect: QRectF) -> None:
    painter.setBrush(QBrush(_GLYPH))
    r = min(rect.width(), rect.height()) * 0.22
    painter.drawEllipse(QRectF(rect.center().x() - r, rect.center().y() - r, r * 2, r * 2))
