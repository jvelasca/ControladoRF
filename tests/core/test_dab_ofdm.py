"""Tests DAB+ OFDM Mode I."""
from __future__ import annotations

import numpy as np

from core.monitor.dab_ofdm import (
    DAB_ACTIVE_CARRIERS,
    DAB_FFT_SIZE,
    DAB_SAMPLE_RATE_HZ,
    DAB_TG_SAMPLES,
    DAB_TS_SAMPLES,
    DAB_TU_SAMPLES,
    analyze_dab_ofdm,
    nearest_dab_block_center_hz,
)


def _dab_mode1_iq(*, n_symbols: int = 12) -> np.ndarray:
    """Genera burst DAB Mode I con CP y modulación diferencial QPSK."""
    margin = (DAB_FFT_SIZE - DAB_ACTIVE_CARRIERS) // 2
    qpsk = np.array([np.pi / 4, 3 * np.pi / 4, -3 * np.pi / 4, -np.pi / 4], dtype=np.float64)
    phases = np.random.choice(qpsk, size=DAB_ACTIVE_CARRIERS)
    chunks: list[np.ndarray] = []
    for sym_idx in range(n_symbols):
        if sym_idx > 0 and sym_idx % 6 == 0:
            chunks.append(np.zeros(DAB_TS_SAMPLES, dtype=np.complex64))
            continue
        dphi = float(np.random.choice(qpsk))
        phases = phases + dphi
        bins = np.zeros(DAB_FFT_SIZE, dtype=np.complex64)
        bins[margin : margin + DAB_ACTIVE_CARRIERS] = (
            np.cos(phases) + 1j * np.sin(phases)
        ).astype(np.complex64)
        useful = np.fft.ifft(np.fft.ifftshift(bins)).astype(np.complex64)
        cp = useful[-DAB_TG_SAMPLES:]
        chunks.append(np.concatenate([cp, useful]))
    return np.concatenate(chunks)


def test_nearest_block_202928_mhz() -> None:
    center_hz, idx = nearest_dab_block_center_hz(202_928_000.0)
    assert 201_000_000.0 < center_hz < 204_000_000.0
    assert idx >= 14


def test_dab_sync_and_ensemble_on_synthetic() -> None:
    iq = _dab_mode1_iq(n_symbols=14)
    result = analyze_dab_ofdm(
        iq,
        sample_rate_hz=DAB_SAMPLE_RATE_HZ,
        center_freq_hz=202_928_000.0,
        vfo_freq_hz=202_928_000.0,
    )
    assert result.valid
    assert result.sync_ok
    assert result.active_carriers >= 800
    assert result.constellation.size >= 32
    assert result.evm_rms_pct is not None
    assert result.evm_rms_pct < 35.0
