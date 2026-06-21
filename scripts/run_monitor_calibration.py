#!/usr/bin/env python
"""Calibración profesional cadena Monitor: SPAN, IQ↔barrido, RBW/FFT/SWT.

Inspirado en self-test de analizadores R&S / Keysight: trazabilidad completa
entrada RF → adquisición → análisis → rejilla visual.

Uso:
  .\\env\\Scripts\\python.exe scripts\\run_monitor_calibration.py
  .\\env\\Scripts\\python.exe scripts\\run_monitor_calibration.py --quick
  .\\env\\Scripts\\python.exe scripts\\run_monitor_calibration.py --live --fc 93.2e6

Salida: logs/calibration/calibration_*.json y calibration_latest.md
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
LOG_DIR = ROOT / "logs" / "calibration"
sys.path.insert(0, str(SRC))

from core.monitor.calibration.harness import CalibrationHarness


def _setup_log() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("monitor_calibration")
    log.setLevel(logging.INFO)
    if not log.handlers:
        fh = logging.FileHandler(LOG_DIR / "calibration_run.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(sh)
    return log


def _run_live_probe(log: logging.Logger, fc: float, span: float) -> int:
    """Captura corta HackRF en el escenario dado (validación hardware)."""
    try:
        from core.monitor.hackrf_iq_capture import HackRfIqCapture
        from core.monitor.iq_fft import compute_spectrum_frame, find_peak_excluding_dc, iq_bytes_to_complex
        from core.monitor.monitor_freq_span_logic import patch_manual_span
        from core.monitor.spectrum_params import SpectrumParams
        from core.rf.bridge import prepare_params_for_capture
    except ImportError as exc:
        log.error("Live probe no disponible: %s", exc)
        return 1

    params = SpectrumParams(
        center_freq_hz=fc,
        source_id="hackrf",
        operating_mode="spectrum",
        span_mode="manual",
    )
    params = patch_manual_span(params, span)
    params = prepare_params_for_capture(params)
    log.info(
        "Live: mode=%s span=%.2f MHz sr=%.2f MHz fft=%s rbw=%.0f Hz",
        params.capture_mode,
        params.span_hz / 1e6,
        params.sample_rate_hz / 1e6,
        params.fft_size,
        params.effective_rbw_hz(),
    )

    if params.capture_mode == "sweep":
        log.info("Modo barrido: validación hardware requiere hackrf_sweep (omitido en probe IQ)")
        return 0

    cap = HackRfIqCapture()
    cap.configure(
        center_freq_hz=fc,
        sample_rate_hz=params.sample_rate_hz,
        lna_gain=24,
        vga_gain=20,
        rf_amp_enable=False,
    )
    ok, msg = cap.start()
    if not ok:
        log.error("HackRF: %s", msg)
        return 1
    time.sleep(0.3)
    block = cap.read_iq_block(params.fft_size, wait_sec=3.0)
    cap.stop()
    if block is None:
        log.error("Sin muestras IQ")
        return 1
    samples = iq_bytes_to_complex(block, num_samples=params.fft_size)
    frame = compute_spectrum_frame(samples, params)
    peak = find_peak_excluding_dc(
        frame.freqs_hz, frame.power_db, center_freq_hz=fc, sample_rate_hz=params.sample_rate_hz
    )
    if peak:
        log.info("Pico %.3f MHz %.1f dBFS", peak[0] / 1e6, peak[1])
    else:
        log.warning("Sin pico detectable (ruido o antena desconectada)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibración cadena Monitor")
    parser.add_argument("--quick", action="store_true", help="Solo rejilla SPAN (sin flags)")
    parser.add_argument("--live", action="store_true", help="Probe HackRF tras matriz offline")
    parser.add_argument("--fc", type=float, default=93.2e6, help="FC para --live")
    parser.add_argument("--live-span", type=float, default=10e6, help="SPAN para --live")
    args = parser.parse_args()

    log = _setup_log()
    harness = CalibrationHarness(on_progress=log.info)
    log.info("=== Calibración Monitor (matriz offline) ===")
    report = harness.run_matrix(include_flags=not args.quick)
    json_path, md_path = harness.write_reports(report, LOG_DIR)

    log.info("Escenarios: %d  PASS: %d  FAIL: %d", report.total, report.passed, report.failed)
    log.info("JSON: %s", json_path)
    log.info("Markdown: %s", md_path)

    if args.live:
        log.info("=== Live probe HackRF ===")
        code = _run_live_probe(log, args.fc, args.live_span)
        if code != 0:
            return code

    if not report.ok:
        log.error("Calibración FALLIDA — revisar %s", md_path)
        return 1
    log.info("Calibración OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
