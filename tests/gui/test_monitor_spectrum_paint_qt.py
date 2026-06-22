"""Tests Qt de pintado espectro (relleno bajo traza)."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams
from gui.monitor.monitor_spectrum_widget import MonitorSpectrumWidget

_app = QApplication.instance() or QApplication([])


def _sample_frame() -> SpectrumFrame:
    n = 256
    freqs = np.linspace(88e6, 108e6, n)
    power = np.linspace(-95.0, -40.0, n)
    return SpectrumFrame(
        freqs_hz=freqs,
        power_db=power,
        center_freq_hz=98e6,
        span_hz=20e6,
        ref_level_dbm=-20.0,
        ref_range_db=80.0,
    )


def test_spectrum_paint_with_trace_fill_enabled() -> None:
    w = MonitorSpectrumWidget(module_id="test", panel_id="test")
    w.resize(640, 320)
    w.set_analyzer_params(
        SpectrumParams(
            capture_mode="iq",
            operating_mode="spectrum",
            display_trace_fill=True,
            ref_scale_auto=False,
        )
    )
    w.update_frame(_sample_frame())
    w.show()
    _app.processEvents()
    w.repaint()
    _app.processEvents()
    img = w.grab()
    assert not img.isNull()
    assert img.width() >= 100
