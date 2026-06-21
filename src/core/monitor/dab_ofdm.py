"""DAB/DAB+ Mode I — sincronismo OFDM, demod diferencial y detección de ensemble."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# ETSI EN 300 401 Mode I @ 2.048 Msps
DAB_SAMPLE_RATE_HZ = 2_048_000.0
DAB_FFT_SIZE = 2048
DAB_TU_SAMPLES = 2048
DAB_TG_SAMPLES = 246
DAB_TS_SAMPLES = DAB_TU_SAMPLES + DAB_TG_SAMPLES
DAB_ACTIVE_CARRIERS = 1536
DAB_BLOCK_SPACING_MHZ = 1.792
DAB_BLOCK_FIRST_MHZ = 174.928
MAX_CONSTELLATION_POINTS = 512


@dataclass(frozen=True)
class DabOfdmResult:
    valid: bool
    sync_ok: bool
    ensemble_detected: bool
    cp_correlation: float
    symbol_offset: int
    symbols_used: int
    active_carriers: int
    evm_rms_pct: float | None
    mer_db: float | None
    constellation: np.ndarray
    null_symbol_ratio: float
    block_center_mhz: float | None
    status: str


def nearest_dab_block_center_hz(freq_hz: float) -> tuple[float, int]:
    """Centro de bloque DAB Band III más cercano (174.928 MHz + n·1.792 MHz)."""
    freq_mhz = float(freq_hz) / 1e6
    index = int(round((freq_mhz - DAB_BLOCK_FIRST_MHZ) / DAB_BLOCK_SPACING_MHZ))
    index = max(0, min(40, index))
    center_mhz = DAB_BLOCK_FIRST_MHZ + index * DAB_BLOCK_SPACING_MHZ
    return center_mhz * 1e6, index


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
    if n < 64:
        return x
    spec = np.fft.fftshift(np.fft.fft(x))
    freqs = np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / float(sample_rate_hz)))
    mask = np.abs(freqs) <= max(1_000.0, float(bandwidth_hz) * 0.55)
    return np.fft.ifft(np.fft.ifftshift(spec * mask)).astype(np.complex64)


def _find_cp_sync(
    samples: np.ndarray,
    *,
    tu: int = DAB_TU_SAMPLES,
    tg: int = DAB_TG_SAMPLES,
    search_samples: int = 12_000,
) -> tuple[int, float]:
    """Correlación intervalo de guarda → inicio de símbolo OFDM."""
    x = np.asarray(samples, dtype=np.complex64).reshape(-1)
    need = tu + tg
    if x.size < need + tg:
        return 0, 0.0
    limit = min(int(search_samples), x.size - need)
    best_pos = 0
    best_corr = 0.0
    step = max(1, tg // 8)
    for pos in range(0, max(1, limit), step):
        cp = x[pos : pos + tg]
        tail = x[pos + tu : pos + tu + tg]
        corr = float(np.abs(np.vdot(cp, tail)))
        if corr > best_corr:
            best_corr = corr
            best_pos = pos
    return int(best_pos), best_corr


def _extract_ofdm_symbols(
    samples: np.ndarray,
    *,
    offset: int,
    max_symbols: int = 8,
) -> list[np.ndarray]:
    """FFT de símbolos alineados (sin CP) → espectro de portadoras."""
    x = np.asarray(samples, dtype=np.complex64).reshape(-1)
    symbols: list[np.ndarray] = []
    pos = int(offset) + DAB_TG_SAMPLES
    for _ in range(max_symbols):
        if pos + DAB_TU_SAMPLES > x.size:
            break
        seg = x[pos : pos + DAB_TU_SAMPLES]
        energy = float(np.mean(np.abs(seg) ** 2))
        if energy < 1e-12:
            break
        spec = np.fft.fftshift(np.fft.fft(seg))
        margin = max(0, (DAB_FFT_SIZE - DAB_ACTIVE_CARRIERS) // 2)
        carriers = spec[margin : margin + DAB_ACTIVE_CARRIERS]
        symbols.append(carriers.astype(np.complex64))
        pos += DAB_TS_SAMPLES
    return symbols


def _differential_qpsk(symbols: list[np.ndarray]) -> np.ndarray:
    if len(symbols) < 2:
        return np.zeros(0, dtype=np.complex64)
    diffs: list[np.ndarray] = []
    for idx in range(1, len(symbols)):
        prev = symbols[idx - 1]
        curr = symbols[idx]
        if prev.size == 0 or curr.size != prev.size:
            continue
        d = curr * np.conjugate(prev)
        mask = (np.abs(prev) > 1e-9) & (np.abs(curr) > 1e-9)
        if not np.any(mask):
            continue
        diffs.append(d[mask])
    if not diffs:
        return np.zeros(0, dtype=np.complex64)
    return np.concatenate(diffs).astype(np.complex64)


def _qpsk_evm_mer(diff_symbols: np.ndarray) -> tuple[float | None, float | None]:
    x = np.asarray(diff_symbols, dtype=np.complex64).reshape(-1)
    if x.size < 32:
        return None, None
    unit = x / (np.abs(x) + 1e-9)
    ideal = np.array(
        [1 + 1j, -1 + 1j, -1 - 1j, 1 - 1j],
        dtype=np.complex64,
    ) / math.sqrt(2.0)
    dist = np.abs(unit.reshape(-1, 1) - ideal.reshape(1, -1))
    nearest = ideal[np.argmin(dist, axis=1)]
    err = unit - nearest
    evm_rms = float(np.sqrt(np.mean(np.abs(err) ** 2) / (np.mean(np.abs(nearest) ** 2) + 1e-12)))
    evm_pct = evm_rms * 100.0
    err_pwr = float(np.mean(np.abs(err) ** 2))
    sig_pwr = float(np.mean(np.abs(nearest) ** 2))
    mer_db = 60.0 if err_pwr <= 1e-15 else float(10.0 * math.log10(sig_pwr / err_pwr))
    return evm_pct, mer_db


def _decimate(points: np.ndarray) -> np.ndarray:
    x = np.asarray(points, dtype=np.complex64).reshape(-1)
    if x.size <= MAX_CONSTELLATION_POINTS:
        return x
    step = max(1, x.size // MAX_CONSTELLATION_POINTS)
    return x[::step][:MAX_CONSTELLATION_POINTS]


def _null_symbol_ratio(symbols: list[np.ndarray], samples: np.ndarray, offset: int) -> float:
    """Ratio energía mínima / media — detecta símbolo nulo DAB."""
    if not symbols:
        return 1.0
    x = np.asarray(samples, dtype=np.complex64).reshape(-1)
    energies: list[float] = []
    pos = int(offset) + DAB_TG_SAMPLES
    for _ in range(min(12, len(symbols) + 2)):
        if pos + DAB_TU_SAMPLES > x.size:
            break
        seg = x[pos : pos + DAB_TU_SAMPLES]
        energies.append(float(np.mean(np.abs(seg) ** 2)))
        pos += DAB_TS_SAMPLES
    if len(energies) < 3:
        return 1.0
    arr = np.asarray(energies, dtype=np.float64)
    mean_e = float(np.mean(arr) + 1e-12)
    return float(np.min(arr) / mean_e)


def analyze_dab_ofdm(
    iq_samples: np.ndarray,
    *,
    sample_rate_hz: float,
    center_freq_hz: float,
    vfo_freq_hz: float,
    channel_bw_hz: float = 1_536_000.0,
) -> DabOfdmResult:
    """Análisis DAB+ Mode I: sync CP, QPSK diferencial, ensemble."""
    empty = DabOfdmResult(
        valid=False,
        sync_ok=False,
        ensemble_detected=False,
        cp_correlation=0.0,
        symbol_offset=0,
        symbols_used=0,
        active_carriers=0,
        evm_rms_pct=None,
        mer_db=None,
        constellation=np.zeros(0, dtype=np.complex64),
        null_symbol_ratio=1.0,
        block_center_mhz=None,
        status="DAB+ — IQ insuficiente",
    )
    x = np.asarray(iq_samples, dtype=np.complex64).reshape(-1)
    if x.size < DAB_TS_SAMPLES * 3:
        return empty

    rate = float(sample_rate_hz)
    if abs(rate - DAB_SAMPLE_RATE_HZ) > 120_000.0:
        return DabOfdmResult(
            valid=False,
            sync_ok=False,
            ensemble_detected=False,
            cp_correlation=0.0,
            symbol_offset=0,
            symbols_used=0,
            active_carriers=0,
            evm_rms_pct=None,
            mer_db=None,
            constellation=np.zeros(0, dtype=np.complex64),
            null_symbol_ratio=1.0,
            block_center_mhz=None,
            status=f"DAB+ — sample rate {rate / 1e6:.2f} MHz (use 2.048 MHz)",
        )

    offset_hz = float(vfo_freq_hz) - float(center_freq_hz)
    x = _frequency_shift(x, offset_hz, rate)
    x = _channel_lowpass(x, bandwidth_hz=channel_bw_hz, sample_rate_hz=rate)

    sym_offset, cp_corr = _find_cp_sync(x)
    symbols = _extract_ofdm_symbols(x, offset=sym_offset, max_symbols=10)
    if len(symbols) < 2:
        return DabOfdmResult(
            valid=False,
            sync_ok=False,
            ensemble_detected=False,
            cp_correlation=cp_corr,
            symbol_offset=sym_offset,
            symbols_used=len(symbols),
            active_carriers=0,
            evm_rms_pct=None,
            mer_db=None,
            constellation=np.zeros(0, dtype=np.complex64),
            null_symbol_ratio=1.0,
            block_center_mhz=None,
            status="DAB+ — sin sincronismo OFDM",
        )

    stack = np.stack(symbols, axis=0)
    power = np.mean(np.abs(stack) ** 2, axis=0)
    peak_pwr = float(np.max(power) + 1e-12)
    active_count = int(np.sum(power > peak_pwr * 0.15))

    diff = _differential_qpsk(symbols)
    if diff.size < 64:
        return DabOfdmResult(
            valid=False,
            sync_ok=cp_corr > 0.0,
            ensemble_detected=False,
            cp_correlation=cp_corr,
            symbol_offset=sym_offset,
            symbols_used=len(symbols),
            active_carriers=active_count,
            evm_rms_pct=None,
            mer_db=None,
            constellation=np.zeros(0, dtype=np.complex64),
            null_symbol_ratio=_null_symbol_ratio(symbols, x, sym_offset),
            block_center_mhz=None,
            status="DAB+ — demod diferencial fallida",
        )

    unit = diff / (np.abs(diff) + 1e-9)
    evm_pct, mer_db = _qpsk_evm_mer(diff)
    plot = _decimate(unit.astype(np.complex64))
    null_ratio = _null_symbol_ratio(symbols, x, sym_offset)

    block_hz, _block_idx = nearest_dab_block_center_hz(vfo_freq_hz or center_freq_hz)
    block_mhz = block_hz / 1e6

    ref_energy = float(np.mean(np.abs(x) ** 2) + 1e-12)
    cp_norm = cp_corr / max(ref_energy * DAB_TG_SAMPLES, 1e-12)
    sync_ok = cp_norm > 0.02 and active_count >= 400
    ensemble = (
        sync_ok
        and active_count >= 800
        and evm_pct is not None
        and evm_pct < 45.0
        and (mer_db is None or mer_db > 4.0)
    )

    status = (
        f"DAB+ · sync {'OK' if sync_ok else '—'} · "
        f"{active_count} portadoras · {len(symbols)} sym"
    )
    if ensemble:
        status += f" · ENSEMBLE · bloque ~{block_mhz:.3f} MHz"
    if evm_pct is not None:
        status += f" · EVM {evm_pct:.1f}%"
    if null_ratio < 0.15:
        status += " · null sym"

    return DabOfdmResult(
        valid=True,
        sync_ok=sync_ok,
        ensemble_detected=ensemble,
        cp_correlation=cp_corr,
        symbol_offset=sym_offset,
        symbols_used=len(symbols),
        active_carriers=active_count,
        evm_rms_pct=evm_pct,
        mer_db=mer_db,
        constellation=plot,
        null_symbol_ratio=null_ratio,
        block_center_mhz=block_mhz,
        status=status,
    )
