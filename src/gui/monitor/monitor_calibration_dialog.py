"""Ventana emergente redimensionable para el asistente de calibración."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QVBoxLayout

from gui.dialog_styles import apply_professional_dialog_style
from gui.monitor.monitor_calibration_widget import MonitorCalibrationPanel
from i18n.json_translation import tr


class MonitorCalibrationDialog(QDialog):
    """Diálogo no modal — permite ver el espectro mientras se calibra."""

    closed = pyqtSignal()

    def __init__(self, panel: MonitorCalibrationPanel, parent=None) -> None:
        super().__init__(parent)
        self._panel = panel
        self.setWindowTitle(tr("cal_wizard_window_title"))
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, True)
        self.setMinimumSize(880, 560)
        self.resize(1040, 720)
        apply_professional_dialog_style(self)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        if self._panel.parent() is not self:
            self._panel.setParent(self)
        layout.addWidget(self._panel)

    def panel(self) -> MonitorCalibrationPanel:
        return self._panel

    def closeEvent(self, event) -> None:
        self._panel.save_draft()
        self.closed.emit()
        super().closeEvent(event)
