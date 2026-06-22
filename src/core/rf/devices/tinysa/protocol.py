"""Protocolo consola TinySA (115200 baud)."""
from __future__ import annotations

import re
from typing import Iterable

import numpy as np

from core.rf.devices.common.serial_link import SerialLink

_TINYSA_BAUD = 115200
_MIN_POINTS = 101
_MAX_POINTS = 290


def _clamp_points(requested: int, span_hz: float) -> int:
    n = max(_MIN_POINTS, min(_MAX_POINTS, int(requested)))
    if span_hz <= 2_000_000.0:
        return max(_MIN_POINTS, min(n, 201))
    return n


def scanraw_spectrum(
    link: SerialLink,
    *,
    start_hz: float,
    stop_hz: float,
    num_points: int,
    timeout_sec: float = 12.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Ejecuta ``scanraw start stop steps`` y parsea frecuencia/nivel."""
    if stop_hz <= start_hz:
        raise ValueError("stop_hz must exceed start_hz")

    points = _clamp_points(num_points, stop_hz - start_hz)
    link.reset_input()
    link.write_line(f"scanraw {int(start_hz)} {int(stop_hz)} {points}")

    freqs: list[float] = []
    levels: list[float] = []

    def _done(line: str, _lines: list[str]) -> bool:
        return line.lower().startswith("ch>") or line.lower().startswith("done")

    raw_lines = link.read_lines_until(timeout_sec=timeout_sec, stop_when=_done)
    for line in raw_lines:
        parsed = _parse_scan_line(line)
        if parsed is None:
            continue
        freq, level = parsed
        freqs.append(freq)
        levels.append(level)

    if len(freqs) < 2:
        raise RuntimeError("TinySA: sin datos de barrido (compruebe conexión USB y puerto COM)")

    return np.asarray(freqs, dtype=np.float64), np.asarray(levels, dtype=np.float64)


def _parse_scan_line(line: str) -> tuple[float, float] | None:
    cleaned = line.strip()
    if not cleaned or cleaned.startswith("#"):
        return None
    if cleaned.lower().startswith(("scan", "ch>", "done", "error")):
        return None
    parts = re.split(r"[\s,;]+", cleaned)
    if len(parts) < 2:
        return None
    try:
        freq = float(parts[0])
        level = float(parts[1])
    except ValueError:
        return None
    if freq <= 0.0:
        return None
    return freq, level


def list_serial_candidates(ports: Iterable[object]) -> list[tuple[str, str]]:
    """Filtra puertos COM con descripción TinySA."""
    found: list[tuple[str, str]] = []
    for port in ports:
        device = str(getattr(port, "device", "") or "")
        desc = str(getattr(port, "description", "") or "")
        hwid = str(getattr(port, "hwid", "") or "")
        blob = f"{desc} {hwid}".lower()
        if "tinysa" in blob or "tiny sa" in blob:
            label = desc.strip() or "TinySA"
            found.append((device, label))
    return found
