"""Dispositivo mock — tests y desarrollo sin hardware."""
from __future__ import annotations

import time

import numpy as np

from core.rf.capabilities import MOCK_CAPABILITIES
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


class MockRfDevice:
    device_id = "mock"

    def __init__(self, *, num_bins: int = 801) -> None:
        self._open = False
        self._num_bins = max(64, int(num_bins))
        self._last_hardware: RfHardwareConfig | None = None

    @property
    def is_open(self) -> bool:
        return self._open

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def configure(self, hardware: RfHardwareConfig, *, window_center_hz: float) -> ConfigureResult:
        self._last_hardware = hardware
        return ConfigureResult(
            ok=True,
            blocks=(
                BlockState(
                    requested=f"lna={hardware.rx_gain.lna_db}",
                    applied=f"lna={hardware.rx_gain.lna_db}",
                    valid=True,
                ),
            ),
        )

    def capture_sweep(self, plan: SweepPlan) -> SpectrumFrame:
        return self._synthetic_frame(
            plan.start_hz,
            plan.stop_hz,
            device_id=self.device_id,
            mode=AcquisitionMode.SWEEP,
            rbw_hz=plan.bin_width_hz,
        )

    def capture_iq_spectrum(self, plan: AcquisitionPlan) -> SpectrumFrame:
        if plan.iq is None:
            raise RuntimeError("IQ plan missing")
        half = plan.iq.sample_rate_hz / 2.0
        start = plan.iq.center_freq_hz - half
        stop = plan.iq.center_freq_hz + half
        rbw = plan.iq.sample_rate_hz / max(plan.iq.fft_size, 1)
        return self._synthetic_frame(
            start,
            stop,
            device_id=self.device_id,
            mode=AcquisitionMode.IQ_STREAM,
            rbw_hz=rbw,
        )

    def _synthetic_frame(
        self,
        start_hz: float,
        stop_hz: float,
        *,
        device_id: str,
        mode: AcquisitionMode,
        rbw_hz: float,
    ) -> SpectrumFrame:
        n = self._num_bins
        freqs = np.linspace(start_hz, stop_hz, n, dtype=np.float64)
        noise = np.random.normal(-95.0, 3.0, n)
        center = (start_hz + stop_hz) / 2.0
        tone = -55.0 * np.exp(-0.5 * ((freqs - center) / max(rbw_hz * 2, 1.0)) ** 2)
        power = noise + tone
        meta = FrameMetadata(
            acquisition_mode=mode,
            device_id=device_id,
            rbw_hz=float(rbw_hz),
            timestamp=time.monotonic(),
        )
        return SpectrumFrame(freqs_hz=freqs, power_db=power.astype(np.float64), metadata=meta)
