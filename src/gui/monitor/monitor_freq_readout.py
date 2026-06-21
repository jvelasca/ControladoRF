"""Control de frecuencia estilo SDR++ (FC / F, paso, menú contextual)."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDoubleValidator, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.monitor.display_scale import center_freq_step_hz
from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_lcd_styles import apply_lcd_readout_style
from i18n.json_translation import tr

STEP_PRESETS_HZ = (
    1_000.0,
    5_000.0,
    10_000.0,
    12_500.0,
    25_000.0,
    50_000.0,
    100_000.0,
    250_000.0,
    1_000_000.0,
)


class MonitorFreqReadout(QFrame):
    """Cuadro FC/F editable con ▲▼ y menú al pulsar."""

    params_changed = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._params = SpectrumParams()
        self._editing = False
        self.setObjectName("MonitorFreqReadout")
        apply_lcd_readout_style(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(0)

        self._label = QLabel("FC", self)
        self._label.setObjectName("MonitorLcdLabel")

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)

        self._down_btn = QPushButton("−", self)
        self._down_btn.setObjectName("MonitorLcdStepDown")
        self._down_btn.setFixedWidth(22)
        self._down_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._down_btn.clicked.connect(lambda: self._step(-1))

        self._value = QLineEdit(self)
        self._value.setObjectName("MonitorLcdValue")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value.setFrame(False)
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._value.setFont(font)
        validator = QDoubleValidator(0.0, 6000.0, 6, self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self._value.setValidator(validator)
        self._value.editingFinished.connect(self._commit_edit)
        self._value.returnPressed.connect(self._commit_edit)

        self._up_btn = QPushButton("+", self)
        self._up_btn.setObjectName("MonitorLcdStepUp")
        self._up_btn.setFixedWidth(22)
        self._up_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._up_btn.clicked.connect(lambda: self._step(1))

        row.addWidget(self._down_btn)
        row.addWidget(self._value, stretch=1)
        row.addWidget(self._up_btn)

        layout.addWidget(self._label)
        layout.addLayout(row)

    def set_params(self, params: SpectrumParams) -> None:
        self._params = params.copy()
        if self._editing:
            return
        self._label.setText(self._readout_label())
        self._value.setText(f"{self._active_freq_mhz():.6f}")

    def _readout_label(self) -> str:
        return "F" if self._params.freq_readout == "f" else "FC"

    def _active_freq_hz(self) -> float:
        if self._params.freq_readout == "f":
            return self._params.selected_freq_hz
        return self._params.center_freq_hz

    def _active_freq_mhz(self) -> float:
        return self._active_freq_hz() / 1_000_000.0

    def _step(self, direction: int) -> None:
        step = self._params.freq_step_hz or center_freq_step_hz(self._active_freq_hz())
        hz = max(0.0, self._active_freq_hz() + direction * step)
        self._apply_active_freq(hz)

    def _commit_edit(self) -> None:
        self._editing = False
        text = self._value.text().strip().replace(",", ".")
        if not text:
            self.set_params(self._params)
            return
        try:
            mhz = float(text)
        except ValueError:
            self.set_params(self._params)
            return
        self._apply_active_freq(max(0.0, mhz * 1_000_000.0))

    def _apply_active_freq(self, hz: float) -> None:
        updated = self._params.copy()
        if updated.freq_readout == "f":
            from core.monitor.marker_bank import patch_active_marker_frequency

            patch_active_marker_frequency(updated, hz)
            if updated.operating_mode_enum().demod_enabled():
                updated.vfo_freq_hz = updated.selected_freq_hz
        else:
            from core.monitor.monitor_freq_span_logic import patch_center_freq

            updated = patch_center_freq(updated, hz)
        self._emit(updated)

    def _emit(self, updated: SpectrumParams) -> None:
        self._params = updated
        self.set_params(updated)
        self.params_changed.emit(updated)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            h = max(1, self.height())
            if pos.y() < h * 0.35:
                self._step(1)
            elif pos.y() > h * 0.65:
                self._step(-1)
            else:
                self._show_menu(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def _show_menu(self, global_pos) -> None:
        menu = QMenu(self)
        readout = self._params.freq_readout
        action_fc = menu.addAction(tr("monitor_freq_menu_show_fc"))
        action_fc.setCheckable(True)
        action_fc.setChecked(readout == "fc")
        action_fc.triggered.connect(lambda: self._set_readout("fc"))

        action_f = menu.addAction(tr("monitor_freq_menu_show_f"))
        action_f.setCheckable(True)
        action_f.setChecked(readout == "f")
        action_f.triggered.connect(lambda: self._set_readout("f"))

        menu.addSeparator()

        step_menu = menu.addMenu(tr("monitor_freq_menu_step"))
        for hz in STEP_PRESETS_HZ:
            label = f"{hz / 1000:.1f} kHz" if hz < 1_000_000 else f"{hz / 1_000_000:.1f} MHz"
            act = step_menu.addAction(label)
            act.triggered.connect(lambda _c=False, s=hz: self._set_step(s))

        menu.addSeparator()

        pan_menu = menu.addMenu(tr("monitor_freq_menu_pan_mode"))
        for mode_id, key in (("center_fixed", "center_fixed"), ("pan_spectrum", "pan_spectrum")):
            act = pan_menu.addAction(tr(f"monitor_freq_pan_{key}"))
            act.setCheckable(True)
            act.setChecked(self._params.freq_pan_mode == mode_id)
            act.triggered.connect(lambda _c=False, m=mode_id: self._set_pan_mode(m))

        menu.addSeparator()
        menu.addAction(tr("monitor_freq_menu_edit_mhz"), self._edit_mhz_dialog)
        menu.addAction(tr("monitor_freq_menu_set_start"), self._set_start)
        menu.addAction(tr("monitor_freq_menu_set_stop"), self._set_stop)
        menu.addAction(tr("monitor_freq_menu_offset"), self._edit_offset)
        menu.addAction(tr("monitor_freq_menu_input_freq"), lambda: self._set_input_mode("frequency"))
        menu.addAction(tr("monitor_freq_menu_input_channel"), lambda: self._set_input_mode("channel"))

        menu.exec(global_pos)

    def _set_readout(self, mode: str) -> None:
        from core.monitor.monitor_freq_span_logic import patch_freq_readout

        self._emit(patch_freq_readout(self._params, mode))

    def _set_step(self, hz: float) -> None:
        updated = self._params.copy()
        updated.freq_step_hz = hz
        self._emit(updated)

    def _set_pan_mode(self, mode: str) -> None:
        updated = self._params.copy()
        updated.freq_pan_mode = mode
        self._emit(updated)

    def _set_start(self) -> None:
        updated = self._params.copy()
        updated.marker_start_hz = self._active_freq_hz()
        self._emit(updated)

    def _set_stop(self) -> None:
        updated = self._params.copy()
        updated.marker_stop_hz = self._active_freq_hz()
        self._emit(updated)

    def _set_input_mode(self, mode: str) -> None:
        updated = self._params.copy()
        updated.freq_input_mode = mode
        self._emit(updated)

    def _edit_offset(self) -> None:
        current_khz = self._params.freq_offset_hz / 1000.0
        value, ok = QInputDialog.getDouble(
            self,
            tr("monitor_freq_menu_offset"),
            tr("monitor_freq_offset_prompt"),
            current_khz,
            -100000.0,
            100000.0,
            3,
        )
        if ok:
            updated = self._params.copy()
            updated.freq_offset_hz = value * 1000.0
            self._emit(updated)

    def _edit_mhz_dialog(self) -> None:
        value, ok = QInputDialog.getDouble(
            self,
            tr("monitor_freq_menu_edit_mhz"),
            tr("monitor_freq_mhz_prompt"),
            self._active_freq_mhz(),
            0.0,
            6000.0,
            6,
        )
        if ok:
            self._apply_active_freq(value * 1_000_000.0)

    def recargar_textos(self) -> None:
        self.set_params(self._params)
