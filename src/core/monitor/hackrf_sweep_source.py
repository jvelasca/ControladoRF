"""Captura de espectro HackRF vía hackrf_sweep (libhackrf CLI)."""
from __future__ import annotations

import math
import subprocess
import time
from typing import List, Optional, Tuple

import numpy as np

from core.monitor.hackrf_paths import resolve_hackrf_tool
from core.rf.display import display_trace_bins
from core.monitor.monitor_mode_profile import source_freq_limits_hz, sweep_timeout_sec
from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams
from utils.subprocess_platform import run_hidden

# Valores absurdos que hackrf_sweep puede emitir en bordes de segmento / sin datos.
SWEEP_POWER_MIN_DB = -140.0
SWEEP_SPIKE_MARGIN_DB = 10.0


def _mhz(hz: float) -> float:
    return hz / 1_000_000.0


def sanitize_sweep_spectrum(
    freqs_hz: np.ndarray,
    power_db: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Limpia barrido hackrf_sweep: fusiona solapes y suprime picos hacia abajo."""
    freqs = np.asarray(freqs_hz, dtype=float).reshape(-1)
    power = np.asarray(power_db, dtype=float).reshape(-1)
    n = min(freqs.size, power.size)
    if n == 0:
        return freqs[:0], power[:0]
    freqs = freqs[:n]
    power = power[:n]
    valid = np.isfinite(freqs) & np.isfinite(power) & (power > SWEEP_POWER_MIN_DB)
    freqs = freqs[valid]
    power = power[valid]
    if freqs.size == 0:
        return freqs, power

    order = np.argsort(freqs, kind="mergesort")
    freqs = freqs[order]
    power = power[order]

    uniq_freqs, inv = np.unique(freqs, return_inverse=True)
    if uniq_freqs.size < freqs.size:
        merged = np.full(uniq_freqs.size, SWEEP_POWER_MIN_DB, dtype=float)
        for idx, value in enumerate(power):
            slot = inv[idx]
            merged[slot] = max(merged[slot], float(value))
        freqs = uniq_freqs
        power = merged

    if power.size >= 5:
        noise_floor = float(np.percentile(power, 20))
        floor_db = noise_floor - SWEEP_SPIKE_MARGIN_DB
        local = np.convolve(power, np.array([0.25, 0.5, 0.25], dtype=float), mode="same")
        isolated_drop = (power < floor_db) & (power + 12.0 < local)
        power = np.where(isolated_drop, np.maximum(power, local - 2.0), power)

    return freqs, power


def resample_sweep_to_display_bins(
    freqs_hz: np.ndarray,
    power_db: np.ndarray,
    *,
    num_bins: int,
    plot_start_hz: float | None = None,
    plot_stop_hz: float | None = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Rejilla uniforme con suelo de extrapolación (evita muescas en bordes)."""
    from core.monitor.spectrum_plot_mapping import resample_power_to_grid

    freqs, power = sanitize_sweep_spectrum(freqs_hz, power_db)
    if freqs.size < 2:
        return freqs, power
    data_start = float(freqs[0])
    data_stop = float(freqs[-1])
    start = data_start if plot_start_hz is None else float(plot_start_hz)
    stop = data_stop if plot_stop_hz is None else float(plot_stop_hz)
    if stop <= start:
        start, stop = data_start, data_stop
    num_bins = max(2, int(num_bins))
    grid_power = resample_power_to_grid(
        freqs,
        power,
        start_hz=start,
        stop_hz=stop,
        num_columns=num_bins,
    )
    grid_freqs = np.linspace(start, stop, num_bins, dtype=float)
    return grid_freqs, grid_power.astype(float)


def parse_hackrf_sweep_output(text: str) -> Tuple[np.ndarray, np.ndarray]:
    """Parsea salida CSV de hackrf_sweep en freq/power arrays."""
    freq_chunks: List[np.ndarray] = []
    power_chunks: List[np.ndarray] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("call ") or line.startswith("Sweeping"):
            continue
        if line.startswith("Stop ") or line.startswith("Total ") or line.startswith("Exiting"):
            continue
        if line.startswith("hackrf_") or line.startswith("exit"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 7:
            continue
        try:
            hz_low = float(parts[2])
            hz_high = float(parts[3])
            bin_width = float(parts[4])
            _num_bins = int(float(parts[5]))
            powers = np.array([float(x) for x in parts[6:]], dtype=float)
        except ValueError:
            continue
        if powers.size == 0:
            continue
        freqs = hz_low + np.arange(powers.size, dtype=float) * bin_width
        freq_chunks.append(freqs)
        power_chunks.append(powers)
    if not freq_chunks:
        return np.array([]), np.array([])
    freqs = np.concatenate(freq_chunks)
    power = np.concatenate(power_chunks)
    order = np.argsort(freqs)
    return freqs[order], power[order]


def run_hackrf_sweep(params: SpectrumParams, *, timeout_sec: Optional[float] = None) -> SpectrumFrame:
    exe = resolve_hackrf_tool("hackrf_sweep")
    if exe is None:
        raise RuntimeError("hackrf_sweep no encontrado — ejecute scripts/install_hackrf_windows.ps1")

    start_hz = max(source_freq_limits_hz(params.source_id)[0], params.freq_start_hz())
    stop_hz = min(source_freq_limits_hz(params.source_id)[1], params.freq_stop_hz())
    start_mhz = int(math.floor(_mhz(start_hz)))
    stop_mhz = int(math.ceil(_mhz(stop_hz)))
    if stop_mhz <= start_mhz:
        stop_mhz = start_mhz + 1

    bin_width_hz = max(int(params.effective_rbw_hz()), 100_000)
    timeout = timeout_sec if timeout_sec is not None else sweep_timeout_sec(params)
    cmd = [
        str(exe),
        "-f",
        f"{start_mhz}:{stop_mhz}",
        "-w",
        str(bin_width_hz),
        "-l",
        str(int(params.lna_gain_db)),
        "-g",
        str(int(params.vga_gain_db)),
        "-a",
        "1" if params.rf_amp_enable else "0",
        "-p",
        "1" if getattr(params, "rf_bias_tee_enable", False) else "0",
        "-1",
    ]
    env = None
    bin_dir = exe.parent
    if bin_dir:
        env = dict(**{k: v for k, v in __import__("os").environ.items()})
        env["PATH"] = str(bin_dir) + ";" + env.get("PATH", "")

    try:
        proc = run_hidden(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
            cwd=str(bin_dir) if bin_dir else None,
        )
    except subprocess.TimeoutExpired as exc:
        detail = (exc.stderr or b"").decode("utf-8", errors="replace")[:200]
        raise RuntimeError(
            f"hackrf_sweep superó {timeout:.0f}s (RBW/SPAN demasiado exigente). {detail}".strip()
        ) from exc
    merged = (proc.stdout or "") + "\n" + (proc.stderr or "")
    freqs, power = parse_hackrf_sweep_output(merged)
    if freqs.size == 0:
        err = (proc.stderr or proc.stdout or "sin datos").strip()[:400]
        if "Resource busy" in err or "busy" in err.lower():
            raise RuntimeError("HackRF ocupado — liberando IQ…")
        raise RuntimeError(f"hackrf_sweep sin datos: {err}")

    time.sleep(0.2)
    target_n = display_trace_bins(params)
    plot_start = float(start_hz)
    plot_stop = float(stop_hz)
    freqs, power = resample_sweep_to_display_bins(
        freqs,
        power,
        num_bins=target_n,
        plot_start_hz=plot_start,
        plot_stop_hz=plot_stop,
    )

    from core.monitor.hackrf_rx_gains import calibrate_hackrf_antenna_power_db

    power = calibrate_hackrf_antenna_power_db(
        power,
        lna_gain_db=int(params.lna_gain_db),
        vga_gain_db=int(params.vga_gain_db),
        rf_amp_enable=bool(params.rf_amp_enable),
    )
    from core.monitor.iq_fft import apply_display_band_edge_guard

    power = apply_display_band_edge_guard(power)
    display_span = params.display_span_hz()
    return SpectrumFrame(
        freqs_hz=freqs,
        power_db=power,
        center_freq_hz=params.center_freq_hz,
        span_hz=display_span,
        ref_level_dbm=params.ref_level_dbm,
        ref_range_db=params.ref_range_db,
    )
