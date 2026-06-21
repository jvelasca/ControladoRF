"""Diagrama de constelación IQ para modulaciones digitales."""
from __future__ import annotations

from typing import Optional

import numpy as np
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from core.monitor.digital_analysis_branch import DigitalAnalysisUiState
from i18n.json_translation import tr


class ConstellationWidget(QFrame):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorConstellationPlot")
        self.setMinimumHeight(160)
        self._points = np.zeros(0, dtype=np.complex64)
        self._active = False
        self._status = ""

    def set_state(self, state: DigitalAnalysisUiState | None) -> None:
        if state is None or not state.valid:
            self._points = np.zeros(0, dtype=np.complex64)
            self._active = False
            self._status = state.status if state is not None else ""
        else:
            self._points = np.asarray(state.constellation, dtype=np.complex64).reshape(-1)
            self._active = True
            self._status = state.status
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(6, 6, -6, -6)
        painter.fillRect(rect, QColor(8, 10, 14))
        cx = rect.center().x()
        cy = rect.center().y()
        radius = min(rect.width(), rect.height()) * 0.42
        grid = QPen(QColor(55, 62, 72), 1, Qt.PenStyle.DashLine)
        painter.setPen(grid)
        painter.drawLine(int(cx - radius), cy, int(cx + radius), cy)
        painter.drawLine(cx, int(cy - radius), cx, int(cy + radius))
        painter.drawEllipse(QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius))
        painter.setPen(QColor(120, 130, 145))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(rect.left() + 4, rect.top() + 12, tr("monitor_digital_constellation"))
        if not self._active:
            msg = self._status or tr("monitor_digital_idle")
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, msg)
            painter.end()
            return
        if self._points.size > 0:
            scale = radius * 0.85
            pen = QPen(QColor(90, 180, 255), 1.2)
            painter.setPen(pen)
            for z in self._points:
                x = cx + float(z.real) * scale
                y = cy - float(z.imag) * scale
                painter.drawPoint(int(x), int(y))
        painter.end()


