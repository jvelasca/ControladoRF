"""Medición multi-canal sobre traza FFT (supervisión inventario)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

import numpy as np

from core.monitor.rf_metrics import _band_power_dbm
from core.monitor.spectrum_params import SpectrumFrame
from core.monitor.supervision.supervision_models import ResolvedSupervisionTarget

GUARD_BAND_FACTOR = 0.5


@dataclass(frozen=True)
class ChannelMeasurement:
    channel_key: str
    label: str
    frequency_hz: float
    carrier_dbm: Optional[float] = None
    noise_dbm: Optional[float] = None
    snr_above_noise_db: Optional[float] = None

    @property
    def is_valid(self) -> bool:
        return self.carrier_dbm is not None and self.noise_dbm is not None


def _local_noise_dbm(
    freqs: np.ndarray,
    power: np.ndarray,
    center_hz: float,
    half_bw_hz: float,
) -> Optional[float]:
    """Piso de ruido en bandas guarda a izquierda y derecha del canal."""
    guard = max(half_bw_hz * GUARD_BAND_FACTOR, 5_000.0)
    main_low = center_hz - half_bw_hz
    main_high = center_hz + half_bw_hz
    left_low = main_low - half_bw_hz - guard
    left_high = main_low - guard
    right_low = main_high + guard
    right_high = main_high + half_bw_hz + guard
    samples: List[float] = []
    for lo, hi in ((left_low, left_high), (right_low, right_high)):
        if lo >= hi:
            continue
        band = (freqs >= lo) & (freqs <= hi)
        if not np.any(band):
            continue
        samples.append(float(np.median(power[band].astype(float))))
    if not samples:
        outside = (freqs < main_low) | (freqs > main_high)
        if np.any(outside):
            return float(np.median(power[outside].astype(float)))
        return float(np.percentile(power.astype(float), 20.0))
    return float(max(samples))


def measure_channel(
    frame: SpectrumFrame,
    target: ResolvedSupervisionTarget,
) -> ChannelMeasurement:
    freqs = np.asarray(frame.freqs_hz, dtype=float).reshape(-1)
    power = np.asarray(frame.power_db, dtype=float).reshape(-1)
    n = min(freqs.size, power.size)
    if n < 2:
        return ChannelMeasurement(
            channel_key=target.channel_key,
            label=target.label,
            frequency_hz=target.frequency_hz,
        )
    freqs = freqs[:n]
    power = power[:n]
    half = target.half_bandwidth_hz
    center = target.frequency_hz
    carrier = _band_power_dbm(freqs, power, center - half, center + half)
    noise = _local_noise_dbm(freqs, power, center, half)
    snr = None
    if carrier is not None and noise is not None:
        snr = float(carrier) - float(noise)
    return ChannelMeasurement(
        channel_key=target.channel_key,
        label=target.label,
        frequency_hz=target.frequency_hz,
        carrier_dbm=carrier,
        noise_dbm=noise,
        snr_above_noise_db=snr,
    )


def measure_targets(
    frame: SpectrumFrame,
    targets: Sequence[ResolvedSupervisionTarget],
) -> List[ChannelMeasurement]:
    return [measure_channel(frame, target) for target in targets if target.enabled]
