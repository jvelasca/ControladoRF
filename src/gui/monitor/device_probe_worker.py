"""Descubrimiento de fuentes SDR en hilo de fondo (no bloquea Qt)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from PyQt6.QtCore import QThread, pyqtSignal

from core.monitor.device_discovery import SourceDescriptor, detect_sources
from core.monitor.sdr_setup import DeviceSetupReport, build_all_setup_reports


@dataclass
class MonitorProbeResult:
    descriptors: List[SourceDescriptor]
    setup_reports: List[DeviceSetupReport]


class MonitorDeviceProbeWorker(QThread):
    """Ejecuta detect_sources + informes de instalación fuera del hilo GUI."""

    finished_probe = pyqtSignal(object)

    def __init__(self, *, probe_backend: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._probe_backend = probe_backend

    def run(self) -> None:
        from core.monitor.hackrf_paths import ensure_hackrf_on_path

        ensure_hackrf_on_path()
        descriptors = detect_sources(probe_backend=self._probe_backend)
        reports = build_all_setup_reports(probe_python=self._probe_backend)
        self.finished_probe.emit(
            MonitorProbeResult(descriptors=descriptors, setup_reports=reports)
        )