class MonitorDigitalAnalysisPanel(QFrame):
    """Constelación + EVM/MER (PSK/QAM)."""

    welle_cli_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorDigitalAnalysisPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(4)

        self._title = QLabel(tr("monitor_digital_analysis_title"))
        self._title.setObjectName("MonitorDigitalAnalysisTitle")
        self._title.setWordWrap(True)
        layout.addWidget(self._title)

        self._plot = ConstellationWidget(self)
        layout.addWidget(self._plot)

        self._metrics = QLabel("—")
        self._metrics.setObjectName("MonitorDigitalAnalysisMetrics")
        self._metrics.setWordWrap(True)
        layout.addWidget(self._metrics)

        self._sync = QLabel("—")
        self._sync.setObjectName("MonitorDigitalAnalysisSync")
        self._sync.setWordWrap(True)
        layout.addWidget(self._sync)

        self._mer_trend = QLabel("—")
        self._mer_trend.setObjectName("MonitorDigitalAnalysisMerTrend")
        layout.addWidget(self._mer_trend)
        self._mer_history: list[float] = []

        self._hint = QLabel(tr("monitor_digital_analysis_hint"))
        self._hint.setWordWrap(True)
        self._hint.setObjectName("MonitorDigitalAnalysisHint")
        layout.addWidget(self._hint)

        self._welle_btn = QPushButton(tr("monitor_dab_welle_btn_launch"))
        self._welle_btn.setObjectName("MonitorDabWelleBtn")
        self._welle_btn.setToolTip(tr("monitor_dab_welle_btn_launch_tip"))
        self._welle_btn.clicked.connect(self.welle_cli_requested.emit)
        self._welle_btn.setVisible(False)
        layout.addWidget(self._welle_btn)

        self._welle_visible = False
        self._welle_available = False

    def set_welle_controls_visible(self, visible: bool) -> None:
        self._welle_visible = bool(visible)
        self._welle_btn.setVisible(self._welle_visible)
        if self._welle_visible:
            from core.monitor.dab_welle_backend import probe_welle_cli

            self._welle_available = probe_welle_cli().available
            self._sync_welle_button()
        elif not self._welle_available:
            self._sync_welle_button()

    def _sync_welle_button(self) -> None:
        if not self._welle_visible:
            return
        if self._welle_available:
            self._welle_btn.setText(tr("monitor_dab_welle_btn_launch"))
            self._welle_btn.setToolTip(tr("monitor_dab_welle_btn_launch_tip"))
        else:
            self._welle_btn.setText(tr("monitor_dab_welle_btn_install"))
            self._welle_btn.setToolTip(tr("monitor_dab_welle_hint"))

    def set_idle(self, *, message: str | None = None) -> None:
        self._plot.set_state(None)
        self._metrics.setText(message or tr("monitor_digital_idle"))
        self._sync.setText("—")
        self._mer_trend.setText("—")
        self._mer_history.clear()

    def update_state(self, state: DigitalAnalysisUiState) -> None:
        self._welle_available = bool(state.welle_cli_available)
        self._sync_welle_button()
        self._plot.set_state(state)
        if not state.valid:
            self._metrics.setText(state.status or tr("monitor_digital_idle"))
            self._sync.setText("—")
            self._mer_trend.setText("—")
            return
        evm = "—" if state.evm_rms_pct is None else f"{state.evm_rms_pct:.1f}%"
        mer = "—" if state.mer_db is None else f"{state.mer_db:.1f} dB"
        mer_smooth = state.mer_db_smoothed
        if mer_smooth is not None:
            self._mer_history.append(float(mer_smooth))
            if len(self._mer_history) > 60:
                self._mer_history = self._mer_history[-60:]
        sync_parts = []
        if state.carrier_locked:
            sync_parts.append(tr("monitor_digital_carrier_locked"))
        if state.timing_locked:
            sync_parts.append(tr("monitor_digital_timing_locked"))
        if state.sync_ok:
            sync_parts.append(tr("monitor_digital_sync_ok"))
        elif not sync_parts:
            sync_parts.append(tr("monitor_digital_sync_no"))
        self._sync.setText(" · ".join(sync_parts))
        if self._mer_history:
            spark = " ".join(f"{value:.0f}" for value in self._mer_history[-12:])
            self._mer_trend.setText(tr("monitor_digital_mer_trend").format(values=spark))
        else:
            self._mer_trend.setText("—")
        if state.modulation == "ofdm":
            ensemble = tr("monitor_dab_ensemble_yes") if state.dab_ensemble_detected else tr(
                "monitor_dab_ensemble_no"
            )
            sync = tr("monitor_dab_sync_ok") if state.dab_sync_ok else tr("monitor_dab_sync_no")
            block = (
                f"{state.dab_block_center_mhz:.3f} MHz"
                if state.dab_block_center_mhz is not None
                else "—"
            )
            self._metrics.setText(
                tr("monitor_dab_metrics").format(
                    sync=sync,
                    ensemble=ensemble,
                    carriers=state.dab_active_carriers,
                    block=block,
                    evm=evm,
                    mer=mer,
                )
            )
            if state.dab_ensemble_detected and not state.welle_cli_available:
                self._hint.setText(tr("monitor_dab_welle_hint"))
            else:
                self._hint.setText(tr("monitor_digital_analysis_hint"))
            return
        self._hint.setText(tr("monitor_digital_analysis_hint"))
        mer_display = mer
        if mer_smooth is not None and state.mer_db is not None:
            mer_display = f"{mer} ({mer_smooth:.1f} dB avg)"
        self._metrics.setText(
            tr("monitor_digital_metrics").format(
                mod=state.modulation.upper(),
                rate=state.symbol_rate_hz / 1e3,
                evm=evm,
                mer=mer_display,
            )
        )

    def recargar_textos(self) -> None:
        self._title.setText(tr("monitor_digital_analysis_title"))
        self._hint.setText(tr("monitor_digital_analysis_hint"))
        self._sync_welle_button()
