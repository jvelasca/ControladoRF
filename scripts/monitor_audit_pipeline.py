#!/usr/bin/env python
"""Auditoria Monitor IQ: captura, FFT, escala y PNG de referencia.

Genera logs en logs/monitor_audit.log y PNG en logs/monitor_audit.png
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
LOG_DIR = ROOT / "logs"
sys.path.insert(0, str(SRC))

import numpy as np

from core.monitor.display_scale import apply_auto_vertical_scale
from core.monitor.hackrf_iq_capture import HackRfIqCapture
from core.monitor.iq_fft import compute_spectrum_frame, find_peak_excluding_dc, iq_bytes_to_complex
from core.monitor.monitor_bw_sweep_logic import patch_rbw_hz
from core.monitor.spectrum_params import SpectrumParams
from core.monitor.spectrum_plot_mapping import resample_power_to_grid


def _setup_log() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("monitor_audit")
    log.setLevel(logging.INFO)
    if not log.handlers:
        fh = logging.FileHandler(LOG_DIR / "monitor_audit.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(sh)
    return log


def _maybe_plot(freqs, power, path: Path, *, title: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    fig, ax = plt.subplots(figsize=(10, 4), dpi=100)
    mhz = np.asarray(freqs, dtype=float) / 1e6
    ax.plot(mhz, power, color="#00dc78", linewidth=0.8)
    ax.set_xlabel("MHz")
    ax.set_ylabel("dBFS")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fc", type=float, default=93.2e6)
    parser.add_argument("--rate", type=float, default=2e6)
    parser.add_argument("--fft", type=int, default=2048)
    parser.add_argument("--mock", action="store_true", help="Simular tono sin HackRF")
    args = parser.parse_args()
    log = _setup_log()

    params = SpectrumParams(
        center_freq_hz=args.fc,
        sample_rate_hz=args.rate,
        fft_size=args.fft,
        capture_mode="iq",
        ref_scale_auto=True,
        lna_gain_db=24,
        vga_gain_db=20,
    )
    params.sync_iq_display()

    if args.mock:
        samples = (0.35 * np.exp(2j * np.pi * 75_000.0 * np.arange(args.fft) / args.rate)).astype(np.complex64)
        log.info("Modo MOCK (sin HackRF)")
    else:
        cap = HackRfIqCapture()
        cap.configure(
            center_freq_hz=args.fc,
            sample_rate_hz=args.rate,
            lna_gain=24,
            vga_gain=20,
            rf_amp_enable=False,
        )
        ok, msg = cap.start()
        if not ok:
            log.error("HackRF start fallo: %s", msg)
            return 1
        log.info("HackRF: %s", msg)
        time.sleep(0.5)
        block = cap.read_iq_block(args.fft, wait_sec=2.0)
        cap.stop()
        if block is None:
            log.error("Sin muestras IQ")
            return 1
        samples = iq_bytes_to_complex(block, num_samples=args.fft)

    frame = compute_spectrum_frame(samples, params)
    peak = find_peak_excluding_dc(
        frame.freqs_hz,
        frame.power_db,
        center_freq_hz=params.center_freq_hz,
        sample_rate_hz=params.sample_rate_hz,
    )
    if peak is None:
        log.warning("Sin pico fuera de DC")
    else:
        log.info(
            "Pico %.3f MHz (offset %+.1f kHz) potencia %.1f dBFS",
            peak[0] / 1e6,
            (peak[0] - params.center_freq_hz) / 1e3,
            peak[1],
        )

    scaled = apply_auto_vertical_scale(frame, params)
    log.info("AUTO escala: ref=%.1f dB rango=%.0f dB", scaled.ref_level_dbm, scaled.ref_range_db)

    rbw_test = patch_rbw_hz(params.copy(), 100_000.0)
    log.info("RBW manual IQ: fft_size sigue=%s rbw=%.0f Hz", rbw_test.fft_size, rbw_test.rbw_hz)

    grid = resample_power_to_grid(
        frame.freqs_hz,
        scaled.power_db,
        start_hz=float(frame.freqs_hz[0]),
        stop_hz=float(frame.freqs_hz[-1]),
        num_columns=800,
    )
    log.info("Rejilla pintado: cols=%s pico_grid=%.1f dBFS", grid.size, float(np.max(grid)))

    png = LOG_DIR / "monitor_audit.png"
    _maybe_plot(frame.freqs_hz, scaled.power_db, png, title="Monitor audit (dBFS + AUTO)")
    if png.exists():
        log.info("PNG: %s", png)
    log.info("Auditoria OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
