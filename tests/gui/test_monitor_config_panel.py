"""Tests GUI Monitor — comprobaciones PyQt6."""
import sys
import time

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication, QComboBox


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_qcombobox_bool_is_false_in_pyqt6(qapp):
    """PyQt6: bool(QComboBox()) es False — usar `is None`, no truthiness."""
    combo = QComboBox()
    assert combo is not None
    assert not combo  # noqa: B011 — documenta el comportamiento de PyQt6


def test_monitor_config_panel_populates_sources(qapp):
    from core.monitor.device_discovery import SourceDescriptor
    from gui.monitor.device_probe_worker import MonitorProbeResult
    from gui.monitor.monitor_config_panel import MonitorConfigPanel

    class Panel(MonitorConfigPanel):
        def refresh_sources_async(self, probe_backend: bool = False) -> None:
            pass

    panel = Panel("monitor", "propiedades")
    result = MonitorProbeResult(
        descriptors=[
            SourceDescriptor(
                source_id="mock",
                display_name="Simulacion",
                available=True,
                detail="mock",
                device_family="mock",
            ),
            SourceDescriptor(
                source_id="hackrf",
                display_name="HackRF One",
                available=True,
                detail="USB OK",
                device_family="hackrf",
                is_default=True,
            ),
        ],
        setup_reports=[],
    )
    panel._apply_probe_result(result)
    combo = panel._source_combo
    assert combo is not None
    assert combo.count() == 2
    assert combo.findData("hackrf") >= 0


def test_monitor_config_panel_async_probe(qapp):
    from gui.monitor.monitor_config_panel import MonitorConfigPanel

    class Panel(MonitorConfigPanel):
        def refresh_sources_async(self, probe_backend: bool = False) -> None:
            pass

    panel = Panel("monitor", "propiedades")
    MonitorConfigPanel.refresh_sources_async(panel)
    worker = panel._probe_worker
    assert worker is not None
    deadline = time.monotonic() + 12.0
    while worker.isRunning() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.05)
    qapp.processEvents()
    assert panel._source_combo is not None
    assert panel._source_combo.count() >= 1
