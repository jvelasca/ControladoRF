"""Reloj de fecha/hora estilo LCD en toolbar Monitor."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QDateTime, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from gui.monitor.monitor_lcd_styles import apply_lcd_readout_style


class MonitorDateTimeReadout(QFrame):
    """Fecha y hora actualizadas cada segundo."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorLcdReadout")
        apply_lcd_readout_style(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(0)

        self._date = QLabel("", self)
        self._time = QLabel("", self)
        self._time.setObjectName("MonitorLcdDateTime")
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._time.setFont(font)
        self._date.setFont(font)
        self._date.setStyleSheet("color: #6a98b8; font-size: 10px;")

        layout.addWidget(self._date)
        layout.addWidget(self._time)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

    def _tick(self) -> None:
        now = QDateTime.currentDateTime()
        self._date.setText(now.toString("dd/MM/yyyy"))
        self._time.setText(now.toString("HH:mm:ss"))
