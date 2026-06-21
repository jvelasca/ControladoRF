"""Botón FC/F estilo SDR++ (diana = centro fijo, flechas = F móvil)."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QToolButton, QWidget

from i18n.json_translation import tr

_ICON_PX = 14


def _make_fc_icon(size: int = _ICON_PX) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    cx, cy = size // 2, size // 2
    r = max(2, size // 2 - 2)
    p.setPen(QPen(QColor(100, 190, 255), 1.5))
    p.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)
    p.drawLine(cx - r + 1, cy, cx + r - 1, cy)
    p.drawLine(cx, cy - r + 1, cx, cy + r - 1)
    p.end()
    return QIcon(pix)


def _make_f_icon(size: int = _ICON_PX) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    cy = size // 2
    p.setPen(QPen(QColor(255, 170, 70), 1.5))
    p.drawLine(2, cy, size - 2, cy)
    p.drawLine(2, cy, 5, cy - 3)
    p.drawLine(2, cy, 5, cy + 3)
    p.drawLine(size - 2, cy, size - 5, cy - 3)
    p.drawLine(size - 2, cy, size - 5, cy + 3)
    p.end()
    return QIcon(pix)


class MonitorFreqModeButton(QToolButton):
    """Alterna FC ↔ F; icono y color según modo."""

    mode_changed = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorFreqModeBtn")
        self.setCheckable(False)
        self.setAutoRaise(False)
        self.setFixedSize(20, 22)
        self.setIconSize(QSize(_ICON_PX, _ICON_PX))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._mode = "fc"
        self.clicked.connect(self._toggle)
        self.set_mode("fc")

    def set_mode(self, mode: str) -> None:
        self._mode = "f" if mode == "f" else "fc"
        if self._mode == "f":
            self.setIcon(_make_f_icon())
            self.setProperty("readoutMode", "f")
            self.setToolTip(tr("monitor_freq_mode_f_tip"))
        else:
            self.setIcon(_make_fc_icon())
            self.setProperty("readoutMode", "fc")
            self.setToolTip(tr("monitor_freq_mode_fc_tip"))
        self.style().unpolish(self)
        self.style().polish(self)

    def mode(self) -> str:
        return self._mode

    def _toggle(self) -> None:
        new_mode = "f" if self._mode == "fc" else "fc"
        self.set_mode(new_mode)
        self.mode_changed.emit(new_mode)
