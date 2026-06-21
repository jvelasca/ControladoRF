"""Análisis de marcador F — nivel interpolado y S/R (estilo analizador)."""
from __future__ import annotations

import numpy as np

REF_LEVEL_STEP_COUNT = 101


def interpolate_power_db(freqs_hz: np.ndarray, power_db: np.ndarray, freq_hz: float) -> float | None:
    """Potencia (dBm) en la frecuencia del marcador por interpolación lineal."""
    if freqs_hz.size == 0 or power_db.size == 0:
        return None
    if freqs_hz.size != power_db.size:
        n = min(freqs_hz.size, power_db.size)
        freqs_hz = freqs_hz[:n]
        power_db = power_db[:n]
    target = float(freq_hz)
    if target <= float(freqs_hz[0]):
        return float(power_db[0])
    if target >= float(freqs_hz[-1]):
        return float(power_db[-1])
    return float(np.interp(target, freqs_hz.astype(float), power_db.astype(float)))


def estimate_snr_db(power_db: np.ndarray, signal_db: float, *, noise_percentile: float = 20.0) -> float | None:
    """S/R ≈ señal − piso de ruido (percentil inferior del trazo)."""
    if power_db.size == 0:
        return None
    noise = float(np.percentile(power_db.astype(float), noise_percentile))
    return float(signal_db) - noise
