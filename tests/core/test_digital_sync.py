"""Tests recuperación Costas/Gardner."""
from __future__ import annotations

import numpy as np

from core.monitor.digital_sync import costas_carrier_sync, gardner_symbol_recovery, sync_psk_qam_samples


def _qpsk_with_offset(*, n_symbols: int, sps: int, offset_hz: float, sample_rate: float) -> np.ndarray:
    angles = np.array([np.pi / 4, 3 * np.pi / 4, -3 * np.pi / 4, -np.pi / 4], dtype=np.float64)
    symbols = np.cos(angles) + 1j * np.sin(angles)
    upsampled = np.repeat(symbols, n_symbols // 4 + 1)[: n_symbols]
    upsampled = np.repeat(upsampled, sps)
    t = np.arange(upsampled.size, dtype=np.float64) / sample_rate
    return (upsampled * np.exp(2j * np.pi * offset_hz * t)).astype(np.complex64)


def test_costas_locks_qpsk_carrier() -> None:
    rate = 2_000_000.0
    sps = 4
    iq = _qpsk_with_offset(n_symbols=400, sps=sps, offset_hz=0.0, sample_rate=rate)
    derotated, locked = costas_carrier_sync(iq, 4)
    assert derotated.size == iq.size
    assert locked


def test_gardner_recovers_symbols() -> None:
    rate = 2_000_000.0
    sps = 4
    iq = _qpsk_with_offset(n_symbols=400, sps=sps, offset_hz=0.0, sample_rate=rate)
    symbols, locked, omega = gardner_symbol_recovery(iq, float(sps))
    assert symbols.size >= 16
    assert abs(omega - sps) <= 1.0


def test_sync_chain_produces_symbols() -> None:
    rate = 2_000_000.0
    sps = 4
    iq = _qpsk_with_offset(n_symbols=400, sps=sps, offset_hz=40_000.0, sample_rate=rate)
    symbols, carrier_locked, timing_locked = sync_psk_qam_samples(
        iq,
        mod_order=4,
        sps_nominal=float(sps),
    )
    assert symbols.size >= 16
