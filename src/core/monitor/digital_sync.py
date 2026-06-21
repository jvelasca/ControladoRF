"""Recuperación portadora (Costas) y timing (Gardner) para análisis PSK/QAM."""
from __future__ import annotations

import math

import numpy as np


def _nearest_constellation_point(sample: complex, mod_order: int) -> complex:
    order = max(4, int(mod_order))
    if order == 4:
        re = math.copysign(1.0, sample.real) if abs(sample.real) > 1e-9 else 0.0
        im = math.copysign(1.0, sample.imag) if abs(sample.imag) > 1e-9 else 0.0
        return complex(re, im) / math.sqrt(2.0)
    side = int(round(math.sqrt(order)))
    if side * side != order:
        side = 4
    levels = np.linspace(-1.0, 1.0, side, dtype=np.float64)
    best = 0j
    best_dist = float("inf")
    for i in levels:
        for q in levels:
            ref = complex(float(i), float(q))
            dist = abs(sample - ref)
            if dist < best_dist:
                best_dist = dist
                best = ref
    rms = math.sqrt(2.0 / (side * side) * sum(x * x for x in levels))
    return best / max(rms, 1e-9)


def costas_carrier_sync(
    samples: np.ndarray,
    mod_order: int,
    *,
    alpha: float = 0.035,
    beta: float = 0.0004,
) -> tuple[np.ndarray, bool]:
    """Derota la portadora residual; devuelve muestras corregidas y estado de lock."""
    x = np.asarray(samples, dtype=np.complex64).reshape(-1)
    if x.size < 64:
        return x, False

    phase = 0.0
    freq = 0.0
    out = np.empty_like(x)
    errors: list[float] = []
    order = max(4, int(mod_order))
    warmup = max(32, x.size // 4)

    for index, sample in enumerate(x):
        rot = np.exp(-1j * phase).astype(np.complex64)
        z = sample * rot
        out[index] = z
        if index < warmup:
            if order == 4:
                err = math.copysign(1.0, z.real) * z.imag - math.copysign(1.0, z.imag) * z.real
            else:
                ideal = _nearest_constellation_point(z, order)
                err = float((z * np.conj(ideal)).imag)
            freq += beta * err
            phase += freq + alpha * err
            continue
        if order == 4:
            err = math.copysign(1.0, z.real) * z.imag - math.copysign(1.0, z.imag) * z.real
        else:
            ideal = _nearest_constellation_point(z, order)
            err = float((z * np.conj(ideal)).imag)
        freq += beta * err
        phase += freq + alpha * err
        errors.append(abs(err))

    if not errors:
        return out, False
    locked = float(np.median(errors)) < 0.55
    return out, locked


def gardner_symbol_recovery(
    samples: np.ndarray,
    sps_nominal: float,
    *,
    max_symbols: int = 512,
) -> tuple[np.ndarray, bool, float]:
    """Recuperación de símbolos con interpolador Gardner (monitor-grade)."""
    x = np.asarray(samples, dtype=np.complex64).reshape(-1)
    n = x.size
    sps = max(2.0, float(sps_nominal))
    if n < int(sps * 8):
        return np.zeros(0, dtype=np.complex64), False, sps

    omega = sps
    idx = sps
    symbols: list[complex] = []
    strobe_prev = 0j
    omega_error = 0.0
    kp = 0.012
    ki = 0.00015
    omega_min = sps * 0.82
    omega_max = sps * 1.18

    while len(symbols) < max_symbols:
        base = int(idx)
        if base + 2 >= n:
            break
        frac = idx - base
        strobe = x[base] * (1.0 - frac) + x[base + 1] * frac

        mid_idx = idx - omega * 0.5
        mid_base = int(mid_idx)
        if mid_base + 1 >= n:
            break
        mid_frac = mid_idx - mid_base
        mid = x[mid_base] * (1.0 - mid_frac) + x[mid_base + 1] * mid_frac

        symbols.append(complex(strobe))
        if len(symbols) >= 2:
            delta = strobe - strobe_prev
            err = delta.real * mid.real + delta.imag * mid.imag
            omega_error += ki * err
            omega = max(omega_min, min(omega_max, sps + omega_error + kp * err))
        strobe_prev = complex(strobe)
        idx += omega

    arr = np.asarray(symbols, dtype=np.complex64)
    locked = arr.size >= 16 and abs(omega - sps) <= sps * 0.07
    return arr, locked, float(omega)


def sync_psk_qam_samples(
    samples: np.ndarray,
    *,
    mod_order: int,
    sps_nominal: float,
) -> tuple[np.ndarray, bool, bool]:
    """Cadena Costas → Gardner → símbolos listos para EVM/MER."""
    derotated, carrier_locked = costas_carrier_sync(samples, mod_order)
    symbols, timing_locked, _ = gardner_symbol_recovery(derotated, sps_nominal)
    return symbols, carrier_locked, timing_locked
