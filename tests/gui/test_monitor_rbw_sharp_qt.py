"""Tests Qt botón F ON/OFF junto a RBW."""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_bw_sweep_controls import MonitorRbwControl

_app = QApplication.instance() or QApplication([])


def test_rbw_sharp_button_visible_in_iq() -> None:
    w = MonitorRbwControl()
    p = SpectrumParams(
        capture_mode="iq",
        operating_mode="spectrum",
        iq_trace_sharp=True,
    )
    w.set_params(p)
    _app.processEvents()
    assert w._sharp_btn.isVisible()
    assert w._sharp_btn.isChecked()
    assert "ON" in w._sharp_btn.text()


def test_rbw_sharp_button_hidden_in_sweep() -> None:
    w = MonitorRbwControl()
    p = SpectrumParams(capture_mode="sweep", operating_mode="spectrum")
    w.set_params(p)
    _app.processEvents()
    assert not w._sharp_btn.isVisible()
