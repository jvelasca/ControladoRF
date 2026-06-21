"""Utilidades de ámbito contextual (árbol de supervisión)."""
from __future__ import annotations

from typing import List

from core.inventory_channel import channel_key as inventory_channel_key
from core.inventory_channel import find_equipo_in_list


def channel_keys_for_same_device(channel_key: str, equipos: list) -> List[str]:
    """Todas las frecuencias/canales del mismo equipo en inventario."""
    key = str(channel_key or "").strip()
    if not key:
        return []
    item = find_equipo_in_list(equipos, key)
    if item is None:
        return [key]
    device_name = str(item.get("device_name") or "").strip()
    if not device_name:
        return [key]
    keys: List[str] = []
    for row in equipos:
        if not isinstance(row, dict):
            continue
        if str(row.get("device_name") or "").strip() != device_name:
            continue
        keys.append(inventory_channel_key(row))
    return keys or [key]
