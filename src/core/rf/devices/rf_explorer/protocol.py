"""Protocolo UART RF Explorer (500000 baud)."""
from __future__ import annotations

from typing import Iterable

import numpy as np

from core.rf.devices.common.serial_link import SerialLink

_RF_EXPLORER_BAUD = 500_000


def reset_device(link: SerialLink) -> None:
    link.reset_input()
    link.write_bytes(b"#\x04\x00\x00")
    link.read_line(timeout_sec=1.5)


def configure_sweep(
    link: SerialLink,
    *,
    start_hz: float,
    stop_hz: float,
    top_dbm: float = -30.0,
    bottom_dbm: float = -110.0,
) -> None:
    start_mhz = start_hz / 1_000_000.0
    stop_mhz = stop_hz / 1_000_000.0
    cmd = f"#C2-F:{start_mhz:.3f},{stop_mhz:.3f},{top_dbm:.1f},{bottom_dbm:.1f}"
    link.write_line(cmd)
    link.read_line(timeout_sec=1.0)


def request_sweep(link: SerialLink, *, timeout_sec: float = 15.0) -> tuple[np.ndarray, np.ndarray]:
    """Solicita traza y parsea líneas ``$S`` del firmware RF Explorer."""
    link.write_line("#C2-:")
    lines = link.read_lines_until(
        timeout_sec=timeout_sec,
        stop_when=lambda line, _all: line.startswith("$S") and len(_all) >= 2,
        max_lines=8192,
    )
    sweep_lines = [line for line in lines if line.startswith("$S")]
    if not sweep_lines:
        raise RuntimeError("RF Explorer: sin datos de barrido (compruebe modelo, span y puerto COM)")

    freqs: list[float] = []
    levels: list[float] = []
    for line in sweep_lines:
        parsed = _parse_sweep_line(line)
        if parsed is None:
            continue
        f_vals, p_vals = parsed
        freqs.extend(f_vals)
        levels.extend(p_vals)

    if len(freqs) < 2:
        raise RuntimeError("RF Explorer: traza vacía o formato no reconocido")

    return np.asarray(freqs, dtype=np.float64), np.asarray(levels, dtype=np.float64)


def _parse_sweep_line(line: str) -> tuple[list[float], list[float]] | None:
    """Parsea ``$S`` con pares frecuencia (MHz), nivel (dBm)."""
    body = line[2:].strip()
    if not body:
        return None
    parts = [p for p in body.replace(";", ",").split(",") if p.strip()]
    if len(parts) < 3:
        return None
    try:
        start_mhz = float(parts[0])
        step_mhz = float(parts[1])
        values = [float(v) for v in parts[2:]]
    except ValueError:
        return None
    if step_mhz <= 0.0:
        return None
    freqs = [ (start_mhz + step_mhz * i) * 1_000_000.0 for i in range(len(values))]
    return freqs, values


def list_serial_candidates(ports: Iterable[object]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for port in ports:
        device = str(getattr(port, "device", "") or "")
        desc = str(getattr(port, "description", "") or "")
        hwid = str(getattr(port, "hwid", "") or "")
        blob = f"{desc} {hwid}".lower()
        if "rf explorer" in blob or "rfexplorer" in blob:
            label = desc.strip() or "RF Explorer"
            found.append((device, label))
            continue
        if "cp210" in blob and "10c4:ea60" in blob.replace(":", "").lower():
            if "rf" in blob or "explorer" in blob:
                label = desc.strip() or "RF Explorer (CP210x)"
                found.append((device, label))
    return found
