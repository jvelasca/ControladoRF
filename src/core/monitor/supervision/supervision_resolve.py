"""Resuelve metadatos de inventario para UI y espectro."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.inventory_channel import channel_key, find_equipo_in_list, normalize_equipo
from core.monitor.supervision.supervision_models import ResolvedSupervisionTarget, SupervisionState


def _equipo_label(item: Dict[str, Any]) -> str:
    name = str(item.get("channel_name") or "").strip()
    if name:
        return name
    device = str(item.get("device_name") or "").strip()
    number = str(item.get("channel_number") or "").strip()
    if device and number:
        return f"{device} · {number}"
    return device or number or str(item.get("model") or "?")


def _equipo_color(item: Dict[str, Any]) -> str:
    raw = item.get("color")
    if raw is None or raw == "":
        return "#66AAFF"
    text = str(raw).strip()
    if text.startswith("#"):
        return text
    try:
        value = int(text)
    except (TypeError, ValueError):
        return "#66AAFF"
    r = (value >> 16) & 0xFF
    g = (value >> 8) & 0xFF
    b = value & 0xFF
    return f"#{r:02X}{g:02X}{b:02X}"


def _frequency_hz(item: Dict[str, Any]) -> Optional[float]:
    mhz = item.get("frequency_mhz")
    if mhz is None or mhz == "":
        return None
    try:
        return float(mhz) * 1_000_000.0
    except (TypeError, ValueError):
        return None


def resolve_supervision_targets(
    state: SupervisionState,
    equipos: List[Dict[str, Any]],
) -> List[ResolvedSupervisionTarget]:
    """Une targets persistidos con filas del inventario."""
    normalized = [normalize_equipo(item) for item in equipos if isinstance(item, dict)]
    resolved: List[ResolvedSupervisionTarget] = []
    for target in state.targets:
        if not target.enabled:
            continue
        item = find_equipo_in_list(normalized, target.channel_key)
        if item is None:
            continue
        freq_hz = _frequency_hz(item)
        if freq_hz is None or freq_hz <= 0.0:
            continue
        resolved.append(
            ResolvedSupervisionTarget(
                channel_key=target.channel_key,
                enabled=True,
                frequency_hz=freq_hz,
                bandwidth_hz=max(1.0, float(target.bandwidth_hz)),
                label=_equipo_label(item),
                color=_equipo_color(item),
                device_type=str(item.get("device_type") or "other"),
                band=str(item.get("band") or ""),
                zone=str(item.get("zone") or ""),
            )
        )
    resolved.sort(key=lambda row: row.frequency_hz)
    return resolved


def resolve_supervision_catalog(
    state: SupervisionState,
    equipos: List[Dict[str, Any]],
) -> List[ResolvedSupervisionTarget]:
    """Todos los canales del inventario con flag enabled — para el árbol de supervisión."""
    normalized = [normalize_equipo(item) for item in equipos if isinstance(item, dict)]
    resolved: List[ResolvedSupervisionTarget] = []
    for target in state.targets:
        item = find_equipo_in_list(normalized, target.channel_key)
        if item is None:
            continue
        freq_hz = _frequency_hz(item)
        if freq_hz is None or freq_hz <= 0.0:
            continue
        resolved.append(
            ResolvedSupervisionTarget(
                channel_key=target.channel_key,
                enabled=bool(target.enabled),
                frequency_hz=freq_hz,
                bandwidth_hz=max(1.0, float(target.bandwidth_hz)),
                label=_equipo_label(item),
                color=_equipo_color(item),
                device_type=str(item.get("device_type") or "other"),
                band=str(item.get("band") or ""),
                zone=str(item.get("zone") or ""),
            )
        )
    resolved.sort(key=lambda row: row.frequency_hz)
    return resolved


def supervision_target_rows(
    state: SupervisionState,
    equipos: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filas para la tabla del gestor de frecuencias."""
    normalized = [normalize_equipo(item) for item in equipos if isinstance(item, dict)]
    by_key = {channel_key(item): item for item in normalized}
    rows: List[Dict[str, Any]] = []
    for target in state.targets:
        item = by_key.get(target.channel_key)
        if item is None:
            continue
        freq_hz = _frequency_hz(item)
        rows.append(
            {
                "channel_key": target.channel_key,
                "enabled": target.enabled,
                "bandwidth_hz": target.bandwidth_hz,
                "bandwidth_source": target.bandwidth_source,
                "label": _equipo_label(item),
                "frequency_mhz": item.get("frequency_mhz"),
                "frequency_hz": freq_hz,
                "device_name": item.get("device_name"),
                "model": item.get("model"),
                "device_type": item.get("device_type"),
                "band": item.get("band"),
                "color": _equipo_color(item),
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("frequency_hz") is None,
            float(row.get("frequency_hz") or 0.0),
            str(row.get("label") or ""),
        )
    )
    return rows
