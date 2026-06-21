"""HackRfDevice — implementación RfDevice."""
from __future__ import annotations

import time

import numpy as np

from core.rf.capabilities import HACKRF_CAPABILITIES
from core.rf.devices.hackrf.baseband import default_filter_for_sample_rate
from core.rf.devices.hackrf.frontend import apply_frontend_config
from core.rf.devices.hackrf.iq_stream import HackRfIqStream
from core.rf.devices.hackrf.rx_gain import snap_rx_gains
from core.rf.spectrum_fft import compute_iq_spectrum_frame, iq_bytes_to_complex
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


def _params_from_sweep(plan: SweepPlan):
    """Puente temporal → SpectrumParams legacy para hackrf_sweep."""
    from core.monitor.spectrum_params import SpectrumParams

    center = (plan.start_hz + plan.stop_hz) / 2.0
    span = plan.stop_hz - plan.start_hz
    return SpectrumParams(
        source_id="hackrf",
        operating_mode="spectrum",
        capture_mode="sweep",
        center_freq_hz=center,
        span_hz=span,
        manual_span_hz=span,
        span_mode="manual",
        marker_start_hz=plan.start_hz,
        marker_stop_hz=plan.stop_hz,
        rbw_hz=float(plan.bin_width_hz),
        rbw_auto=False,
        fft_size=int(plan.display_bins),
        sweep_time_ms=float(plan.sweep_time_ms),
        sweep_auto=bool(plan.sweep_auto),
        lna_gain_db=plan.lna_db,
        vga_gain_db=plan.vga_db,
        rf_amp_enable=plan.rf_amp_enable,
        rf_bias_tee_enable=plan.bias_tee_enable,
        rf_attenuation_db=float(plan.rf_attenuation_db),
    )


class HackRfDevice:
    device_id = "hackrf"

    def __init__(self) -> None:
        self._open = False
        self._last_hw: RfHardwareConfig | None = None
        self._bb_filter_hz: int = 7_000_000
        self._iq_stream = HackRfIqStream()
        self._last_capture_kind: str = ""

    @property
    def is_open(self) -> bool:
        return self._open

    def demod_iq_capture(self):
        """HackRfIqCapture compartido con demodulación (un solo hackrf_transfer)."""
        return self._iq_stream.capture

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._iq_stream.stop()
        self._open = False

    def configure(self, hardware: RfHardwareConfig, *, window_center_hz: float) -> ConfigureResult:
        prev = self._last_hw
        frontend, fe_state = apply_frontend_config(hardware.frontend)
        gain = snap_rx_gains(hardware.rx_gain)
        bb = hardware.baseband
        if bb.filter_auto:
            filt = default_filter_for_sample_rate(bb.sample_rate_hz)
        else:
            from core.rf.devices.hackrf.baseband import snap_filter_bw

            filt = snap_filter_bw(bb.filter_bw_hz)
        self._bb_filter_hz = int(filt)
        new_hw = RfHardwareConfig(
            center_freq_hz=window_center_hz,
            frontend=frontend,
            rx_gain=gain,
            baseband=bb,
        )
        needs_iq_teardown = (
            prev is not None
            and self._iq_stream.is_running
            and (
                abs(prev.baseband.sample_rate_hz - new_hw.baseband.sample_rate_hz) >= 1.0
                or prev.frontend.bias_tee_enable != new_hw.frontend.bias_tee_enable
            )
        )
        if needs_iq_teardown:
            self._iq_stream.stop()
        self._last_hw = new_hw
        gain_state = BlockState(
            requested=(
                f"LNA {hardware.rx_gain.lna_db} VGA {hardware.rx_gain.vga_db} "
                f"P{'+' if hardware.rx_gain.rf_amp_enable else '−'}"
            ),
            applied=(
                f"LNA {gain.lna_db} VGA {gain.vga_db} "
                f"P{'+' if gain.rf_amp_enable else '−'}"
            ),
            valid=True,
        )
        return ConfigureResult(ok=True, blocks=(fe_state, gain_state))

    def capture_sweep(self, plan: SweepPlan) -> SpectrumFrame:
        from core.monitor.hackrf_sweep_source import run_hackrf_sweep

        self._iq_stream.stop()
        self._last_capture_kind = "sweep"
        rbw_hz = float(plan.bin_width_hz)
        params = _params_from_sweep(plan)
        legacy = run_hackrf_sweep(params, timeout_sec=float(plan.timeout_sec))
        meta = FrameMetadata(
            acquisition_mode=AcquisitionMode.SWEEP,
            device_id=self.device_id,
            rbw_hz=rbw_hz,
            timestamp=time.monotonic(),
            acquisition_reason="hackrf_sweep",
        )
        return SpectrumFrame(
            freqs_hz=np.asarray(legacy.freqs_hz, dtype=np.float64),
            power_db=np.asarray(legacy.power_db, dtype=np.float64),
            metadata=meta,
        )

    def capture_iq_spectrum(self, plan: AcquisitionPlan) -> SpectrumFrame:
        if plan.iq is None:
            raise RuntimeError("IQ plan missing")
        if self._last_hw is None:
            raise RuntimeError("HackRF no configurado")

        if self._last_capture_kind == "sweep":
            self._iq_stream.stop()
            from core.monitor.hackrf_iq_capture import HackRfIqCapture

            HackRfIqCapture._release_orphan_transfer()
            time.sleep(0.35)
        self._last_capture_kind = "iq"

        iq = plan.iq
        hw = self._last_hw
        gain = snap_rx_gains(hw.rx_gain)

        self._iq_stream.ensure_stream(hw, iq)

        block = self._iq_stream.read_iq_block(iq.fft_size)
        n_fft = max(256, iq.fft_size)
        samples = iq_bytes_to_complex(block, num_samples=n_fft)
        rbw_hz = iq.sample_rate_hz / max(n_fft, 1)
        return compute_iq_spectrum_frame(
            samples,
            center_freq_hz=iq.center_freq_hz,
            sample_rate_hz=iq.sample_rate_hz,
            rx_gain=gain,
            device_id=self.device_id,
            rbw_hz=rbw_hz,
        )
