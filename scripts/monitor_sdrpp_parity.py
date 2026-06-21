#!/usr/bin/env python3
"""Compara parámetros ControladoRF vs SDR++ para HackRF FM."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.monitor.hackrf_baseband import default_baseband_filter_for_sample_rate
from core.monitor.iq_sdr_profile import prepare_iq_for_play
from core.monitor.spectrum_params import SpectrumParams


def main() -> int:
    parser = argparse.ArgumentParser(description="Paridad SDR++ / ControladoRF IQ")
    parser.add_argument("--fc", type=float, default=93.2e6)
    parser.add_argument("--rate", type=float, default=2e6)
    parser.add_argument("--lna", type=int, default=24)
    parser.add_argument("--vga", type=int, default=34)
    parser.add_argument("--amp", action="store_true")
    args = parser.parse_args()

    params = SpectrumParams(
        capture_mode="iq",
        center_freq_hz=args.fc,
        sample_rate_hz=args.rate,
        manual_span_hz=args.rate,
        lna_gain_db=args.lna,
        vga_gain_db=args.vga,
        rf_amp_enable=args.amp,
        operating_mode="sdr",
        demod_mode="fm",
        audio_enabled=True,
    )
    prepare_iq_for_play(params)

    bb = default_baseband_filter_for_sample_rate(params.sample_rate_hz)
    print("=== Perfil SDR++ equivalente ===")
    print(f"  FC:        {params.center_freq_hz/1e6:.3f} MHz")
    print(f"  Sample rate (BW toolbar): {params.sample_rate_hz/1e6:.2f} Msps")
    print(f"  Filtro FI (auto 75%):     {bb/1e6:.2f} MHz  (SDR++ Bandwidth auto)")
    print(f"  LNA:       {params.lna_gain_db} dB")
    print(f"  VGA:       {params.vga_gain_db} dB")
    print(f"  P (amp):   {'ON' if params.rf_amp_enable else 'OFF'}")
    print(f"  RBW pantalla: {params.effective_rbw_hz():.1f} Hz (= SR/FFT)")
    print(f"  FFT size:  {params.fft_size}")
    print()
    print("hackrf_transfer equivalente:")
    print(
        f"  hackrf_transfer -r - -f {int(params.center_freq_hz)} "
        f"-s {int(params.sample_rate_hz)} -b {bb} "
        f"-l {params.lna_gain_db} -g {params.vga_gain_db} "
        f"-a {1 if params.rf_amp_enable else 0}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
