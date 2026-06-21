"""Análisis de modulaciones digitales PSK/QAM/OFDM — constelación, EVM y MER."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from core.monitor.digital_signal_profiles import (
    DigitalSignalProfile,
    get_digital_profile,
    resolve_mod_order,
)
from core.monitor.spectrum_params import SpectrumParams

from core.monitor.dab_ofdm import DAB_FFT_SIZE, analyze_dab_ofdm
from core.monitor.dab_welle_backend import probe_welle_cli, welle_channel_hint


MAX_CONSTELLATION_POINTS = 512


@dataclass(frozen=True)
class DigitalModAnalysis:
    valid: bool
    profile_id: str
    modulation: str
    symbol_rate_hz: float
    samples_per_symbol: int
    evm_rms_pct: float | None
    mer_db: float | None
    constellation: np.ndarray
    status: str
    dab_sync_ok: bool = False
    dab_ensemble_detected: bool = False
    dab_active_carriers: int = 0
    dab_block_center_mhz: float | None = None
    welle_cli_available: bool = False
    carrier_locked: bool = False
    timing_locked: bool = False
    sync_ok: bool = False
    mer_db_smoothed: float | None = None

    @property
    def is_ofdm(self) -> bool:
        return self.modulation == "ofdm"


def _ideal_constellation(mod_order: int) -> np.ndarray:
    order = max(4, int(mod_order))
    if order == 4:
        angles = np.array([np.pi / 4, 3 * np.pi / 4, -3 * np.pi / 4, -np.pi / 4], dtype=np.float64)
        return (np.cos(angles) + 1j * np.sin(angles)).astype(np.complex64)
    side = int(round(math.sqrt(order)))
    if side * side != order:
        side = 4
        order = 16
    levels = np.linspace(-1.0, 1.0, side, dtype=np.float64)
    grid = np.array([complex(i, q) for i in levels for q in levels], dtype=np.complex64)
    rms = float(np.sqrt(np.mean(np.abs(grid) ** 2)) + 1e-12)
    return (grid / rms).astype(np.complex64)


def _frequency_shift(samples: np.ndarray, offset_hz: float, sample_rate_hz: float) -> np.ndarray:
    x = np.asarray(samples, dtype=np.complex64).reshape(-1)
    if x.size == 0 or abs(offset_hz) < 0.5:
        return x
    dphi = (-2.0 * math.pi * float(offset_hz)) / float(sample_rate_hz)
    rot = np.exp(1j * dphi * np.arange(x.size, dtype=np.float64)).astype(np.complex64)
    return x * rot


def _channel_lowpass(samples: np.ndarray, *, bandwidth_hz: float, sample_rate_hz: float) -> np.ndarray:
    x = np.asarray(samples, dtype=np.complex64).reshape(-1)
    n = x.size
    if n < 32:
        return x
    spec = np.fft.fftshift(np.fft.fft(x))
    freqs = np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / float(sample_rate_hz)))
    mask = np.abs(freqs) <= max(1_000.0, float(bandwidth_hz) * 0.55)
    return np.fft.ifft(np.fft.ifftshift(spec * mask)).astype(np.complex64)


def _samples_per_symbol(sample_rate_hz: float, symbol_rate_hz: float) -> int:
    sps = int(round(float(sample_rate_hz) / max(float(symbol_rate_hz), 1.0)))
    return max(2, min(sps, 256))


def _extract_symbols_peak(samples: np.ndarray, sps: int) -> np.ndarray:
    x = np.asarray(samples, dtype=np.complex64).reshape(-1)
    n_sym = int(x.size // sps)
    if n_sym < 8:
        return np.zeros(0, dtype=np.complex64)
    trimmed = x[: n_sym * sps].reshape(n_sym, sps)
    idx = np.argmax(np.abs(trimmed), axis=1)
    return trimmed[np.arange(n_sym), idx].astype(np.complex64)


def _extract_symbols_eye_center(samples: np.ndarray, sps: int) -> np.ndarray:
    x = np.asarray(samples, dtype=np.complex64).reshape(-1)
    n_sym = int(x.size // sps)
    if n_sym < 8:
        return np.zeros(0, dtype=np.complex64)
    trimmed = x[: n_sym * sps].reshape(n_sym, sps)
    center = max(0, min(sps - 1, sps // 2))
    return trimmed[:, center].astype(np.complex64)


def _extract_symbols(samples: np.ndarray, sps: int, *, eye_center: bool) -> np.ndarray:
    if eye_center:
        syms = _extract_symbols_eye_center(samples, sps)
        if syms.size >= 16:
            return syms
    return _extract_symbols_peak(samples, sps)


def _normalize_symbols(symbols: np.ndarray) -> np.ndarray:
    if symbols.size == 0:
        return symbols
    x = symbols.astype(np.complex64) - np.mean(symbols)
    power = float(np.mean(np.abs(x) ** 2))
    if power <= 1e-12:
        return x
    return (x / math.sqrt(power)).astype(np.complex64)


def _evm_and_mer(symbols: np.ndarray, mod_order: int) -> tuple[float | None, float | None]:
    if symbols.size < 8:
        return None, None
    ideal = _ideal_constellation(mod_order)
    norm = _normalize_symbols(symbols)
    dist = np.abs(norm.reshape(-1, 1) - ideal.reshape(1, -1))
    nearest = ideal[np.argmin(dist, axis=1)]
    err = norm - nearest
    evm_rms = float(np.sqrt(np.mean(np.abs(err) ** 2) / (np.mean(np.abs(nearest) ** 2) + 1e-12)))
    evm_pct = evm_rms * 100.0
    signal_pwr = float(np.mean(np.abs(nearest) ** 2))
    error_pwr = float(np.mean(np.abs(err) ** 2))
    if error_pwr <= 1e-15:
        mer_db = 60.0
    else:
        mer_db = float(10.0 * math.log10(signal_pwr / error_pwr))
    return evm_pct, mer_db


def _decimate_constellation(points: np.ndarray) -> np.ndarray:
    norm = np.asarray(points, dtype=np.complex64).reshape(-1)
    if norm.size <= MAX_CONSTELLATION_POINTS:
        return norm
    step = max(1, norm.size // MAX_CONSTELLATION_POINTS)
    return norm[::step][:MAX_CONSTELLATION_POINTS]


def _empty_result(*, profile_id: str, status: str, modulation: str = "unknown") -> DigitalModAnalysis:
    return DigitalModAnalysis(
        valid=False,
        profile_id=profile_id,
        modulation=modulation,
        symbol_rate_hz=0.0,
        samples_per_symbol=0,
        evm_rms_pct=None,
        mer_db=None,
        constellation=np.zeros(0, dtype=np.complex64),
        status=status,
    )


def _analyze_dab_ofdm(
    iq_samples: np.ndarray,
    params: SpectrumParams,
    *,
    sample_rate_hz: float,
    profile: DigitalSignalProfile,
) -> DigitalModAnalysis:
    """DAB+ Mode I: sync CP, QPSK diferencial, detección ensemble."""
    dab = analyze_dab_ofdm(
        iq_samples,
        sample_rate_hz=sample_rate_hz,
        center_freq_hz=float(params.center_freq_hz),
        vfo_freq_hz=float(params.vfo_freq_hz),
        channel_bw_hz=profile.channel_bw_hz,
    )
    welle = probe_welle_cli()
    status = dab.status
    if dab.ensemble_detected and not welle.available:
        status += " · welle-cli no instalado (audio DAB+)"
    elif welle.available and dab.ensemble_detected:
        hint = welle_channel_hint(params.vfo_freq_hz or params.center_freq_hz)
        status += f" · welle-cli OK · {hint}"

    return DigitalModAnalysis(
        valid=dab.valid,
        profile_id=profile.profile_id,
        modulation="ofdm",
        symbol_rate_hz=profile.symbol_rate_hz,
        samples_per_symbol=DAB_FFT_SIZE,
        evm_rms_pct=dab.evm_rms_pct,
        mer_db=dab.mer_db,
        constellation=dab.constellation,
        status=status,
        dab_sync_ok=dab.sync_ok,
        dab_ensemble_detected=dab.ensemble_detected,
        dab_active_carriers=dab.active_carriers,
        dab_block_center_mhz=dab.block_center_mhz,
        welle_cli_available=welle.available,
        carrier_locked=dab.sync_ok,
        timing_locked=dab.sync_ok,
        sync_ok=bool(dab.sync_ok and dab.ensemble_detected),
    )


def _analyze_psk_qam(
    iq_samples: np.ndarray,
    params: SpectrumParams,
    *,
    sample_rate_hz: float,
    profile: DigitalSignalProfile,
) -> DigitalModAnalysis:
    x = np.asarray(iq_samples, dtype=np.complex64).reshape(-1)
    if x.size < 256 or sample_rate_hz <= 0:
        return _empty_result(profile_id=profile.profile_id, status="IQ insuficiente")

    offset_hz = float(params.vfo_freq_hz) - float(params.center_freq_hz)
    x = _frequency_shift(x, offset_hz, sample_rate_hz)
    x = _channel_lowpass(x, bandwidth_hz=profile.channel_bw_hz, sample_rate_hz=sample_rate_hz)

    symbol_rate = float(params.digital_symbol_rate_hz or profile.symbol_rate_hz)
    sps = _samples_per_symbol(sample_rate_hz, symbol_rate)
    mod_order = resolve_mod_order(profile, params)

    from core.monitor.digital_sync import sync_psk_qam_samples

    symbols, carrier_locked, timing_locked = sync_psk_qam_samples(
        x,
        mod_order=mod_order,
        sps_nominal=float(sps),
    )
    if symbols.size < 16:
        symbols = _extract_symbols(x, sps, eye_center=profile.use_eye_center)
        carrier_locked = False
        timing_locked = False
    if symbols.size < 16:
        return _empty_result(profile_id=profile.profile_id, status="Sin símbolos detectados")

    mod_label = profile.modulation.upper()
    if mod_order == 16:
        mod_label = "QAM16"
    elif mod_order == 64:
        mod_label = "QAM64"
    elif mod_order == 4:
        mod_label = "QPSK"

    norm = _normalize_symbols(symbols)
    evm_pct, mer_db = _evm_and_mer(norm, mod_order)
    if evm_pct is not None and evm_pct > 35.0:
        fallback = _extract_symbols(x, sps, eye_center=profile.use_eye_center)
        if fallback.size >= 16:
            fnorm = _normalize_symbols(fallback)
            fevm, fmer = _evm_and_mer(fnorm, mod_order)
            if fevm is not None and (evm_pct is None or fevm < evm_pct):
                symbols = fallback
                norm = fnorm
                evm_pct, mer_db = fevm, fmer
                carrier_locked = False
                timing_locked = False
    plot_points = _decimate_constellation(norm)

    status = f"{mod_label} · {symbol_rate / 1e3:.0f} ksps · {len(norm)} sym"
    if carrier_locked:
        status += " · Costas"
    if timing_locked:
        status += " · Gardner"
    if evm_pct is not None:
        status += f" · EVM {evm_pct:.1f}%"
    return DigitalModAnalysis(
        valid=True,
        profile_id=profile.profile_id,
        modulation=profile.modulation,
        symbol_rate_hz=symbol_rate,
        samples_per_symbol=sps,
        evm_rms_pct=evm_pct,
        mer_db=mer_db,
        constellation=plot_points,
        status=status,
        carrier_locked=bool(carrier_locked),
        timing_locked=bool(timing_locked),
        sync_ok=bool(carrier_locked and timing_locked),
    )


def analyze_digital_modulation(
    iq_samples: np.ndarray,
    params: SpectrumParams,
    *,
    sample_rate_hz: float,
    profile: DigitalSignalProfile | None = None,
) -> DigitalModAnalysis:
    """Constelación + EVM/MER (PSK/QAM) o DAB+ OFDM sincronizado."""
    prof = profile or get_digital_profile(params.digital_profile)
    if prof.modulation == "ofdm":
        return _analyze_dab_ofdm(
            iq_samples,
            params,
            sample_rate_hz=sample_rate_hz,
            profile=prof,
        )
    return _analyze_psk_qam(
        iq_samples,
        params,
        sample_rate_hz=sample_rate_hz,
        profile=prof,
    )
