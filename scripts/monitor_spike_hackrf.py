#!/usr/bin/env python
"""Spike HackRF: open con timeout en subproceso (sin colgar terminal)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _worker_code() -> str:
    return f"""
import sys
sys.path.insert(0, r'{SRC}')
from core.monitor.spectrum_source import HackRFSpectrumSource
src = HackRFSpectrumSource()
ok, msg = src.open()
print('RESULT', ok, msg)
if ok:
    src.close()
sys.exit(0 if ok else 1)
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args()

    print(f"Abriendo HackRF en subproceso (timeout {args.timeout}s)…")
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _worker_code()],
            capture_output=True,
            text=True,
            timeout=args.timeout,
            cwd=str(ROOT),
        )
    except subprocess.TimeoutExpired:
        print("FAIL: timeout — el driver/backend bloquea el open")
        return 1

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    print(out or err or f"exit={proc.returncode}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
