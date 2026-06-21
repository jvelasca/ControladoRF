"""Política de análisis — RBW, FFT, SWT."""
from __future__ import annotations

from dataclasses import dataclass

from core.rf.capabilities import capabilities_for_device
from core.rf.types import AcquisitionMode, AcquisitionPlan, AnalysisConfig, OperatorIntent

ANALYZER_AUTO_POINTS = 801


def _snap_fft(n: int) -> int:
    size = max(256, min(8192, int(n)))
    power = 1 << round(size.bit_length() - 1) if size > 0 else 256
    return max(256, min(8192, power))


def _stable_sweep_rbw(span_hz: float, caps, current: float | None) -> float:
    ideal = max(caps.sweep_rbw_min_hz, min(caps.sweep_rbw_max_hz, span_hz / ANALYZER_AUTO_POINTS))
    if current and current > 0 and abs(ideal - current) / current < 0.12:
        return current
    return ideal


@dataclass
class DefaultAnalysisPolicy:
    _last_sweep_rbw_hz: float | None = None

    def resolve(self, intent: OperatorIntent, acquisition: AcquisitionPlan) -> AnalysisConfig:
        caps = capabilities_for_device(intent.source_id)
        base = intent.analysis

        if acquisition.mode is AcquisitionMode.SWEEP and acquisition.sweep is not None:
            if base.rbw_auto:
                rbw = _stable_sweep_rbw(acquisition.window.span_hz, caps, self._last_sweep_rbw_hz)
                self._last_sweep_rbw_hz = rbw
            else:
                rbw = base.rbw_hz
            from core.rf.display import auto_sweep_time_ms_for_span

            sweep_ms = base.sweep_time_ms
            if base.sweep_auto:
                sweep_ms = auto_sweep_time_ms_for_span(acquisition.window.span_hz, rbw)
            return AnalysisConfig(
                rbw_hz=rbw,
                rbw_auto=base.rbw_auto,
                fft_size=_snap_fft(
                    ANALYZER_AUTO_POINTS if base.fft_auto else base.fft_size
                ),
                fft_auto=base.fft_auto,
                sweep_time_ms=sweep_ms,
                sweep_auto=base.sweep_auto,
                trace_smooth_bins=base.trace_smooth_bins,
                trace_smooth_auto=base.trace_smooth_auto,
                detector=base.detector,
                trace_mode=base.trace_mode,
            )

        iq = acquisition.iq
        sr = iq.sample_rate_hz if iq else caps.sample_rate_max_hz
        if base.fft_auto:
            fft = _snap_fft(ANALYZER_AUTO_POINTS)
            rbw = sr / max(fft, 1)
        else:
            fft = _snap_fft(base.fft_size)
            rbw = max(float(base.rbw_hz), 1.0)
            if acquisition.mode is AcquisitionMode.IQ_STREAM:
                rbw = sr / max(fft, 1)
        return AnalysisConfig(
            rbw_hz=rbw,
            rbw_auto=base.rbw_auto,
            fft_size=fft,
            fft_auto=base.fft_auto,
            sweep_time_ms=base.sweep_time_ms,
            sweep_auto=base.sweep_auto,
            trace_smooth_bins=base.trace_smooth_bins,
            trace_smooth_auto=base.trace_smooth_auto,
            detector=base.detector,
            trace_mode=base.trace_mode,
        )

    def reset(self) -> None:
        self._last_sweep_rbw_hz = None
