"""Menú SPAN (…) no debe fallar al construirse."""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication, QMenu

from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_freq_span_controls import MonitorSpanControl
from gui.monitor.monitor_span_menu import SPAN_MODES, populate_span_menu

_app = QApplication.instance() or QApplication([])


def test_populate_span_menu_builds_actions() -> None:
    menu = QMenu()
    params = SpectrumParams()
    patches: list[SpectrumParams] = []

    populate_span_menu(menu, params, patch=patches.append, parent=None)
    assert menu.actions()
    assert len([a for a in menu.actions() if not a.isSeparator()]) >= len(SPAN_MODES) + 1


def test_span_control_build_menu_does_not_crash() -> None:
    w = MonitorSpanControl()
    w.set_params(SpectrumParams())
    _app.processEvents()
    menu = QMenu()
    w._build_menu(menu)
    assert len(menu.actions()) >= len(SPAN_MODES)
