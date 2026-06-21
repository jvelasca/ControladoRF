#!/usr/bin/env python
"""Spike del motor FFT (mock) — tiempos de arranque/parada sin GUI."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.monitor.spectrum_engine import SpectrumEngine


def main() -> int:
    frames = []
    statuses = []

    engine = SpectrumEngine(
        on_frame=lambda f: frames.append(f),
        on_status=lambda s: statuses.append(s),
        on_running_changed=lambda r: print(f"  running={r}"),
    )

    print("Seleccionando mock…")
    ok, msg = engine.set_source("mock")
    print(f"  {ok}: {msg}")

    print("Iniciando (debe devolver al instante)…")
    t0 = time.perf_counter()
    ok, msg = engine.start()
    dt = (time.perf_counter() - t0) * 1000
    print(f"  start() {dt:.1f} ms -> {ok}: {msg}")
    if dt > 200:
        print("  AVISO: start() tardó demasiado (¿bloqueo en hilo GUI?)")
        return 1

    time.sleep(0.4)
    engine.stop()
    print(f"  frames={len(frames)} statuses={statuses[-3:]}")
    return 0 if len(frames) >= 1 else 2


if __name__ == "__main__":
    raise SystemExit(main())
