"""Tests Qt de suavizado de traza (SUAV)."""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

from core.monitor.monitor_bw_sweep_logic import (
    patch_trace_smooth_auto,
    patch_trace_smooth_bins,
    patch_trace_smooth_manual,
)
from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_bw_sweep_controls import MonitorVbwControl

_app = QApplication.instance() or QApplication([])


def test_smooth_auto_to_manual_via_control() -> None:
    w = MonitorVbwControl()
    p = SpectrumParams(trace_smooth_auto=True)
    w.set_params(p)
    w._emit_patch(patch_trace_smooth_manual(p))
    _app.processEvents()
    assert w._params.trace_smooth_auto is False


def test_smooth_preset_bins() -> None:
    w = MonitorVbwControl()
    base = SpectrumParams(capture_mode="iq", fft_size=2048, sample_rate_hz=2_000_000.0)
    w.set_params(base)
    updated = patch_trace_smooth_bins(base, 11)
    w._emit_patch(updated)
    _app.processEvents()
    assert w._params.trace_smooth_auto is False
    assert w._params.trace_smooth_bins == 11


def test_smooth_manual_to_auto() -> None:
    w = MonitorVbwControl()
    p = patch_trace_smooth_bins(SpectrumParams(), 5)
    w.set_params(p)
    w._emit_patch(patch_trace_smooth_auto(w._params, enabled=True))
    _app.processEvents()
    assert w._params.trace_smooth_auto is True
