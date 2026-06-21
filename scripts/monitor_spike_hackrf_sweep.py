#!/usr/bin/env python
"""Spike Fase B: un barrido HackRF real vía hackrf_sweep."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.monitor.spectrum_params import SpectrumParams
from core.monitor.spectrum_source import HackRFSpectrumSource


def main() -> int:
    src = HackRFSpectrumSource()
    ok, msg = src.open()
    print("open:", ok, msg)
    if not ok:
        return 1
    params = SpectrumParams(center_freq_hz=100e6, span_hz=20e6, fft_size=512)
    frame = src.read_frame(params)
    power = frame.power_db
    print("bins:", len(power), "min/max dB:", float(min(power)), float(max(power)))
    src.close()
    return 0 if len(power) >= 256 else 2


if __name__ == "__main__":
    raise SystemExit(main())
