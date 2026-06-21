"""Iconos compactos compartidos para toolbars de supervisión (REC, engranaje)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget

_TOOL_ICON_PX = 14
_REC_DOT_DIAMETER = 9


def toolbar_icon_color(widget: QWidget) -> QColor:
    return widget.palette().color(widget.foregroundRole())


def make_record_icon(*, diameter: int = _REC_DOT_DIAMETER, bright: bool = True) -> QIcon:
    px = _TOOL_ICON_PX
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    color = QColor("#ef4444" if bright else "#991b1b")
    painter.setBrush(QBrush(color))
    painter.setPen(Qt.PenStyle.NoPen)
    offset = (px - diameter) // 2
    painter.drawEllipse(offset, offset, diameter, diameter)
    painter.end()
    return QIcon(pixmap)


def make_gear_icon(size: int, color: QColor) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(color, 1.0))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    cx = cy = size / 2.0
    tooth_w = max(2, int(size * 0.11))
    tooth_h = max(3, int(size * 0.14))
    for index in range(8):
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(index * 45.0)
        painter.drawRoundedRect(-tooth_w // 2, -int(size * 0.38), tooth_w, tooth_h, 1, 1)
        painter.restore()
    painter.drawEllipse(QPointF(cx, cy), size * 0.22, size * 0.22)
    painter.drawEllipse(QPointF(cx, cy), size * 0.10, size * 0.10)
    painter.end()
    return QIcon(pixmap)
