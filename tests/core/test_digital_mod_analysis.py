"""Tests análisis digital PSK/QAM/OFDM."""
from __future__ import annotations

import numpy as np

from core.monitor.dab_ofdm import DAB_FFT_SIZE, DAB_SAMPLE_RATE_HZ, DAB_TG_SAMPLES, DAB_TS_SAMPLES, DAB_TU_SAMPLES, DAB_ACTIVE_CARRIERS
from core.monitor.digital_mod_analysis import analyze_digital_modulation
from core.monitor.digital_signal_profiles import get_digital_profile
from core.monitor.spectrum_params import SpectrumParams


def _qpsk_iq(
    *,
    n_symbols: int,
    sample_rate_hz: float,
    symbol_rate_hz: float,
    offset_hz: float = 0.0,
) -> np.ndarray:
    sps = int(round(sample_rate_hz / symbol_rate_hz))
    angles = np.random.choice(
        np.array([np.pi / 4, 3 * np.pi / 4, -3 * np.pi / 4, -np.pi / 4], dtype=np.float64),
        size=n_symbols,
    )
    symbols = np.cos(angles) + 1j * np.sin(angles)
    upsampled = np.repeat(symbols, sps)
    t = np.arange(upsampled.size, dtype=np.float64) / sample_rate_hz
    return (upsampled * np.exp(2j * np.pi * offset_hz * t)).astype(np.complex64)


def _qam16_iq(*, n_symbols: int, sample_rate_hz: float, symbol_rate_hz: float) -> np.ndarray:
    sps = int(round(sample_rate_hz / symbol_rate_hz))
    levels = np.array([-3, -1, 1, 3], dtype=np.float64)
    i = np.random.choice(levels, size=n_symbols)
    q = np.random.choice(levels, size=n_symbols)
    symbols = (i + 1j * q).astype(np.complex64)
    symbols /= np.sqrt(np.mean(np.abs(symbols) ** 2))
    return np.repeat(symbols, sps).astype(np.complex64)


def _dab_ofdm_iq(*, n_symbols: int = 12, sample_rate_hz: float = DAB_SAMPLE_RATE_HZ) -> np.ndarray:
    margin = (DAB_FFT_SIZE - DAB_ACTIVE_CARRIERS) // 2
    qpsk = np.array([np.pi / 4, 3 * np.pi / 4, -3 * np.pi / 4, -np.pi / 4], dtype=np.float64)
    phases = np.random.choice(qpsk, size=DAB_ACTIVE_CARRIERS)
    chunks: list[np.ndarray] = []
    for _ in range(n_symbols):
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


def test_qpsk_analysis_produces_constellation_and_evm() -> None:
    rate = 2_000_000.0
    sym_rate = 500_000.0
    iq = _qpsk_iq(n_symbols=400, sample_rate_hz=rate, symbol_rate_hz=sym_rate, offset_hz=50_000.0)
    params = SpectrumParams(
        center_freq_hz=500_000_000.0,
        vfo_freq_hz=500_050_000.0,
        sample_rate_hz=rate,
        digital_analysis_enabled=True,
        digital_profile="shure_digital",
        digital_symbol_rate_hz=sym_rate,
        digital_mod_order=4,
        capture_mode="iq",
    )
    result = analyze_digital_modulation(
        iq,
        params,
        sample_rate_hz=rate,
        profile=get_digital_profile("shure_digital"),
    )
    assert result.valid
    assert result.constellation.size >= 16
    assert result.evm_rms_pct is not None
    assert result.evm_rms_pct < 25.0
    assert result.mer_db is not None
    assert result.mer_db > 6.0


def test_qam16_analysis() -> None:
    rate = 2_000_000.0
    sym_rate = 500_000.0
    iq = _qam16_iq(n_symbols=300, sample_rate_hz=rate, symbol_rate_hz=sym_rate)
    params = SpectrumParams(
        center_freq_hz=500_000_000.0,
        vfo_freq_hz=500_000_000.0,
        sample_rate_hz=rate,
        digital_analysis_enabled=True,
        digital_profile="custom",
        digital_symbol_rate_hz=sym_rate,
        digital_mod_order=16,
        capture_mode="iq",
    )
    result = analyze_digital_modulation(
        iq,
        params,
        sample_rate_hz=rate,
        profile=get_digital_profile("custom"),
    )
    assert result.valid
    assert result.evm_rms_pct is not None
    assert result.evm_rms_pct < 35.0


def test_dab_ofdm_analysis() -> None:
    rate = DAB_SAMPLE_RATE_HZ
    iq = _dab_ofdm_iq(n_symbols=12, sample_rate_hz=rate)
    params = SpectrumParams(
        center_freq_hz=202_928_000.0,
        vfo_freq_hz=202_928_000.0,
        sample_rate_hz=rate,
        demod_mode="dig",
        digital_analysis_enabled=True,
        digital_profile="dab_iii",
        capture_mode="iq",
        operating_mode="sdr",
    )
    result = analyze_digital_modulation(
        iq,
        params,
        sample_rate_hz=rate,
        profile=get_digital_profile("dab_iii"),
    )
    assert result.valid
    assert result.is_ofdm
    assert result.dab_sync_ok
    assert result.constellation.size >= 16
    assert "DAB" in result.status
