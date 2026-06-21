"""Tests del widget waterfall — historial coherente al cambiar RBW/fft."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams
from gui.monitor.monitor_waterfall_widget import MonitorWaterfallWidget

_app = QApplication.instance() or QApplication([])


def _frame(n: int, *, ref: float = -40.0) -> SpectrumFrame:
    freqs = np.linspace(90e6, 110e6, n)
    power = np.full(n, ref, dtype=float)
    return SpectrumFrame(
        freqs_hz=freqs,
        power_db=power,
        center_freq_hz=100e6,
        span_hz=20e6,
        ref_level_dbm=0.0,
        ref_range_db=80.0,
    )


def test_waterfall_survives_fft_bin_count_change() -> None:
    widget = MonitorWaterfallWidget("monitor", "acciones")
    widget.update_frame(_frame(2048))
    assert len(widget._history) == 1
    widget.update_frame(_frame(256))
    assert len(widget._history) == 1
    assert widget._history[0].shape[0] == 256
    widget._rebuild_image()
    assert widget._image is not None
    assert not widget._image.isNull()


def test_clear_history_on_analyzer_params_fft_change() -> None:
    widget = MonitorWaterfallWidget("monitor", "acciones")
    widget.update_frame(_frame(512))
    params = SpectrumParams(fft_size=256)
    widget.set_analyzer_params(params)
    widget.update_frame(_frame(256))
    widget._rebuild_image()
    assert widget._image is not None
