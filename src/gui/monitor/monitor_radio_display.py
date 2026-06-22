"""Visualización de demodulación — osciloscopio, VU LED y nivel (modo SDR)."""
from __future__ import annotations

from typing import Optional

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.monitor.demod_branch import DemodUiState
from gui.monitor.led_meter_widget import CompactLedMeterBar
from i18n.json_translation import tr

_VU_MIN_DB = -54.0
_VU_MAX_DB = 0.0
_VU_SEGMENTS = 14


class DemodScopeWidget(QFrame):
    """Osciloscopio de la señal demodulada (banda base)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorDemodScope")
        self.setMinimumHeight(96)
        self._scope = np.zeros(0, dtype=np.float32)
        self._active = False

    def set_scope(self, samples: np.ndarray, *, active: bool) -> None:
        self._scope = np.asarray(samples, dtype=np.float32).reshape(-1)
        self._active = active
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.fillRect(rect, QColor(8, 10, 14))
        painter.setPen(QColor(90, 100, 115))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(rect.left() + 4, rect.top() + 12, tr("monitor_demod_scope"))
        if not self._active or self._scope.size < 2:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, tr("monitor_demod_idle"))
            painter.end()
            return
        mid_y = rect.center().y()
        grid = QPen(QColor(55, 62, 72), 1, Qt.PenStyle.DashLine)
        painter.setPen(grid)
        for frac in (0.25, 0.5, 0.75):
            y = rect.top() + int(frac * rect.height())
            painter.drawLine(rect.left(), y, rect.right(), y)
        painter.drawLine(rect.left(), mid_y, rect.right(), mid_y)
        trace = self._scope
        peak = float(np.max(np.abs(trace)) + 1e-9)
        norm = trace / peak
        pen = QPen(QColor(80, 200, 120), 1.2)
        painter.setPen(pen)
        n = norm.size
        step = max(1, n // max(rect.width(), 1))
        last_x = rect.left()
        last_y = mid_y
        for i in range(0, n, step):
            x = rect.left() + int(i * rect.width() / max(n - 1, 1))
            y = mid_y - int(float(norm[i]) * (rect.height() * 0.44))
            if i > 0:
                painter.drawLine(last_x, last_y, x, y)
            last_x, last_y = x, y
        painter.end()


class DemodLedVuMeterWidget(QFrame):
    """Vúmetro LED broadcast compacto (verde / naranja / rojo)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorDemodLedVu")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel(tr("monitor_demod_vu"))
        self._title.setObjectName("MonitorDemodVuTitle")
        header.addWidget(self._title)
        header.addStretch(1)
        self._peak_readout = QLabel("")
        self._peak_readout.setObjectName("MonitorDemodVuPeak")
        self._peak_readout.setFont(QFont("Consolas", 7))
        self._peak_readout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self._peak_readout)
        layout.addLayout(header)

        self._led_bar = CompactLedMeterBar(
            segments=_VU_SEGMENTS,
            height=12,
            min_db=_VU_MIN_DB,
            max_db=_VU_MAX_DB,
            mode="vu",
            parent=self,
        )
        layout.addWidget(self._led_bar)

        self._level_readout = QLabel("—")
        self._level_readout.setObjectName("MonitorDemodVuLevel")
        self._level_readout.setFont(QFont("Consolas", 7))
        self._level_readout.setMinimumHeight(14)
        layout.addWidget(self._level_readout)

        self._peak_hold_dbfs = -120.0

    def set_levels(self, *, vu_dbfs: float, peak_dbfs: float, active: bool) -> None:
        if active and peak_dbfs > self._peak_hold_dbfs:
            self._peak_hold_dbfs = peak_dbfs
        elif not active:
            self._peak_hold_dbfs = -120.0
        self._led_bar.set_level(
            vu_dbfs if active else None,
            peak_db=self._peak_hold_dbfs if active else None,
            active=active,
        )
        if not active:
            self._level_readout.setText("—")
            self._peak_readout.setText("")
        else:
            self._level_readout.setText(f"{vu_dbfs:.1f} dBFS")
            self._peak_readout.setText(f"P {self._peak_hold_dbfs:.1f}")

    def recargar_textos(self) -> None:
        self._title.setText(tr("monitor_demod_vu"))


class MonitorDemodDisplay(QFrame):
    """Osciloscopio, VU LED y nivel demodulado."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorDemodDisplay")
        self._last_squelch_open: bool | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(6)

        self._vu = DemodLedVuMeterWidget(self)
        layout.addWidget(self._vu)

        self._squelch_label = QLabel()
        self._squelch_label.setObjectName("MonitorDemodSquelchLabel")
        self._squelch_label.setMinimumHeight(18)
        layout.addWidget(self._squelch_label)

        self._rds_label = QLabel()
        self._rds_label.setObjectName("MonitorDemodRdsLabel")
        self._rds_label.setWordWrap(True)
        self._rds_label.setMinimumHeight(20)
        layout.addWidget(self._rds_label)

        self._scope = DemodScopeWidget(self)
        layout.addWidget(self._scope)

        self._status = QLabel()
        self._status.setWordWrap(True)
        self._status.setObjectName("MonitorDemodStatusLabel")
        layout.addWidget(self._status)

    def set_idle(self, *, message: str) -> None:
        self._last_squelch_open = None
        self._vu.set_levels(vu_dbfs=-120.0, peak_dbfs=-120.0, active=False)
        self._squelch_label.setText("")
        self._rds_label.setText("")
        self._scope.set_scope(np.zeros(0), active=False)
        self._status.setText(message)

    def _format_rds(self, state: DemodUiState) -> str:
        if state.rds_pi or state.rds_ps:
            parts = []
            if state.rds_pi:
                parts.append(f"PI {state.rds_pi}")
            if state.rds_ps:
                parts.append(state.rds_ps)
            return "RDS · " + " · ".join(parts)
        if state.rds_text:
            return f"RDS · {state.rds_text}"
        return tr("monitor_demod_rds_waiting")

    def update_state(self, state: DemodUiState) -> None:
        vu_active = state.level_dbfs > -90.0
        self._vu.set_levels(
            vu_dbfs=state.vu_dbfs,
            peak_dbfs=state.peak_dbfs,
            active=vu_active,
        )
        if state.squelch_open != self._last_squelch_open:
            self._last_squelch_open = state.squelch_open
            if state.squelch_open:
                self._squelch_label.setText(tr("monitor_demod_squelch_open"))
                self._squelch_label.setStyleSheet("color: #6ecf8a;")
            else:
                self._squelch_label.setText(tr("monitor_demod_squelch_closed"))
                self._squelch_label.setStyleSheet("color: #c08060;")
        scope_active = state.squelch_open and state.level_dbfs > -90.0
        rds_text = self._format_rds(state)
        if self._rds_label.text() != rds_text:
            self._rds_label.setText(rds_text)
        show_rds = state.mode == "WFM"
        self._rds_label.setVisible(show_rds)
        if show_rds:
            rds_style = (
                "color: #7eb8e8;" if (state.rds_pi or state.rds_ps) else "color: #888;"
            )
            if self._rds_label.styleSheet() != rds_style:
                self._rds_label.setStyleSheet(rds_style)
        self._scope.set_scope(state.scope, active=scope_active)
        if self._status.text() != state.status:
            self._status.setText(state.status)

    def recargar_textos(self) -> None:
        self._vu.recargar_textos()
