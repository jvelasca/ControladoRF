#!/usr/bin/env python
"""Alias: redirige al informe completo monitor_sdr_setup.py."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent / "monitor_sdr_setup.py"
sys.argv[0] = str(TARGET)
runpy.run_path(str(TARGET), run_name="__main__")
