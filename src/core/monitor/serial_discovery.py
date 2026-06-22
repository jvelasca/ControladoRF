"""Descubrimiento de analizadores por puerto serie (RF Explorer, TinySA)."""
from __future__ import annotations

from typing import List

from core.monitor.device_discovery import SourceDescriptor
from core.rf.devices.rf_explorer.protocol import list_serial_candidates as rf_explorer_ports
from core.rf.devices.tinysa.protocol import list_serial_candidates as tinysa_ports
from core.rf.source_ids import format_serial_source_id


def _list_com_ports() -> list[object]:
    try:
        from serial.tools import list_ports  # type: ignore[import-untyped]
    except ImportError:
        return []
    return list(list_ports.comports())


def detect_serial_analyzers() -> List[SourceDescriptor]:
    """Detecta RF Explorer y TinySA en puertos COM/USB-serie."""
    ports = _list_com_ports()
    results: List[SourceDescriptor] = []
    found: set[str] = set()

    tinysa = tinysa_ports(ports)
    for index, (port, label) in enumerate(tinysa):
        source_id = format_serial_source_id("tinysa", port, index=index)
        found.add("tinysa")
        results.append(
            SourceDescriptor(
                source_id=source_id,
                display_name=f"{label} · {port}",
                available=True,
                detail=f"TinySA · puerto {port} · barrido scanraw",
                device_family="tinysa",
                backend_ready=True,
            )
        )

    rf_exp = rf_explorer_ports(ports)
    for index, (port, label) in enumerate(rf_exp):
        source_id = format_serial_source_id("rf_explorer", port, index=index)
        found.add("rf_explorer")
        results.append(
            SourceDescriptor(
                source_id=source_id,
                display_name=f"{label} · {port}",
                available=True,
                detail=f"RF Explorer · puerto {port} · barrido UART",
                device_family="rf_explorer",
                backend_ready=True,
            )
        )

    for placeholder in _offline_placeholders():
        if placeholder.device_family not in found:
            results.append(placeholder)
    return results


def _offline_placeholders() -> List[SourceDescriptor]:
    """Entradas de catálogo cuando no hay puerto detectado (asistente / selección manual)."""
    return [
        SourceDescriptor(
            source_id="tinysa",
            display_name="TinySA",
            available=False,
            detail="Conecte por USB o instale pyserial para detectar el puerto COM",
            device_family="tinysa",
            backend_ready=False,
        ),
        SourceDescriptor(
            source_id="rf_explorer",
            display_name="RF Explorer",
            available=False,
            detail="Conecte por USB (CP210x) o instale pyserial para detectar el puerto COM",
            device_family="rf_explorer",
            backend_ready=False,
        ),
    ]
