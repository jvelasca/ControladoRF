"""Política de adquisición — IQ fluido dentro del BW instantáneo; barrido solo si SPAN > BW."""
from __future__ import annotations

from dataclasses import dataclass

from core.rf.capabilities import DeviceCapabilities, capabilities_for_device
from core.rf.types import (
    AcquisitionMode,
    AcquisitionPlan,
    IqStreamPlan,
    OperatingMode,
    OperatorIntent,
    SweepPlan,
)

ANALYZER_AUTO_POINTS = 801
SPAN_MIN_IQ_HZ = 2_000_000.0


def _snap_fft(n: int, *, min_size: int = 256, max_size: int = 8192) -> int:
    size = max(min_size, min(max_size, int(n)))
    power = 1 << (size.bit_length() - 1) if size > 0 else min_size
    return max(min_size, min(max_size, power))


def _wants_sweep(
    span_hz: float,
    *,
    instant_bw_hz: float,
    operating_mode: OperatingMode,
) -> tuple[bool, str]:
    """IQ solo dentro del BW instantaneo; barrido GSG si SPAN lo supera."""
    if operating_mode is OperatingMode.SDR:
        return False, "sdr_mode_prefers_iq"

    from core.rf.acquisition.iq_stitch_plan import span_exceeds_instant_bw

    if span_exceeds_instant_bw(span_hz, instant_bw_hz):
        return True, "span_exceeds_instant_bw"
    return False, "iq_within_instant_bw"


def _clamp_sweep_rbw(span_hz: float, caps: DeviceCapabilities) -> float:
    ideal = span_hz / ANALYZER_AUTO_POINTS
    return max(caps.sweep_rbw_min_hz, min(caps.sweep_rbw_max_hz, ideal))


def _iq_sample_rate(span_hz: float, caps: DeviceCapabilities, intent: OperatorIntent) -> float:
    from core.monitor.display_scale import snap_iq_sample_rate_hz

    span = max(float(span_hz), SPAN_MIN_IQ_HZ)
    rate = min(caps.instant_bw_hz, span)
    hw_rate = float(intent.hardware.baseband.sample_rate_hz or 0.0)
    if hw_rate >= SPAN_MIN_IQ_HZ:
        rate = min(caps.instant_bw_hz, max(rate, hw_rate))
    return float(snap_iq_sample_rate_hz(rate))


def _iq_fft_size(intent: OperatorIntent) -> int:
    analysis = intent.analysis
    if analysis.fft_auto:
        return _snap_fft(ANALYZER_AUTO_POINTS)
    return _snap_fft(analysis.fft_size)


@dataclass
class DefaultAcquisitionPolicy:
    """Motor v2 — IQ fluido <= BW instantaneo; hackrf_sweep para lapso ancho correcto."""

    def plan(self, intent: OperatorIntent, *, device_id: str, instant_bw_hz: float | None = None) -> AcquisitionPlan:
        caps = capabilities_for_device(device_id)
        instant = instant_bw_hz if instant_bw_hz is not None else caps.instant_bw_hz
        window = intent.window
        span = window.span_hz

        if not caps.supports_iq_stream:
            want_sweep = caps.supports_sweep
            reason = "analyzer_only_sweep" if want_sweep else "analyzer_no_capture"
        else:
            want_sweep, reason = _wants_sweep(
                span,
                instant_bw_hz=instant,
                operating_mode=intent.operating_mode,
            )

        hw = intent.hardware
        if want_sweep and caps.supports_sweep:
            if intent.analysis.rbw_auto:
                rbw = _clamp_sweep_rbw(span, caps)
            else:
                from core.rf.display import clamp_sweep_rbw_hz

                rbw = clamp_sweep_rbw_hz(float(intent.analysis.rbw_hz))
            sweep = SweepPlan(
                start_hz=window.start_hz,
                stop_hz=window.stop_hz,
                bin_width_hz=rbw,
                lna_db=hw.rx_gain.lna_db,
                vga_db=hw.rx_gain.vga_db,
                rf_amp_enable=hw.rx_gain.rf_amp_enable,
                bias_tee_enable=hw.frontend.bias_tee_enable,
            )
            return AcquisitionPlan(
                mode=AcquisitionMode.SWEEP,
                window=window,
                sweep=sweep,
                reason=reason,
            )

        sr = _iq_sample_rate(span, caps, intent)
        fft = _iq_fft_size(intent)
        iq = IqStreamPlan(
            center_freq_hz=window.center_hz,
            sample_rate_hz=sr,
            fft_size=fft,
        )
        return AcquisitionPlan(
            mode=AcquisitionMode.IQ_STREAM,
            window=window,
            iq=iq,
            reason=reason if not want_sweep else "sweep_unavailable_fallback_iq",
        )

    def reset_sticky(self) -> None:
        return
