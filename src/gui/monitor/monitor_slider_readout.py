"""Lectura azul clicable bajo cada slider vertical del espectro."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QWidget


class MonitorSliderReadout(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text: str = "", *, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("MonitorOverlayReadout")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        font = QFont("Consolas", 7)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
