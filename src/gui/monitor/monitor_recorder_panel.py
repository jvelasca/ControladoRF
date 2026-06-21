"""Panel RECORDER — baseband IQ o audio demodulado."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.monitor.monitor_recorder import (
    build_recording_filename,
    default_recorder_directory,
    resolve_recording_path,
)
from core.monitor.spectrum_params import SpectrumParams
from i18n.json_translation import tr

_RECORD_BTN_QSS = """
QPushButton#MonitorRecordBtn {
    min-height: 28px;
    padding: 4px 12px;
    font-weight: 600;
}
QPushButton#MonitorRecordBtn:checked {
    color: #ffe8e8;
    background-color: #6a1818;
    border: 1px solid #ff5555;
}
QPushButton#MonitorRecordBtn:checked[blinkOn="true"] {
    background-color: #a02020;
}
QPushButton#MonitorRecordBtn:disabled {
    color: #888;
}
"""


class MonitorRecorderPanel(QWidget):
    """Selector de modo, ruta/nombre y botón Grabar."""

    params_changed = pyqtSignal(object)
    record_toggled = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._params = SpectrumParams()
        self._recording = False
        self._blink_on = False
        self._capture_running = False
        self._iq_mode = False
        self._demod_active = False
        self._mode_combo: Optional[QComboBox] = None
        self._folder_edit: Optional[QLineEdit] = None
        self._browse_btn: Optional[QPushButton] = None
        self._filename_edit: Optional[QLineEdit] = None
        self._path_preview: Optional[QLabel] = None
        self._record_btn: Optional[QPushButton] = None
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(500)
        self._blink_timer.timeout.connect(self._on_blink)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setContentsMargins(0, 0, 0, 0)

        self._mode_combo = QComboBox()
        self._mode_combo.addItem(tr("monitor_recorder_mode_baseband"), "baseband")
        self._mode_combo.addItem(tr("monitor_recorder_mode_audio"), "audio")
        self._mode_combo.currentIndexChanged.connect(self._emit_patch)

        folder_row = QWidget(self)
        folder_row.setMinimumWidth(0)
        folder_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        folder_layout = QHBoxLayout(folder_row)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(6)
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText(tr("monitor_recorder_folder_placeholder"))
        self._folder_edit.setMinimumWidth(0)
        self._folder_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._folder_edit.editingFinished.connect(self._emit_patch)
        self._browse_btn = QPushButton(tr("monitor_recorder_browse"))
        self._browse_btn.clicked.connect(self._browse_folder)
        folder_layout.addWidget(self._folder_edit, stretch=1)
        folder_layout.addWidget(self._browse_btn, stretch=0)

        self._filename_edit = QLineEdit()
        self._filename_edit.setPlaceholderText(tr("monitor_recorder_filename_placeholder"))
        self._filename_edit.setMinimumWidth(0)
        self._filename_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._filename_edit.editingFinished.connect(self._emit_patch)

        form.addRow(tr("monitor_recorder_mode"), self._mode_combo)
        form.addRow(tr("monitor_recorder_folder"), folder_row)
        form.addRow(tr("monitor_recorder_filename"), self._filename_edit)
        layout.addLayout(form)

        self._path_preview = QLabel()
        self._path_preview.setWordWrap(True)
        self._path_preview.setObjectName("MonitorRecorderPathPreview")
        layout.addWidget(self._path_preview)

        self._record_btn = QPushButton(tr("monitor_recorder_record"))
        self._record_btn.setObjectName("MonitorRecordBtn")
        self._record_btn.setCheckable(True)
        self._record_btn.setEnabled(False)
        self._record_btn.setStyleSheet(_RECORD_BTN_QSS)
        self._record_btn.clicked.connect(self._on_record_clicked)
        layout.addWidget(self._record_btn)

        self._refresh_path_preview()

    def set_params(self, params: SpectrumParams) -> None:
        self._params = params.copy()
        mode = (params.recorder_mode or "baseband").lower()
        if self._mode_combo is not None:
            idx = self._mode_combo.findData(mode if mode in ("baseband", "audio") else "baseband")
            if idx < 0:
                idx = 0
            self._mode_combo.blockSignals(True)
            self._mode_combo.setCurrentIndex(idx)
            self._mode_combo.blockSignals(False)
        if self._folder_edit is not None:
            self._folder_edit.blockSignals(True)
            self._folder_edit.setText(params.recorder_directory or "")
            self._folder_edit.blockSignals(False)
        if self._filename_edit is not None:
            self._filename_edit.blockSignals(True)
            self._filename_edit.setText(params.recorder_filename or "")
            self._filename_edit.blockSignals(False)
        self._refresh_path_preview()
        self._refresh_record_enabled()

    def set_recording_active(self, active: bool) -> None:
        self._recording = bool(active)
        if self._record_btn is not None:
            self._record_btn.blockSignals(True)
            self._record_btn.setChecked(self._recording)
            self._record_btn.blockSignals(False)
        self._set_controls_enabled(not self._recording)
        if self._recording:
            self._blink_timer.start()
            self._apply_record_button_label(recording=True)
        else:
            self._blink_timer.stop()
            self._blink_on = False
            if self._record_btn is not None:
                self._record_btn.setProperty("blinkOn", False)
                self._record_btn.style().unpolish(self._record_btn)
                self._record_btn.style().polish(self._record_btn)
            self._apply_record_button_label(recording=False)
            self._refresh_record_enabled()

    def resolve_output_path(self, params: SpectrumParams | None = None) -> Path:
        return resolve_recording_path(params or self._params, self._current_mode())

    def recargar_textos(self) -> None:
        if self._mode_combo is not None:
            current = self._mode_combo.currentData()
            self._mode_combo.blockSignals(True)
            self._mode_combo.clear()
            self._mode_combo.addItem(tr("monitor_recorder_mode_baseband"), "baseband")
            self._mode_combo.addItem(tr("monitor_recorder_mode_audio"), "audio")
            idx = self._mode_combo.findData(current)
            if idx >= 0:
                self._mode_combo.setCurrentIndex(idx)
            self._mode_combo.blockSignals(False)
        if self._browse_btn is not None:
            self._browse_btn.setText(tr("monitor_recorder_browse"))
        if self._folder_edit is not None:
            self._folder_edit.setPlaceholderText(tr("monitor_recorder_folder_placeholder"))
        if self._filename_edit is not None:
            self._filename_edit.setPlaceholderText(tr("monitor_recorder_filename_placeholder"))
        self._apply_record_button_label(recording=self._recording)
        self._refresh_path_preview()

    def set_capture_ready(self, *, running: bool, iq_mode: bool, demod_active: bool) -> None:
        self._capture_running = running
        self._iq_mode = iq_mode
        self._demod_active = demod_active
        self._refresh_record_enabled()

    def _current_mode(self) -> str:
        if self._mode_combo is None:
            return "baseband"
        mode = self._mode_combo.currentData()
        return str(mode or "baseband")

    def _emit_patch(self) -> None:
        if self._recording:
            return
        updated = self._params.copy()
        updated.recorder_mode = self._current_mode()
        if self._folder_edit is not None:
            updated.recorder_directory = self._folder_edit.text().strip()
        if self._filename_edit is not None:
            updated.recorder_filename = self._filename_edit.text().strip()
        self._params = updated
        self._refresh_path_preview()
        self._refresh_record_enabled()
        self.params_changed.emit(updated)

    def _browse_folder(self) -> None:
        if self._recording:
            return
        start = self._folder_edit.text().strip() if self._folder_edit else ""
        if not start:
            start = str(default_recorder_directory(self._current_mode()))
        folder = QFileDialog.getExistingDirectory(self, tr("monitor_recorder_browse"), start)
        if not folder or self._folder_edit is None:
            return
        self._folder_edit.setText(folder)
        self._emit_patch()

    def _on_record_clicked(self, checked: bool) -> None:
        self.record_toggled.emit(checked)

    def _on_blink(self) -> None:
        if not self._recording or self._record_btn is None:
            return
        self._blink_on = not self._blink_on
        self._record_btn.setProperty("blinkOn", self._blink_on)
        self._record_btn.style().unpolish(self._record_btn)
        self._record_btn.style().polish(self._record_btn)
        prefix = "● " if self._blink_on else "○ "
        self._record_btn.setText(prefix + tr("monitor_recorder_recording"))

    def _apply_record_button_label(self, *, recording: bool) -> None:
        if self._record_btn is None:
            return
        if recording:
            prefix = "● " if self._blink_on else "○ "
            self._record_btn.setText(prefix + tr("monitor_recorder_recording"))
        else:
            self._record_btn.setText(tr("monitor_recorder_record"))

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in (self._mode_combo, self._folder_edit, self._browse_btn, self._filename_edit):
            if widget is not None:
                widget.setEnabled(enabled)

    def _refresh_record_enabled(self) -> None:
        if self._record_btn is None:
            return
        if self._recording:
            self._record_btn.setEnabled(True)
            return
        mode = self._current_mode()
        ready = self._capture_running and (
            (mode == "baseband" and self._iq_mode) or (mode == "audio" and self._demod_active)
        )
        self._record_btn.setEnabled(ready)

    def _refresh_path_preview(self) -> None:
        if self._path_preview is None:
            return
        mode = self._current_mode()
        folder = self._folder_edit.text().strip() if self._folder_edit else ""
        if not folder:
            folder = str(default_recorder_directory(mode))
        name = self._filename_edit.text().strip() if self._filename_edit else ""
        if not name:
            name = build_recording_filename(self._params, mode)
        full = str(Path(folder) / Path(name).name)
        self._path_preview.setText(tr("monitor_recorder_path_preview").format(path=full))
