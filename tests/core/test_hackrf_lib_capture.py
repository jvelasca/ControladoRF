"""Captura IQ libhackrf — ganancias en caliente sin reiniciar stream."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.monitor.hackrf_iq_capture import HackRfIqCapture


def test_restart_if_needed_applies_gains_live_on_lib_backend():
    cap = HackRfIqCapture()
    cap.configure(
        center_freq_hz=93_200_000.0,
        sample_rate_hz=2_000_000.0,
        lna_gain=24,
        vga_gain=34,
        rf_amp_enable=False,
    )
    cap._backend = "lib"
    mock_lib = MagicMock()
    mock_lib.is_streaming = True
    cap._lib = mock_lib

    ok, msg = cap.restart_if_needed(
        center_freq_hz=93_200_000.0,
        sample_rate_hz=2_000_000.0,
        lna_gain=32,
        vga_gain=40,
        rf_amp_enable=True,
    )

    assert ok is True
    assert msg == "Sin cambios"
    mock_lib.apply_gains.assert_called_once_with(
        lna_gain=32,
        vga_gain=40,
        rf_amp_enable=True,
        rf_bias_tee_enable=False,
    )
    mock_lib.stop_rx.assert_not_called()
    assert cap._lna_gain == 32
    assert cap._vga_gain == 40
    assert cap._rf_amp_enable is True
    assert cap._applied_rf_amp_enable is True


def test_restart_if_needed_restarts_transfer_when_not_lib():
    cap = HackRfIqCapture()
    cap.configure(
        center_freq_hz=93_200_000.0,
        sample_rate_hz=2_000_000.0,
        lna_gain=24,
        vga_gain=34,
    )
    cap._backend = "transfer"
    cap._proc = MagicMock()
    cap._proc.poll.return_value = None

    with patch.object(cap, "stop") as stop_mock, patch.object(
        cap, "start", return_value=(True, "ok")
    ) as start_mock:
        ok, msg = cap.restart_if_needed(
            center_freq_hz=93_200_000.0,
            sample_rate_hz=2_000_000.0,
            lna_gain=32,
            vga_gain=34,
        )

    assert ok is True
    stop_mock.assert_called_once()
    start_mock.assert_called_once()


def test_libhackrf_dll_resolves_on_windows():
    from core.monitor.hackrf_lib import resolve_hackrf_dll

    path = resolve_hackrf_dll()
    if path is not None:
        assert path.name.lower() in ("hackrf.dll", "libhackrf.dll", "libhackrf.so", "libhackrf.dylib")
