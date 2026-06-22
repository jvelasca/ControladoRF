"""Comprobación de actualizaciones en segundo plano (solo app empaquetada)."""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from core.app_update import UpdateCheckResult, check_for_update


class AppUpdateCheckWorker(QThread):
    finished_check = pyqtSignal(object)

    def run(self) -> None:
        self.finished_check.emit(check_for_update())
