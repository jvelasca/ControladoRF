"""Dispositivo RF Explorer — analizador sweep-only."""
from __future__ import annotations

import time

from core.rf.devices.common.serial_link import SerialLink, SerialTransport
from core.rf.devices.rf_explorer.protocol import (
    _RF_EXPLORER_BAUD,
    configure_sweep,
    request_sweep,
    reset_device,
)
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


class RfExplorerDevice:
    device_id = "rf_explorer"

    def __init__(self, *, port: str = "", transport: SerialTransport | None = None) -> None:
        self._port = port
        self._transport = transport
        self._link: SerialLink | None = None
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open

    def open(self) -> None:
        if not self._port:
            raise RuntimeError(
                "RF Explorer: seleccione un puerto COM (detección USB o fuente rf_explorer@COMx)"
            )
        self._link = SerialLink(self._port, _RF_EXPLORER_BAUD, transport=self._transport)
        reset_device(self._link)
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
                    requested="rf_explorer_sweep",
                    applied="rf_explorer_sweep",
                    valid=True,
                ),
            ),
        )

    def capture_sweep(self, plan: SweepPlan) -> SpectrumFrame:
        if not self._open or self._link is None:
            raise RuntimeError("RF Explorer no abierto")
        span = plan.stop_hz - plan.start_hz
        configure_sweep(
            self._link,
            start_hz=plan.start_hz,
            stop_hz=plan.stop_hz,
            top_dbm=-20.0,
            bottom_dbm=min(-110.0, float(plan.vga_db) - 90.0),
        )
        freqs, power = request_sweep(self._link, timeout_sec=_sweep_timeout_sec(span))
        from core.monitor.iq_fft import apply_display_band_edge_guard

        power = apply_display_band_edge_guard(power)
        meta = FrameMetadata(
            acquisition_mode=AcquisitionMode.SWEEP,
            device_id=self.device_id,
            rbw_hz=float(plan.bin_width_hz),
            timestamp=time.monotonic(),
        )
        return SpectrumFrame(freqs_hz=freqs, power_db=power.astype(np.float64), metadata=meta)

    def capture_iq_spectrum(self, plan: AcquisitionPlan) -> SpectrumFrame:
        raise RuntimeError("RF Explorer no admite captura IQ — use modo Analizador (barrido)")


def _sweep_timeout_sec(span_hz: float) -> float:
    span_mhz = max(0.001, span_hz / 1_000_000.0)
    return max(10.0, min(180.0, 8.0 + span_mhz * 0.4))
