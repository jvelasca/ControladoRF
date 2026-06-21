"""Identidad y resolución de canales RF del inventario."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.inventory_catalog import enrich_equipo_metadata


def channel_key(item: Dict[str, Any]) -> str:
    """Clave estable del canal dentro de un proyecto."""
    explicit = item.get("channel_key")
    if explicit:
        return str(explicit)
    workbench = item.get("workbench_channel_id") or item.get("workbench_device_id")
    if workbench:
        return str(workbench)
    parts = (
        str(item.get("device_name") or ""),
        str(item.get("channel_number") or ""),
        str(item.get("channel_name") or ""),
        str(item.get("frequency_mhz") or ""),
        str(item.get("model") or ""),
    )
    return "|".join(parts)


def project_storage_key(file_path: Optional[str], project_name: str = "") -> str:
    """Clave de proyecto para SQLite (ruta normalizada o sesión sin guardar)."""
    if file_path:
        return str(file_path).replace("\\", "/").casefold()
    name = (project_name or "untitled").strip() or "untitled"
    return f"unsaved:{name.casefold()}"


def find_equipo_in_project(project, key: str) -> Optional[Dict[str, Any]]:
    """Busca un canal en `project.modules.inventario_rf.equipos` por clave estable."""
    equipos = project.modules.get("inventario_rf", {}).get("equipos") or []
    return find_equipo_in_list(equipos, key)


def find_equipo_in_list(equipos: List[Dict[str, Any]], key: str) -> Optional[Dict[str, Any]]:
    for item in equipos:
        if not isinstance(item, dict):
            continue
        if channel_key(item) == key:
            return dict(item)
    return None


def normalize_equipo(item: Dict[str, Any]) -> Dict[str, Any]:
    """Enriquece metadatos y garantiza `channel_key`."""
    data = enrich_equipo_metadata(dict(item))
    data["channel_key"] = channel_key(data)
    return data


def equipos_from_project(project) -> List[Dict[str, Any]]:
    raw = project.modules.get("inventario_rf", {}).get("equipos") or []
    return [normalize_equipo(item) for item in raw if isinstance(item, dict)]
