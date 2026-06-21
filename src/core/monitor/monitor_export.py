"""Exportación de datos del Monitor (traza, instantáneas)."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Mapping, Optional, Tuple

import numpy as np

from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams

RF_TOOL_MIN_STEP_HZ = 25_000.0


class MonitorExportError(Exception):
    """Error al exportar datos del Monitor."""


class TraceExportFormat(str, Enum):
    """Formato de exportación de traza espectral."""

    CONTROLADORF = "controladorf"
    WORKBENCH = "workbench"
    SOUNDBASE = "soundbase"


def default_export_filename(
    kind: str,
    *,
    extension: str,
    timestamp: Optional[datetime] = None,
) -> str:
    when = timestamp or datetime.now(timezone.utc)
    stamp = when.strftime("%Y%m%d_%H%M%S")
    safe_kind = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in kind)
    return f"monitor_{safe_kind}_{stamp}.{extension.lstrip('.')}"


def rf_tool_scan_filename(frame: SpectrumFrame, *, prefix: str = "Scan") -> str:
    """Nombre estilo Scan_470-698.csv (SoundBase / Workbench)."""
    freqs, _power = _trace_arrays(frame)
    if freqs.size == 0:
        return f"{prefix}_export.csv"
    start_mhz = int(float(freqs[0]) / 1_000_000.0)
    stop_mhz = int(float(freqs[-1]) / 1_000_000.0)
    if stop_mhz < start_mhz:
        start_mhz, stop_mhz = stop_mhz, start_mhz
    return f"{prefix}_{start_mhz}-{stop_mhz}.csv"


def export_spectrum_trace_csv(
    frame: SpectrumFrame,
    params: SpectrumParams,
    path: str | Path,
    *,
    metadata: Optional[Mapping[str, str]] = None,
    export_format: TraceExportFormat | str = TraceExportFormat.CONTROLADORF,
) -> None:
    """Exporta la traza visible según el formato solicitado."""
    fmt = (
        export_format
        if isinstance(export_format, TraceExportFormat)
        else TraceExportFormat(str(export_format))
    )
    if fmt is TraceExportFormat.WORKBENCH:
        export_spectrum_trace_workbench_csv(frame, params, path)
        return
    if fmt is TraceExportFormat.SOUNDBASE:
        export_spectrum_trace_soundbase_csv(frame, params, path)
        return
    _export_spectrum_trace_controladorf_csv(frame, params, path, metadata=metadata)


def export_spectrum_trace_workbench_csv(
    frame: SpectrumFrame,
    params: SpectrumParams,
    path: str | Path,
) -> None:
    """Shure Wireless Workbench: pares MHz,dBm sin cabecera (importación de scan)."""
    _ = params
    freqs, power = _trace_arrays_binned(frame)
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as handle:
            for hz, dbm in zip(freqs, power, strict=False):
                mhz = float(hz) / 1_000_000.0
                handle.write(f"{mhz:.3f},{float(dbm):.1f}\n")
    except OSError as exc:
        raise MonitorExportError(str(exc)) from exc


def export_spectrum_trace_soundbase_csv(
    frame: SpectrumFrame,
    params: SpectrumParams,
    path: str | Path,
) -> None:
    """Shure SoundBase: CSV MHz/dBm con cabecera (carga de scan en Coord)."""
    _ = params
    freqs, power = _trace_arrays_binned(frame)
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, delimiter=",")
            writer.writerow(["Frequency_MHz", "Level_dBm"])
            for hz, dbm in zip(freqs, power, strict=False):
                writer.writerow(
                    [
                        f"{float(hz) / 1_000_000.0:.6f}",
                        f"{float(dbm):.2f}",
                    ]
                )
    except OSError as exc:
        raise MonitorExportError(str(exc)) from exc


def _export_spectrum_trace_controladorf_csv(
    frame: SpectrumFrame,
    params: SpectrumParams,
    path: str | Path,
    *,
    metadata: Optional[Mapping[str, str]] = None,
) -> None:
    """Exporta la traza visible (freq, potencia) en CSV con separador ; y BOM UTF-8."""
    target = Path(path)
    freqs, power = _trace_arrays(frame)
    meta = dict(metadata or {})
    meta.setdefault("exported_at", datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    meta.setdefault("center_freq_hz", f"{frame.center_freq_hz:.3f}")
    meta.setdefault("span_hz", f"{frame.span_hz:.3f}")
    meta.setdefault("source_id", params.source_id)
    meta.setdefault("trace_mode", params.trace_mode)
    meta.setdefault("detector", params.detector)
    meta.setdefault("rbw_hz", f"{params.effective_rbw_hz():.3f}")
    meta.setdefault("lna_db", str(int(params.lna_gain_db)))
    meta.setdefault("vga_db", str(int(params.vga_gain_db)))
    meta.setdefault("preamp", "1" if params.rf_amp_enable else "0")

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(["# CONTROLADORF Monitor export"])
            for key, value in meta.items():
                writer.writerow([f"# {key}", value])
            writer.writerow([])
            writer.writerow(["freq_hz", "freq_mhz", "power_dbm"])
            for hz, dbm in zip(freqs, power, strict=False):
                writer.writerow(
                    [
                        f"{float(hz):.3f}",
                        f"{float(hz) / 1_000_000.0:.9f}",
                        f"{float(dbm):.4f}",
                    ]
                )
    except OSError as exc:
        raise MonitorExportError(str(exc)) from exc


def _trace_arrays(frame: SpectrumFrame) -> Tuple[np.ndarray, np.ndarray]:
    freqs = np.asarray(frame.freqs_hz, dtype=float).ravel()
    power = np.asarray(frame.power_db, dtype=float).ravel()
    if freqs.size == 0 or power.size == 0:
        raise MonitorExportError("No hay traza para exportar")
    count = min(freqs.size, power.size)
    return freqs[:count], power[:count]


def _trace_arrays_binned(
    frame: SpectrumFrame,
    *,
    step_hz: float = RF_TOOL_MIN_STEP_HZ,
) -> Tuple[np.ndarray, np.ndarray]:
    """Agrupa la traza a pasos ≥ 25 kHz (requisito Workbench / herramientas RF)."""
    freqs, power = _trace_arrays(frame)
    step = max(float(step_hz), RF_TOOL_MIN_STEP_HZ)
    start = float(freqs[0])
    stop = float(freqs[-1])
    if stop <= start:
        return freqs, power

    edges = np.arange(start, stop + step, step)
    if edges.size < 2:
        return freqs, power

    bin_indices = np.clip(
        np.searchsorted(edges, freqs, side="right") - 1,
        0,
        len(edges) - 2,
    )
    centers = (edges[:-1] + edges[1:]) / 2.0
    binned_power = np.full(centers.shape, -120.0, dtype=float)
    for idx in range(centers.size):
        mask = bin_indices == idx
        if np.any(mask):
            binned_power[idx] = float(np.max(power[mask]))
    return centers, binned_power
