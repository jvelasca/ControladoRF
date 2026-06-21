"""Sesión IQ continua HackRF para motor RF v2."""
from __future__ import annotations

import time

from core.monitor.hackrf_iq_capture import HackRfIqCapture
from core.rf.devices.hackrf.baseband import default_filter_for_sample_rate, snap_filter_bw
from core.rf.devices.hackrf.rx_gain import snap_rx_gains
from core.rf.types import IqStreamPlan, RfHardwareConfig


class HackRfIqStream:
    """Adapta HackRfIqCapture a RfHardwareConfig + IqStreamPlan."""

    def __init__(self) -> None:
        self._capture = HackRfIqCapture()
        self._stream_fail_until = 0.0

    @property
    def is_running(self) -> bool:
        return self._capture.is_running

    @property
    def capture(self) -> HackRfIqCapture:
        return self._capture

    def stop(self) -> None:
        self._capture.stop()

    def _baseband_filter_hz(self, hw: RfHardwareConfig, sample_rate_hz: float) -> int:
        bb = hw.baseband
        if bb.filter_auto:
            return int(default_filter_for_sample_rate(sample_rate_hz))
        return int(snap_filter_bw(bb.filter_bw_hz))

    def ensure_stream(self, hw: RfHardwareConfig, iq: IqStreamPlan) -> None:
        gain = snap_rx_gains(hw.rx_gain)
        bb_hz = self._baseband_filter_hz(hw, iq.sample_rate_hz)
        ok, msg = self._capture.restart_if_needed(
            center_freq_hz=iq.center_freq_hz,
            sample_rate_hz=iq.sample_rate_hz,
            lna_gain=gain.lna_db,
            vga_gain=gain.vga_db,
            rf_amp_enable=gain.rf_amp_enable,
            rf_bias_tee_enable=hw.frontend.bias_tee_enable,
            baseband_filter_bw_hz=bb_hz,
        )
        if not ok:
            self._stream_fail_until = time.monotonic() + 1.5
            raise RuntimeError(msg)
        self._stream_fail_until = 0.0

    def read_iq_block(self, fft_size: int, *, wait_sec: float = 0.35) -> bytes:
        n_fft = max(256, int(fft_size))
        if not self._capture.is_running:
            now = time.monotonic()
            if now < self._stream_fail_until:
                raise RuntimeError("Iniciando captura IQ…")
            raise RuntimeError("Reiniciando captura IQ…")

        block = self._capture.read_iq_block(n_fft, wait_sec=wait_sec)
        if block is None:
            block = self._capture.read_iq_block(n_fft, wait_sec=1.0)
        if block is None:
            if not self._capture.is_running:
                raise RuntimeError("Reiniciando captura IQ…")
            err = self._capture.last_error or "Sin muestras IQ"
            raise RuntimeError(err)
        if not self._capture.is_running:
            raise RuntimeError("Reiniciando captura IQ…")
        return block
