"""Pipeline de análisis — detector, SUAV, hold."""
from __future__ import annotations

import numpy as np

from core.rf.types import AcquisitionMode, AnalysisConfig, SpectrumFrame


def apply_detector(
    power_db: np.ndarray,
    detector: str,
    *,
    acquisition_mode: AcquisitionMode | None = None,
) -> np.ndarray:
    x = np.asarray(power_db, dtype=float)
    if x.size == 0:
        return x
    if acquisition_mode is AcquisitionMode.IQ_STREAM:
        return x
    mode = (detector or "rms").lower()
    if mode in ("peak", "neg_peak", "sample", "average"):
        return x
    if x.size < 3:
        return x
    kernel = np.array([0.25, 0.5, 0.25], dtype=float)
    return np.convolve(x, kernel, mode="same")


def apply_trace_smooth(power_db: np.ndarray, config: AnalysisConfig) -> np.ndarray:
    x = np.asarray(power_db, dtype=float)
    if x.size == 0 or config.trace_smooth_auto:
        return x
    width = max(1, int(config.trace_smooth_bins))
    if width <= 1:
        return x
    lin = np.power(10.0, x / 10.0)
    kernel = np.ones(width, dtype=float) / float(width)
    smoothed = np.convolve(lin, kernel, mode="same")
    return (10.0 * np.log10(np.maximum(smoothed, 1e-30))).astype(float)


class AnalysisPipeline:
    def __init__(self) -> None:
        self._hold_max: np.ndarray | None = None
        self._hold_min: np.ndarray | None = None
        self._average: np.ndarray | None = None
        self._avg_count = 0

    def reset(self) -> None:
        self._hold_max = None
        self._hold_min = None
        self._average = None
        self._avg_count = 0

    def _apply_trace_mode(self, power_db: np.ndarray, config: AnalysisConfig) -> np.ndarray:
        x = np.asarray(power_db, dtype=float)
        if x.size == 0:
            return x
        mode = (config.trace_mode or "clear_write").lower()
        if mode == "max_hold":
            if self._hold_max is None or self._hold_max.shape != x.shape:
                self._hold_max = x.copy()
            else:
                self._hold_max = np.maximum(self._hold_max, x)
            return self._hold_max.copy()
        if mode == "min_hold":
            if self._hold_min is None or self._hold_min.shape != x.shape:
                self._hold_min = x.copy()
            else:
                self._hold_min = np.minimum(self._hold_min, x)
            return self._hold_min.copy()
        if mode == "average":
            if self._average is None or self._average.shape != x.shape:
                self._average = x.copy()
                self._avg_count = 1
            else:
                self._avg_count += 1
                alpha = 1.0 / float(self._avg_count)
                self._average = self._average * (1.0 - alpha) + x * alpha
            return self._average.copy()
        self.reset()
        return x

    def process(self, frame: SpectrumFrame, config: AnalysisConfig) -> SpectrumFrame:
        power = np.asarray(frame.power_db, dtype=float)
        is_sweep = (
            frame.metadata is not None
            and frame.metadata.acquisition_mode is AcquisitionMode.SWEEP
        )
        if not config.trace_smooth_auto and config.trace_smooth_bins > 1:
            power = apply_trace_smooth(power, config)
        acq_mode = frame.metadata.acquisition_mode if frame.metadata is not None else None
        if not is_sweep:
            power = apply_detector(power, config.detector, acquisition_mode=acq_mode)
        power = self._apply_trace_mode(power, config)
        return SpectrumFrame(
            freqs_hz=frame.freqs_hz,
            power_db=power,
            metadata=frame.metadata,
        )
