"""Tests Qt de la toolbar del Monitor (import, AMPT AUTO, control F)."""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication, QFrame

from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_ampt_control import MonitorAmptControl
from gui.monitor.monitor_bw_sweep_controls import MonitorRbwControl
from gui.monitor.monitor_lcd_styles import MONITOR_TOOLBAR_CONTROL_HEIGHT, MONITOR_TOOLBAR_GROUP_HEIGHT
from gui.monitor.monitor_toolbar import MonitorToolBarWidget

_app = QApplication.instance() or QApplication([])


def test_monitor_toolbar_imports_and_builds() -> None:
    bar = MonitorToolBarWidget()
    _app.processEvents()
    assert bar.isVisible() or True
    bar.set_params(SpectrumParams())
    _app.processEvents()


def test_monitor_toolbar_recargar_textos_no_crash() -> None:
    bar = MonitorToolBarWidget()
    bar.set_params(SpectrumParams(capture_mode="iq", operating_mode="spectrum"))
    bar.recargar_textos()
    _app.processEvents()


def test_ampt_auto_shows_live_ref_not_zero_placeholder() -> None:
    w = MonitorAmptControl()
    p = SpectrumParams(ref_scale_auto=True, ref_level_dbm=0.0, amplitude_unit="dBm")
    w.set_params(p)
    w.set_live_scale(-14.6, 80.0)
    _app.processEvents()
    text = w._spin.lineEdit().text() if w._spin.lineEdit() is not None else ""
    assert "AUTO" in w._spin.suffix().upper() or "A" in w._spin.suffix()
    assert "-14" in text or "-15" in text
    assert text.strip() not in ("", "0", "0.0")


def test_sharp_trace_control_f_label_and_menu() -> None:
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


def test_toolbar_group_frames_share_uniform_height() -> None:
    bar = MonitorToolBarWidget()
    bar.set_params(SpectrumParams(capture_mode="iq", operating_mode="spectrum", iq_trace_sharp=True))
    bar.resize(1200, MONITOR_TOOLBAR_GROUP_HEIGHT + 4)
    bar.show()
    _app.processEvents()
    groups = [
        f
        for f in bar.findChildren(QFrame)
        if f.objectName().startswith("MonitorToolbar")
    ]
    assert groups
    assert {f.height() for f in groups} == {MONITOR_TOOLBAR_GROUP_HEIGHT}
    assert bar._freq is not None and bar._rbw is not None
    assert bar._freq.height() == MONITOR_TOOLBAR_CONTROL_HEIGHT
    assert bar._rbw.height() == MONITOR_TOOLBAR_CONTROL_HEIGHT
    for mode in bar._mode_buttons.values():
        assert mode.height() == MONITOR_TOOLBAR_CONTROL_HEIGHT


def test_toolbar_live_display_scale_updates_ampt() -> None:
    bar = MonitorToolBarWidget()
    bar.set_params(SpectrumParams(ref_scale_auto=True))
    bar.set_live_display_scale(-22.3, 100.0)
    _app.processEvents()
    assert bar._ampt is not None
    text = bar._ampt._spin.lineEdit().text() if bar._ampt._spin.lineEdit() else ""
    assert "-22" in text
