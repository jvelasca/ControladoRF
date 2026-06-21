"""Indicadores de rejilla vertical/horizontal (divisiones AMP y Span)."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from gui.monitor.monitor_lcd_styles import apply_lcd_readout_style


class MonitorGraticuleIndicator(QFrame):
    """Cuadros que representan divisiones de pantalla (AMP o Span)."""

    def __init__(
        self,
        *,
        orientation: str = "vertical",
        divisions: int = 10,
        caption: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._orientation = orientation
        self._divisions = divisions
        self._active_divisions = divisions
        self.setObjectName("MonitorGraticuleFrame")
        apply_lcd_readout_style(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(1)

        self._canvas = QFrame(self)
        self._canvas.setMinimumSize(18, 24 if orientation == "vertical" else 12)
        layout.addWidget(self._canvas, stretch=1)

        self._caption = QLabel(caption, self)
        self._caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._caption.setStyleSheet("color: #6a8898; font-size: 8px;")
        layout.addWidget(self._caption)

        if orientation == "vertical":
            self.setFixedSize(30, 52)
        else:
            self.setFixedSize(58, 36)

    def set_divisions(self, total: int, active: Optional[int] = None) -> None:
        self._divisions = max(1, total)
        self._active_divisions = active if active is not None else self._divisions
        self.update()

    def set_caption(self, text: str) -> None:
        self._caption.setText(text)

    def paintEvent(self, _event) -> None:
        super().paintEvent(_event)
        painter = QPainter(self)
        inner = self._canvas.geometry()
        divs = self._divisions
        active = min(self._active_divisions, divs)

        if self._orientation == "vertical":
            cell_h = max(1, inner.height() // divs)
            for i in range(divs):
                y = inner.bottom() - (i + 1) * cell_h
                filled = i < active
                color = QColor(80, 200, 120, 210 if filled else 50)
                painter.fillRect(inner.left(), y, inner.width(), cell_h - 1, color)
                painter.setPen(QPen(QColor(30, 45, 55), 1))
                painter.drawRect(inner.left(), y, inner.width(), cell_h - 1)
        else:
            cell_w = max(1, inner.width() // divs)
            for i in range(divs):
                x = inner.left() + i * cell_w
                filled = i < active
                color = QColor(100, 180, 255, 210 if filled else 50)
                painter.fillRect(x, inner.top(), cell_w - 1, inner.height(), color)
                painter.setPen(QPen(QColor(30, 45, 55), 1))
                painter.drawRect(x, inner.top(), cell_w - 1, inner.height())
        painter.end()
