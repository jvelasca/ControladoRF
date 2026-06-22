"""Tests Qt de transiciones RBW (manual/auto/presets)."""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

from core.monitor.monitor_bw_sweep_logic import (
    RBW_PRESETS_HZ,
    patch_rbw_auto,
    patch_rbw_hz,
    patch_rbw_manual,
    sync_analysis_chain,
)
from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_bw_sweep_controls import MonitorFftControl, MonitorRbwControl

_app = QApplication.instance() or QApplication([])


def test_rbw_visible_in_iq_analyzer_mode() -> None:
    w = MonitorRbwControl()
    p = SpectrumParams(
        capture_mode="iq",
        operating_mode="spectrum",
        span_hz=19_000_000.0,
        sample_rate_hz=19_000_000.0,
        fft_auto=True,
        fft_size=1024,
    )
    w.set_params(p)
    assert w.isVisible()


def test_fft_hidden_in_iq_uses_rbw_control() -> None:
    w = MonitorFftControl()
    p = SpectrumParams(
        capture_mode="iq",
        operating_mode="spectrum",
        span_hz=18_000_000.0,
        sample_rate_hz=18_000_000.0,
        fft_auto=True,
        fft_size=1024,
    )
    w.set_params(p)
    assert not w.isVisible()


def test_rbw_auto_to_manual_via_control() -> None:
    w = MonitorRbwControl()
    p = SpectrumParams(rbw_auto=True)
    w.set_params(p)
    w._emit_patch(patch_rbw_manual(p))
    _app.processEvents()
    assert w._params.rbw_auto is False
    assert w._params.rbw_hz >= 1.0
    assert 256 <= w._params.fft_size <= 8192


@pytest.mark.parametrize("preset_hz", [hz for hz in RBW_PRESETS_HZ if hz >= 100_000.0])
def test_rbw_preset_spin_update(preset_hz: float) -> None:
    w = MonitorRbwControl()
    base = SpectrumParams(
        capture_mode="sweep",
        span_hz=20_000_000.0,
        manual_span_hz=20_000_000.0,
        center_freq_hz=98_000_000.0,
        operating_mode="spectrum",
    )
    w.set_params(base)
    updated = patch_rbw_hz(base, preset_hz)
    sync_analysis_chain(updated)
    w._emit_patch(updated)
    _app.processEvents()
    assert w._params.rbw_auto is False
    assert abs(w._params.rbw_hz - preset_hz) < 0.01


def test_rbw_preset_iq_updates_fft() -> None:
    w = MonitorRbwControl()
    base = SpectrumParams(
        capture_mode="iq",
        sample_rate_hz=2_000_000.0,
        span_hz=2_000_000.0,
        fft_size=2048,
    )
    w.set_params(base)
    updated = patch_rbw_hz(base, 10_000.0)
    w._emit_patch(updated)
    _app.processEvents()
    assert w._params.rbw_auto is False
    assert w._params.fft_size == 256
    assert abs(w._params.effective_rbw_hz() - 7_812.5) < 1.0


def test_rbw_manual_to_auto() -> None:
    w = MonitorRbwControl()
    p = patch_rbw_hz(
        SpectrumParams(
            capture_mode="sweep",
            span_hz=20_000_000.0,
            operating_mode="spectrum",
        ),
        100_000.0,
    )
    w.set_params(p)
    w._emit_patch(patch_rbw_auto(w._params, enabled=True))
    _app.processEvents()
    assert w._params.rbw_auto is True


def test_rbw_manual_spin_commit() -> None:
    w = MonitorRbwControl()
    p = patch_rbw_manual(SpectrumParams())
    w.set_params(p, force=True)
    w._on_spin_committed(100.0)
    _app.processEvents()
    assert w._params.rbw_auto is False
    assert w._params.rbw_hz >= 1.0
