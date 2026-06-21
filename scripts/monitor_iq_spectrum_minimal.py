#!/usr/bin/env python
"""Prueba mínima: captura IQ HackRF + FFT sin GUI.

Comprueba que el pico RF real no coincide con FC (fuga LO en centro).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np

from core.monitor.hackrf_iq_capture import HackRfIqCapture
from core.monitor.iq_fft import compute_spectrum_frame, find_peak_excluding_dc, iq_bytes_to_complex
from core.monitor.spectrum_params import SpectrumParams


def main() -> int:
    parser = argparse.ArgumentParser(description="Test mínimo espectro IQ HackRF")
    parser.add_argument("--fc", type=float, default=93.2e6, help="Frecuencia central (Hz)")
    parser.add_argument("--rate", type=float, default=2e6, help="Sample rate (Hz)")
    parser.add_argument("--fft", type=int, default=2048, help="Tamaño FFT")
    parser.add_argument("--lna", type=int, default=24)
    parser.add_argument("--vga", type=int, default=20)
    args = parser.parse_args()

    cap = HackRfIqCapture()
    cap.configure(
        center_freq_hz=args.fc,
        sample_rate_hz=args.rate,
        lna_gain=args.lna,
        vga_gain=args.vga,
        rf_amp_enable=False,
    )
    print(f"Iniciando RX IQ {args.fc / 1e6:.3f} MHz · {args.rate / 1e6:.1f} Msps …")
    ok, msg = cap.start()
    if not ok:
        print(f"FAIL: {msg}")
        return 1
    print(msg)
    time.sleep(0.6)

    params = SpectrumParams(
        center_freq_hz=args.fc,
        sample_rate_hz=cap._sample_rate_hz,
        fft_size=args.fft,
        lna_gain_db=args.lna,
        vga_gain_db=args.vga,
    )
    block = cap.read_iq_block(args.fft, wait_sec=2.0)
    cap.stop()
    if block is None:
        print("FAIL: sin muestras IQ")
        return 1

    samples = iq_bytes_to_complex(block, num_samples=args.fft)
    frame = compute_spectrum_frame(samples, params)
    freqs = np.asarray(frame.freqs_hz, dtype=float)
    power = np.asarray(frame.power_db, dtype=float)

    raw_i = int(np.argmax(power))
    raw_peak_hz = float(freqs[raw_i])
    raw_peak_db = float(power[raw_i])

    peak = find_peak_excluding_dc(
        freqs,
        power,
        center_freq_hz=params.center_freq_hz,
        sample_rate_hz=params.sample_rate_hz,
    )
    if peak is None:
        print("FAIL: no se encontró pico fuera de DC")
        return 1

    peak_hz, peak_db = peak
    offset_khz = (peak_hz - params.center_freq_hz) / 1e3
    dc_offset_khz = (raw_peak_hz - params.center_freq_hz) / 1e3

    print(f"Pico bruto (con DC): {raw_peak_hz / 1e6:.6f} MHz  ({raw_peak_db:.1f} dB)  offset={dc_offset_khz:+.1f} kHz")
    print(f"Pico filtrado:       {peak_hz / 1e6:.6f} MHz  ({peak_db:.1f} dB)  offset={offset_khz:+.1f} kHz")
    print(f"Ruido p10: {float(np.percentile(power, 10)):.1f} dB · SNR~{peak_db - float(np.percentile(power, 10)):.1f} dB")

    if abs(offset_khz) < 5.0:
        print("WARN: pico filtrado muy cerca del centro — ¿antena/señal ausente o solo LO?")
        return 2
    print("OK: portadora fuera del centro (espectro usable)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
