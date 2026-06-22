"""Dispositivo TinySA — analizador sweep-only."""
from __future__ import annotations

import time

from core.rf.devices.common.serial_link import SerialLink, SerialTransport
from core.rf.devices.tinysa.protocol import _TINYSA_BAUD, scanraw_spectrum
from core.rf.types import (
    AcquisitionMode,
    AcquisitionPlan,
    BlockState,
    ConfigureResult,
    FrameMetadata,
    RfHardwareConfig,
    SpectrumFrame,
    SweepPlan,
)


class TinySaDevice:
    device_id = "tinysa"

    def __init__(self, *, port: str = "", transport: SerialTransport | None = None) -> None:
        self._port = port
        self._transport = transport
        self._link: SerialLink | None = None
        self._open = False
        self._last_span_hz = 0.0

    @property
    def is_open(self) -> bool:
        return self._open

    def open(self) -> None:
        if not self._port:
            raise RuntimeError("TinySA: seleccione un puerto COM (detección USB o fuente tinysa@COMx)")
        self._link = SerialLink(self._port, _TINYSA_BAUD, transport=self._transport)
        self._link.reset_input()
        self._open = True

    def close(self) -> None:
        if self._link is not None:
            self._link.close()
        self._link = None
        self._open = False

    def configure(self, hardware: RfHardwareConfig, *, window_center_hz: float) -> ConfigureResult:
        return ConfigureResult(
            ok=True,
            blocks=(
                BlockState(
                    requested="tinysa_sweep",
                    applied="tinysa_sweep",
                    valid=True,
                ),
            ),
        )

    def capture_sweep(self, plan: SweepPlan) -> SpectrumFrame:
        if not self._open or self._link is None:
            raise RuntimeError("TinySA no abierto")
        span = plan.stop_hz - plan.start_hz
        points = max(101, min(290, int(span / max(plan.bin_width_hz, 1.0)) + 1))
        freqs, power = scanraw_spectrum(
            self._link,
            start_hz=plan.start_hz,
            stop_hz=plan.stop_hz,
            num_points=points,
            timeout_sec=_sweep_timeout_sec(span),
        )
        from core.monitor.iq_fft import apply_display_band_edge_guard

        power = apply_display_band_edge_guard(power)
        self._last_span_hz = span
        meta = FrameMetadata(
            acquisition_mode=AcquisitionMode.SWEEP,
            device_id=self.device_id,
            rbw_hz=float(plan.bin_width_hz),
            timestamp=time.monotonic(),
        )
        return SpectrumFrame(freqs_hz=freqs, power_db=power.astype(np.float64), metadata=meta)

    def capture_iq_spectrum(self, plan: AcquisitionPlan) -> SpectrumFrame:
        raise RuntimeError("TinySA no admite captura IQ — use modo Analizador (barrido)")


def _sweep_timeout_sec(span_hz: float) -> float:
    span_mhz = max(0.001, span_hz / 1_000_000.0)
    return max(8.0, min(120.0, 6.0 + span_mhz * 0.35))
