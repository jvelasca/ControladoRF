"""Tests de la barra de herramientas contextual."""
import sys

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_toolbar_module_switch_preserves_monitor_widget(qapp):
    from gui.tool_bar import ToolBar

    tb = ToolBar()
    monitor = tb.get_monitor_toolbar()
    assert monitor is not None

    tb.set_active_module("monitor")
    assert tb.get_monitor_toolbar() is monitor

    tb.set_active_module("inventario_rf")
    assert tb.get_monitor_toolbar() is monitor

    tb.set_active_module("monitor")
    assert tb.get_monitor_toolbar() is monitor
