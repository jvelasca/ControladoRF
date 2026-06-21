"""Tests de conexión, alertas y apply_params del Monitor."""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from core.monitor.monitor_bw_sweep_logic import patch_rbw_hz, sync_analysis_chain
from core.monitor.spectrum_engine import SpectrumEngine, is_fatal_capture_error
from core.monitor.spectrum_params import SpectrumParams


def test_is_fatal_capture_error_usb() -> None:
    assert is_fatal_capture_error("HackRF desconectado (USB)")
    assert is_fatal_capture_error("device not found")
    assert not is_fatal_capture_error("Sin muestras IQ")


def test_engine_stop_preserves_fatal_message() -> None:
    engine = SpectrumEngine()
    engine._last_exit_message = "HackRF desconectado (USB) — deteniendo captura"
    statuses: list[str] = []
    engine._on_status = statuses.append
    engine.stop()
    assert engine.last_exit_message
    assert statuses == []


def test_rbw_100_manual_chain() -> None:
    updated = patch_rbw_hz(SpectrumParams(), 100.0)
    sync_analysis_chain(updated)
    assert updated.rbw_auto is False
    assert abs(updated.rbw_hz - 100.0) < 0.01
    assert 256 <= updated.fft_size <= 8192
