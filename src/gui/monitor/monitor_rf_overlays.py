"""Sliders verticales de entrada RF (P → LNA → VGA) sobre el espectro."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QMenu, QVBoxLayout, QWidget

from core.monitor.display_scale import (
    LNA_GAIN_STEPS_DB,
    VGA_GAIN_STEP_COUNT,
    VGA_GAIN_STEP_DB,
    lna_gain_from_step_index,
    lna_step_index,
    vga_gain_from_step_index,
    vga_step_index,
)
from core.monitor.monitor_freq_span_logic import patch_hackrf_amp, patch_hackrf_lna, patch_hackrf_vga
from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_discrete_vertical_slider import MonitorDiscreteVerticalSlider
from gui.monitor.monitor_spectrum_overlays import _SLIDER_QSS
from gui.monitor.monitor_status_dialogs import edit_lna_dialog, edit_vga_dialog
from i18n.json_translation import tr


class _MonitorRfSliderBase(QFrame):
    params_changed = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_SLIDER_QSS)
        self._params = SpectrumParams()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._column: MonitorDiscreteVerticalSlider | None = None

    def _patch(self, updated: SpectrumParams) -> None:
        self._params = updated
        self.set_params(updated)
        self.params_changed.emit(updated)

    def _parent_window(self) -> QWidget:
        return self.window()


def _mount_rf_column(parent: _MonitorRfSliderBase, column: MonitorDiscreteVerticalSlider) -> None:
    parent._column = column
    parent._layout.addWidget(column)


class MonitorPreampToggle(_MonitorRfSliderBase):
    """Preamplificador +14 dB — interruptor ON/OFF."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        from PyQt6.QtWidgets import QCheckBox, QLabel

        self._label = QLabel(tr("monitor_overlay_p"), self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._toggle = QCheckBox(self)
        self._toggle.setObjectName("MonitorPreampToggle")
        self._toggle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._toggle.toggled.connect(self._on_toggle)
        self._layout.addWidget(self._label)
        self._layout.addWidget(self._toggle, 0, Qt.AlignmentFlag.AlignHCenter)
        self._layout.addStretch(1)
        self._apply_tooltips()

    def recargar_textos(self) -> None:
        self._label.setText(tr("monitor_overlay_p"))
        self.set_params(self._params)
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        self.setToolTip(tr("monitor_tip_overlay_preamp"))
        self._toggle.setToolTip(tr("monitor_tip_overlay_preamp"))

    def set_params(self, params: SpectrumParams) -> None:
        self._params = params.copy()
        self._toggle.blockSignals(True)
        self._toggle.setChecked(bool(params.rf_amp_enable))
        self._toggle.setText(
            tr("monitor_readout_pre_on") if params.rf_amp_enable else tr("monitor_readout_pre_off")
        )
        self._toggle.blockSignals(False)

    def _on_toggle(self, checked: bool) -> None:
        self._toggle.setText(
            tr("monitor_readout_pre_on") if checked else tr("monitor_readout_pre_off")
        )
        self._patch(patch_hackrf_amp(self._params, enabled=checked))


class MonitorPreampSlider(_MonitorRfSliderBase):
    """Preamplificador +14 dB — dos posiciones."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        column = MonitorDiscreteVerticalSlider(
            self,
            label=tr("monitor_overlay_p"),
            slider_object_name="MonitorOverlaySliderPreamp",
            step_count=2,
        )
        _mount_rf_column(self, column)
        self._column = column
        self._column.connect_step_handler(self._on_step)
        self._column.readout_clicked.connect(self._toggle_preamp)
        self._apply_tooltips()

    def recargar_textos(self) -> None:
        self._column.set_label(tr("monitor_overlay_p"))
        self.set_params(self._params)
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        self._column.set_tooltips(tr("monitor_tip_overlay_preamp"))

    def _readout_text(self, enabled: bool) -> str:
        key = "monitor_readout_pre_on" if enabled else "monitor_readout_pre_off"
        return tr(key)

    def set_params(self, params: SpectrumParams) -> None:
        self._params = params.copy()
        self._column.set_step_index(1 if params.rf_amp_enable else 0)
        self._column.set_readout_text(self._readout_text(params.rf_amp_enable))

    def _on_step(self, index: int) -> None:
        self._patch(patch_hackrf_amp(self._params, enabled=index >= 1))

    def _toggle_preamp(self) -> None:
        self._patch(patch_hackrf_amp(self._params, enabled=not self._params.rf_amp_enable))


class MonitorLnaSlider(_MonitorRfSliderBase):
    """Ganancia LNA — pasos de 8 dB."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        column = MonitorDiscreteVerticalSlider(
            self,
            label=tr("monitor_lcd_lna"),
            slider_object_name="MonitorOverlaySliderLna",
            step_count=len(LNA_GAIN_STEPS_DB),
            tick_interval=1,
        )
        _mount_rf_column(self, column)
        self._column = column
        self._column.connect_step_handler(self._on_step)
        self._column.readout_clicked.connect(self._edit_lna)
        self._apply_tooltips()

    def recargar_textos(self) -> None:
        self._column.set_label(tr("monitor_lcd_lna"))
        self.set_params(self._params)
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        self._column.set_tooltips(tr("monitor_tip_overlay_lna"), tr("monitor_tip_status_edit_lna"))

    def set_params(self, params: SpectrumParams) -> None:
        prev = self._params
        self._params = params.copy()
        idx = lna_step_index(params.lna_gain_db)
        if idx != self._column.step_index() or int(prev.lna_gain_db) != int(params.lna_gain_db):
            self._column.set_step_index(idx)
            self._column.set_readout_text(f"{int(params.lna_gain_db)}")

    def _on_step(self, index: int) -> None:
        gain = lna_gain_from_step_index(index)
        self._patch(patch_hackrf_lna(self._params, gain))

    def _edit_lna(self) -> None:
        updated = edit_lna_dialog(self._params, parent=self._parent_window())
        if updated is not None:
            self._patch(updated)


class MonitorVgaSlider(_MonitorRfSliderBase):
    """Ganancia VGA — pasos de 2 dB."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        column = MonitorDiscreteVerticalSlider(
            self,
            label=tr("monitor_lcd_vga"),
            slider_object_name="MonitorOverlaySliderVga",
            step_count=VGA_GAIN_STEP_COUNT,
            tick_interval=4,
        )
        _mount_rf_column(self, column)
        self._column = column
        self._column.connect_step_handler(self._on_step)
        self._column.readout_clicked.connect(self._edit_vga)
        self._apply_tooltips()

    def recargar_textos(self) -> None:
        self._column.set_label(tr("monitor_lcd_vga"))
        self.set_params(self._params)
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        self._column.set_tooltips(tr("monitor_tip_overlay_vga"), tr("monitor_tip_status_edit_vga"))

    def set_params(self, params: SpectrumParams) -> None:
        prev = self._params
        self._params = params.copy()
        target_idx = vga_step_index(params.vga_gain_db)
        if (
            target_idx != self._column.step_index()
            or int(prev.vga_gain_db) != int(params.vga_gain_db)
        ):
            self._column.set_step_index(target_idx)
            self._column.set_readout_text(f"{int(params.vga_gain_db)}")

    def _on_step(self, index: int) -> None:
        gain = vga_gain_from_step_index(index)
        self._patch(patch_hackrf_vga(self._params, gain))

    def _edit_vga(self) -> None:
        updated = edit_vga_dialog(self._params, parent=self._parent_window())
        if updated is not None:
            self._patch(updated)
