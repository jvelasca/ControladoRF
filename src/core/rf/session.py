"""Sesión RF — orquesta políticas, dispositivo y pipeline."""
from __future__ import annotations

import time
from dataclasses import replace
from typing import TYPE_CHECKING

from core.rf.acquisition.policy import DefaultAcquisitionPolicy
from core.rf.analysis.pipeline import AnalysisPipeline
from core.rf.analysis.policy import DefaultAnalysisPolicy
from core.rf.capabilities import capabilities_for_device
from core.rf.presentation.scale import apply_display_scale
from core.rf.protocols import RfDevice
from core.rf.registry import create_device
from core.rf.types import (
    AcquisitionMode,
    OperatorIntent,
    RfFrontendConfig,
    RxGainConfig,
    RfTelemetry,
    SpectrumDisplayFrame,
    SpectrumFrame,
)

if TYPE_CHECKING:
    from core.monitor.spectrum_params import SpectrumParams


class RfSession:
    """Fachada única GUI ↔ hardware."""

    def __init__(
        self,
        device: RfDevice | None = None,
        *,
        acquisition_policy: DefaultAcquisitionPolicy | None = None,
        analysis_policy: DefaultAnalysisPolicy | None = None,
    ) -> None:
        self._device = device
        self._acquisition = acquisition_policy or DefaultAcquisitionPolicy()
        self._analysis_policy = analysis_policy or DefaultAnalysisPolicy()
        self._pipeline = AnalysisPipeline()
        self._intent: OperatorIntent | None = None
        self._last_frame: SpectrumFrame | None = None
        self._last_analysis = None
        self._last_acquisition = None
        self._last_capture_ms = 0.0

    @property
    def device(self) -> RfDevice | None:
        return self._device

    def attach_source(self, source_id: str) -> None:
        if self._device is not None and self._device.is_open:
            self._device.close()
        self._device = create_device(source_id)

    def set_intent(self, intent: OperatorIntent) -> None:
        self._intent = intent

    def reset_analysis_pipeline(self) -> None:
        self._pipeline.reset()

    def open(self) -> None:
        if self._device is None:
            raise RuntimeError("No device attached")
        if not self._device.is_open:
            self._device.open()

    def close(self) -> None:
        if self._device is not None and self._device.is_open:
            self._device.close()

    def create_demod_iq_source(self):
        """Fuente IQ para demod/audio sin abrir un segundo stream USB."""
        from core.rf.demod_iq_source import RfDemodIqSource
        from core.rf.devices.hackrf.device import HackRfDevice

        device = self._device
        if not isinstance(device, HackRfDevice):
            return None
        capture = device.demod_iq_capture()
        if capture is None:
            return None
        return RfDemodIqSource(capture)

    def capture_once(self, *, legacy_params: "SpectrumParams | None" = None) -> SpectrumDisplayFrame:
        if self._intent is None:
            raise RuntimeError("OperatorIntent not set")
        if self._device is None:
            raise RuntimeError("No device attached")
        intent = self._intent
        acquisition = self._acquisition.plan(intent, device_id=intent.source_id)
        if legacy_params is not None:
            from core.rf.bridge import analysis_config_from_params, enrich_acquisition_plan

            analysis = analysis_config_from_params(legacy_params)
            acquisition = enrich_acquisition_plan(acquisition, legacy_params, analysis)
        else:
            analysis = self._analysis_policy.resolve(intent, acquisition)
        self._last_acquisition = acquisition
        self._last_analysis = analysis

        hw = replace(
            intent.hardware,
            center_freq_hz=intent.window.center_hz,
        )
        if legacy_params is not None and acquisition.iq is not None:
            hw = replace(
                hw,
                frontend=RfFrontendConfig(
                    rf_amp_enable=bool(legacy_params.rf_amp_enable),
                    bias_tee_enable=bool(legacy_params.rf_bias_tee_enable),
                ),
                rx_gain=RxGainConfig(
                    lna_db=int(legacy_params.lna_gain_db),
                    vga_db=int(legacy_params.vga_gain_db),
                    rf_amp_enable=bool(legacy_params.rf_amp_enable),
                ),
                baseband=replace(
                    hw.baseband,
                    sample_rate_hz=float(legacy_params.sample_rate_hz),
                ),
            )
        elif legacy_params is not None and acquisition.mode is AcquisitionMode.SWEEP:
            hw = replace(
                hw,
                frontend=RfFrontendConfig(
                    rf_amp_enable=bool(legacy_params.rf_amp_enable),
                    bias_tee_enable=bool(legacy_params.rf_bias_tee_enable),
                ),
                rx_gain=RxGainConfig(
                    lna_db=int(legacy_params.lna_gain_db),
                    vga_db=int(legacy_params.vga_gain_db),
                    rf_amp_enable=bool(legacy_params.rf_amp_enable),
                ),
            )
        self._device.configure(hw, window_center_hz=intent.window.center_hz)

        t_capture = time.monotonic()
        if acquisition.mode is AcquisitionMode.SWEEP:
            if acquisition.sweep is None:
                raise RuntimeError("Sweep plan missing")
            raw = self._device.capture_sweep(acquisition.sweep)
        else:
            raw = self._device.capture_iq_spectrum(acquisition)
        self._last_capture_ms = max(0.0, (time.monotonic() - t_capture) * 1000.0)

        meta = replace(
            raw.metadata,
            acquisition_reason=acquisition.reason,
            rbw_hz=analysis.rbw_hz,
        )
        raw = SpectrumFrame(freqs_hz=raw.freqs_hz, power_db=raw.power_db, metadata=meta)
        processed = self._pipeline.process(raw, analysis)
        self._last_frame = processed

        display_cfg = replace(intent.display)
        return apply_display_scale(processed, display_cfg)

    def telemetry(self) -> RfTelemetry:
        intent = self._intent
        acq = self._last_acquisition
        analysis = self._last_analysis
        frame = self._last_frame
        device_id = intent.source_id if intent else "none"
        if intent is None or acq is None or analysis is None:
            return RfTelemetry(
                acquisition_mode="unknown",
                acquisition_reason="",
                device_id=device_id,
                window_start_hz=0.0,
                window_stop_hz=0.0,
                center_hz=0.0,
                sample_rate_hz=None,
                sweep_rbw_hz=None,
                lna_db=0,
                vga_db=0,
                amp_on=False,
                bb_filter_hz=None,
                frame_bins=0,
                rbw_effective_hz=0.0,
            )
        hw = intent.hardware
        return RfTelemetry(
            acquisition_mode=acq.mode.value,
            acquisition_reason=acq.reason,
            device_id=device_id,
            window_start_hz=intent.window.start_hz,
            window_stop_hz=intent.window.stop_hz,
            center_hz=intent.window.center_hz,
            sample_rate_hz=acq.iq.sample_rate_hz if acq.iq else None,
            sweep_rbw_hz=acq.sweep.bin_width_hz if acq.sweep else None,
            lna_db=hw.rx_gain.lna_db,
            vga_db=hw.rx_gain.vga_db,
            amp_on=hw.rx_gain.rf_amp_enable,
            bb_filter_hz=int(hw.baseband.filter_bw_hz) if not hw.baseband.filter_auto else None,
            frame_bins=int(frame.power_db.size) if frame is not None else 0,
            rbw_effective_hz=analysis.rbw_hz,
            last_capture_ms=float(self._last_capture_ms),
        )
