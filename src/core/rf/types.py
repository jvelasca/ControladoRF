"""Tipos inmutables del motor RF."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

import numpy as np
from numpy.typing import NDArray


class OperatingMode(str, Enum):
    SPECTRUM = "spectrum"
    SDR = "sdr"


class AcquisitionMode(str, Enum):
    IQ_STREAM = "iq_stream"
    SWEEP = "sweep"
    MOCK = "mock"


class FrequencyAnchor(str, Enum):
    CENTER_SPAN = "center_span"
    START_STOP = "start_stop"


@dataclass(frozen=True)
class FrequencyWindow:
    """Ventana de frecuencia visible y de captura."""

    start_hz: float
    stop_hz: float
    anchor: FrequencyAnchor = FrequencyAnchor.CENTER_SPAN
    center_hz: float = 0.0

    def __post_init__(self) -> None:
        if self.stop_hz <= self.start_hz:
            raise ValueError("stop_hz must exceed start_hz")
        if self.center_hz <= 0.0:
            object.__setattr__(self, "center_hz", (self.start_hz + self.stop_hz) / 2.0)

    @property
    def span_hz(self) -> float:
        return self.stop_hz - self.start_hz

    @classmethod
    def from_center_span(cls, center_hz: float, span_hz: float) -> FrequencyWindow:
        half = max(float(span_hz), 1.0) / 2.0
        return cls(
            start_hz=center_hz - half,
            stop_hz=center_hz + half,
            anchor=FrequencyAnchor.CENTER_SPAN,
            center_hz=center_hz,
        )

    @classmethod
    def from_start_stop(cls, start_hz: float, stop_hz: float) -> FrequencyWindow:
        return cls(
            start_hz=float(start_hz),
            stop_hz=float(stop_hz),
            anchor=FrequencyAnchor.START_STOP,
        )


@dataclass(frozen=True)
class RfFrontendConfig:
    rf_amp_enable: bool = False
    bias_tee_enable: bool = False


@dataclass(frozen=True)
class RxGainConfig:
    lna_db: int = 32
    vga_db: int = 40
    rf_amp_enable: bool = False


@dataclass(frozen=True)
class BasebandConfig:
    sample_rate_hz: float = 10_000_000.0
    filter_bw_hz: int = 7_000_000
    filter_auto: bool = True


@dataclass(frozen=True)
class RfHardwareConfig:
    center_freq_hz: float = 100_000_000.0
    frontend: RfFrontendConfig = field(default_factory=RfFrontendConfig)
    rx_gain: RxGainConfig = field(default_factory=RxGainConfig)
    baseband: BasebandConfig = field(default_factory=BasebandConfig)


@dataclass(frozen=True)
class AnalysisConfig:
    rbw_hz: float = 100_000.0
    rbw_auto: bool = True
    fft_size: int = 1024
    fft_auto: bool = True
    sweep_time_ms: float = 100.0
    sweep_auto: bool = True
    trace_smooth_bins: int = 1
    trace_smooth_auto: bool = True
    detector: str = "rms"
    trace_mode: str = "clear_write"


@dataclass(frozen=True)
class DisplayConfig:
    ref_level_dbm: float = 0.0
    ref_range_db: float = 100.0
    ref_auto: bool = True
    amplitude_unit: str = "dBm"
    ref_offset_db: float = 0.0


@dataclass(frozen=True)
class OperatorIntent:
    """Intención única GUI → motor (sustituye patch_* dispersos)."""

    window: FrequencyWindow
    operating_mode: OperatingMode = OperatingMode.SPECTRUM
    hardware: RfHardwareConfig = field(default_factory=RfHardwareConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    source_id: str = "mock"


@dataclass(frozen=True)
class IqStreamPlan:
    center_freq_hz: float
    sample_rate_hz: float
    fft_size: int


@dataclass(frozen=True)
class SweepPlan:
    start_hz: float
    stop_hz: float
    bin_width_hz: float
    lna_db: int
    vga_db: int
    rf_amp_enable: bool
    bias_tee_enable: bool
    dwell_ms: float = 0.0
    sweep_time_ms: float = 100.0
    sweep_auto: bool = True
    fft_size: int = 801
    display_bins: int = 801
    rf_attenuation_db: float = 8.0
    timeout_sec: float = 30.0


@dataclass(frozen=True)
class AcquisitionPlan:
    mode: AcquisitionMode
    window: FrequencyWindow
    iq: IqStreamPlan | None = None
    sweep: SweepPlan | None = None
    reason: str = ""


@dataclass(frozen=True)
class FrameMetadata:
    acquisition_mode: AcquisitionMode
    device_id: str
    rbw_hz: float
    timestamp: float = 0.0
    acquisition_reason: str = ""


@dataclass(frozen=True)
class SpectrumFrame:
    freqs_hz: NDArray[np.float64]
    power_db: NDArray[np.float64]
    metadata: FrameMetadata

    def __post_init__(self) -> None:
        if self.freqs_hz.shape != self.power_db.shape:
            raise ValueError("freqs_hz and power_db must have the same shape")


@dataclass(frozen=True)
class SpectrumDisplayFrame:
    frame: SpectrumFrame
    ref_level_dbm: float
    ref_range_db: float


@dataclass(frozen=True)
class BlockState:
    requested: str
    applied: str
    valid: bool
    message: str = ""


@dataclass(frozen=True)
class ConfigureResult:
    ok: bool
    blocks: tuple[BlockState, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class RfTelemetry:
    acquisition_mode: str
    acquisition_reason: str
    device_id: str
    window_start_hz: float
    window_stop_hz: float
    center_hz: float
    sample_rate_hz: float | None
    sweep_rbw_hz: float | None
    lna_db: int
    vga_db: int
    amp_on: bool
    bb_filter_hz: int | None
    frame_bins: int
    rbw_effective_hz: float
    last_capture_ms: float = 0.0
    fps: float = 0.0


ApplyStatus = Literal["ok", "partial", "error"]
