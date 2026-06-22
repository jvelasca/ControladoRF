"""Control LNA + preamplificador en toolbar Monitor."""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from core.monitor.hackrf_rx_gains import LNA_GAIN_MAX_DB
from core.monitor.monitor_freq_span_logic import patch_hackrf_amp, patch_hackrf_lna
from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_lcd_styles import apply_lcd_readout_style
from gui.monitor.monitor_numeric_control import MonitorDecimalSpinBox
from i18n.json_translation import tr


class MonitorLnaControl(QFrame):
    """Ganancia LNA (IF, 0–40 dB) + botón P (RF amp ~11 dB)."""

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorNumericControl")
        apply_lcd_readout_style(self)
        self._params = SpectrumParams()
        self._patch_callback: Optional[Callable[[SpectrumParams], None]] = None
        self._syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)

        self._label = QLabel(tr("monitor_lcd_lna").upper(), self)
        self._label.setObjectName("MonitorLcdLabel")

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)

        self._spin = MonitorDecimalSpinBox(self)
        self._spin.setObjectName("MonitorNumericSpin")
        self._spin.setDecimals(0)
        self._spin.setRange(0, LNA_GAIN_MAX_DB)
        self._spin.setSingleStep(8)
        self._spin.setSuffix(" dB")
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._spin.setFont(font)
        self._spin.valueCommitted.connect(self._on_lna_changed)

        self._preamp_btn = QToolButton(self)
        self._preamp_btn.setObjectName("MonitorPreampBtn")
        self._preamp_btn.setCheckable(True)
        self._preamp_btn.setMinimumWidth(34)
        self._preamp_btn.setFixedHeight(22)
        self._preamp_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._preamp_btn.toggled.connect(self._on_preamp_toggled)

        row.addWidget(self._spin, stretch=1)
        row.addWidget(self._preamp_btn)

        layout.addWidget(self._label)
        layout.addLayout(row)
        self._apply_tooltips()

    def bind_patch(self, callback: Callable[[SpectrumParams], None]) -> None:
        self._patch_callback = callback

    def set_title(self, title: str) -> None:
        self._label.setText(title.upper())

    def set_params(self, params: SpectrumParams) -> None:
        self._syncing = True
        try:
            self._params = params.copy()
            self._spin.blockSignals(True)
            self._spin.setValue(float(self._params.lna_gain_db))
            self._spin.blockSignals(False)
            self._refresh_preamp_button()
        finally:
            self._syncing = False

    def _refresh_preamp_button(self) -> None:
        if self._preamp_btn is None:
            return
        enabled = bool(self._params.rf_amp_enable)
        self._preamp_btn.blockSignals(True)
        self._preamp_btn.setChecked(enabled)
        self._preamp_btn.setText(
            tr("monitor_readout_pre_on") if enabled else tr("monitor_readout_pre_off")
        )
        self._preamp_btn.blockSignals(False)

    def recargar_textos(self) -> None:
        self.set_title(tr("monitor_lcd_lna"))
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        self._spin.setToolTip(tr("monitor_tip_lna"))
        self._preamp_btn.setToolTip(tr("monitor_tip_preamp"))

    def _emit_patch(self, updated: SpectrumParams) -> None:
        self._params = updated
        self.set_params(updated)
        if self._patch_callback:
            self._patch_callback(updated)

    def _on_lna_changed(self, value: float) -> None:
        if self._syncing:
            return
        self._emit_patch(patch_hackrf_lna(self._params, int(value)))

    def _on_preamp_toggled(self, checked: bool) -> None:
        if self._syncing:
            return
        self._emit_patch(patch_hackrf_amp(self._params, enabled=bool(checked)))
