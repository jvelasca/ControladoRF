"""Métricas RF de capa física (Fase 1) — calidad de enlace inalámbrico."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from core.monitor.marker_analysis import estimate_snr_db, interpolate_power_db
from core.monitor.monitor_freq_span_logic import active_marker_freq_hz
from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams

DEFAULT_CHANNEL_HALF_BW_HZ = 100_000.0
DEFAULT_MASK_HALF_BW_HZ = 100_000.0
OBW_DB_DOWN = 26.0


@dataclass(frozen=True)
class RfLinkMetrics:
    """Resultado de análisis RF en la frecuencia del marcador."""

    marker_freq_hz: float
    channel_power_dbm: Optional[float] = None
    obw_hz: Optional[float] = None
    snr_db: Optional[float] = None
    acp_left_db: Optional[float] = None
    acp_right_db: Optional[float] = None
    carrier_offset_hz: Optional[float] = None
    noise_floor_dbm: Optional[float] = None
    mask_pass: Optional[bool] = None
    link_score: int = 0
    link_grade: str = "unknown"  # good | fair | poor | unknown

    def is_valid(self) -> bool:
        return self.channel_power_dbm is not None or self.snr_db is not None


def _band_power_dbm(
    freqs_hz: np.ndarray,
    power_db: np.ndarray,
    low_hz: float,
    high_hz: float,
) -> Optional[float]:
    if low_hz >= high_hz or freqs_hz.size == 0:
        return None
    mask = (freqs_hz >= low_hz) & (freqs_hz <= high_hz)
    if not np.any(mask):
        return None
    linear = np.power(10.0, power_db[mask].astype(float) / 10.0)
    total = float(np.sum(linear))
    if total <= 0.0:
        return None
    return float(10.0 * np.log10(total))


def _noise_floor_dbm(power_db: np.ndarray, *, percentile: float = 20.0) -> Optional[float]:
    if power_db.size == 0:
        return None
    return float(np.percentile(power_db.astype(float), percentile))


def compute_obw_hz(
    freqs_hz: np.ndarray,
    power_db: np.ndarray,
    *,
    center_hz: float,
    search_half_bw_hz: float = DEFAULT_CHANNEL_HALF_BW_HZ,
    db_down: float = OBW_DB_DOWN,
) -> Optional[float]:
    """Ancho ocupado (−26 dBc respecto al pico en la banda de canal)."""
    freqs = freqs_hz.astype(float).reshape(-1)
    power = power_db.astype(float).reshape(-1)
    n = min(freqs.size, power.size)
    if n < 2:
        return None
    freqs = freqs[:n]
    power = power[:n]
    band = (freqs >= center_hz - search_half_bw_hz) & (freqs <= center_hz + search_half_bw_hz)
    if not np.any(band):
        peak_idx = int(np.argmax(power))
    else:
        local = np.where(band)[0]
        peak_idx = int(local[int(np.argmax(power[local]))])
    peak_pwr = float(power[peak_idx])
    threshold = peak_pwr - float(db_down)
    above = power >= threshold
    if not np.any(above):
        return None
    idx = np.where(above)[0]
    return float(freqs[idx[-1]] - freqs[idx[0]])


def compute_carrier_offset_hz(
    freqs_hz: np.ndarray,
    power_db: np.ndarray,
    *,
    expected_hz: float,
    search_half_bw_hz: float = DEFAULT_CHANNEL_HALF_BW_HZ,
) -> Optional[float]:
    freqs = freqs_hz.astype(float).reshape(-1)
    power = power_db.astype(float).reshape(-1)
    n = min(freqs.size, power.size)
    if n < 2:
        return None
    freqs = freqs[:n]
    power = power[:n]
    band = (freqs >= expected_hz - search_half_bw_hz) & (freqs <= expected_hz + search_half_bw_hz)
    if not np.any(band):
        peak_freq = float(freqs[int(np.argmax(power))])
    else:
        local = np.where(band)[0]
        peak_freq = float(freqs[local[int(np.argmax(power[local]))]])
    return peak_freq - float(expected_hz)


def evaluate_spectral_mask(
    freqs_hz: np.ndarray,
    power_db: np.ndarray,
    *,
    center_hz: float,
    half_bw_hz: float = DEFAULT_MASK_HALF_BW_HZ,
    shoulder_db: float = 40.0,
) -> Optional[bool]:
    """Pass si potencia fuera de ±half_bw cae ≥ shoulder_db respecto al pico del canal."""
    freqs = freqs_hz.astype(float).reshape(-1)
    power = power_db.astype(float).reshape(-1)
    n = min(freqs.size, power.size)
    if n < 4:
        return None
    freqs = freqs[:n]
    power = power[:n]
    inband = (freqs >= center_hz - half_bw_hz) & (freqs <= center_hz + half_bw_hz)
    if not np.any(inband):
        peak_pwr = float(np.max(power))
    else:
        peak_pwr = float(np.max(power[inband]))
    left = freqs < (center_hz - half_bw_hz)
    right = freqs > (center_hz + half_bw_hz)
    ok = True
    if np.any(left):
        ok = ok and (peak_pwr - float(np.max(power[left])) >= shoulder_db - 2.0)
    if np.any(right):
        ok = ok and (peak_pwr - float(np.max(power[right])) >= shoulder_db - 2.0)
    return bool(ok)


def compute_link_score(
    *,
    snr_db: Optional[float],
    obw_hz: Optional[float],
    mask_pass: Optional[bool],
    channel_half_bw_hz: float = DEFAULT_CHANNEL_HALF_BW_HZ,
) -> tuple[int, str]:
    """Puntuación 0–100 y semáforo good/fair/poor."""
    score = 0.0
    weight = 0.0

    if snr_db is not None:
        snr_score = max(0.0, min(100.0, (float(snr_db) - 6.0) / 24.0 * 100.0))
        score += 0.45 * snr_score
        weight += 0.45

    if obw_hz is not None:
        full_bw = channel_half_bw_hz * 2.0
        ratio = float(obw_hz) / max(full_bw, 1.0)
        if ratio <= 1.05:
            obw_score = 100.0
        elif ratio <= 1.25:
            obw_score = 65.0
        elif ratio <= 1.5:
            obw_score = 35.0
        else:
            obw_score = 10.0
        score += 0.25 * obw_score
        weight += 0.25

    if mask_pass is not None:
        score += 0.30 * (100.0 if mask_pass else 25.0)
        weight += 0.30

    if weight <= 0.0:
        return 0, "unknown"

    final = int(round(max(0.0, min(100.0, score / weight))))
    if final >= 75:
        grade = "good"
    elif final >= 45:
        grade = "fair"
    else:
        grade = "poor"
    return final, grade


def compute_rf_link_metrics(
    frame: SpectrumFrame,
    params: SpectrumParams,
    *,
    channel_half_bw_hz: float = DEFAULT_CHANNEL_HALF_BW_HZ,
) -> RfLinkMetrics:
    """Calcula métricas RF en la frecuencia activa del marcador."""
    marker_hz = float(active_marker_freq_hz(params))
    freqs = np.asarray(frame.freqs_hz, dtype=float).reshape(-1)
    power = np.asarray(frame.power_db, dtype=float).reshape(-1)
    n = min(freqs.size, power.size)
    if n < 2:
        return RfLinkMetrics(marker_freq_hz=marker_hz)

    freqs = freqs[:n]
    power = power[:n]

    channel_pwr = _band_power_dbm(
        freqs,
        power,
        marker_hz - channel_half_bw_hz,
        marker_hz + channel_half_bw_hz,
    )
    level_at_marker = interpolate_power_db(freqs, power, marker_hz)
    snr = estimate_snr_db(power, level_at_marker) if level_at_marker is not None else None
    noise = _noise_floor_dbm(power)
    obw = compute_obw_hz(freqs, power, center_hz=marker_hz, search_half_bw_hz=channel_half_bw_hz)
    offset = compute_carrier_offset_hz(
        freqs,
        power,
        expected_hz=marker_hz,
        search_half_bw_hz=channel_half_bw_hz,
    )

    adj = channel_half_bw_hz * 2.0
    main_low = marker_hz - channel_half_bw_hz
    main_high = marker_hz + channel_half_bw_hz
    left_pwr = _band_power_dbm(freqs, power, main_low - adj, main_low)
    right_pwr = _band_power_dbm(freqs, power, main_high, main_high + adj)
    acp_l = (channel_pwr - left_pwr) if channel_pwr is not None and left_pwr is not None else None
    acp_r = (channel_pwr - right_pwr) if channel_pwr is not None and right_pwr is not None else None

    mask = evaluate_spectral_mask(
        freqs,
        power,
        center_hz=marker_hz,
        half_bw_hz=channel_half_bw_hz,
    )
    score, grade = compute_link_score(snr_db=snr, obw_hz=obw, mask_pass=mask)

    return RfLinkMetrics(
        marker_freq_hz=marker_hz,
        channel_power_dbm=channel_pwr,
        obw_hz=obw,
        snr_db=snr,
        acp_left_db=acp_l,
        acp_right_db=acp_r,
        carrier_offset_hz=offset,
        noise_floor_dbm=noise,
        mask_pass=mask,
        link_score=score,
        link_grade=grade,
    )
