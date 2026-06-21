"""Metadatos de lista y grupos del inventario RF (notas, color, bloqueo)."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.inventory_catalog import GROUP_MODES, GROUP_NONE, group_key_for_item

SCOPE_LIST = "list"
SCOPE_GROUP = "group"

DEFAULT_METADATA: Dict[str, Any] = {
    "notes": "",
    "color": "",
    "locked": False,
}


def _normalize_metadata(raw: Any) -> Dict[str, Any]:
    data = dict(DEFAULT_METADATA)
    if not isinstance(raw, dict):
        return data
    data["notes"] = str(raw.get("notes") or "")
    color = raw.get("color")
    data["color"] = str(color) if color not in (None, "") else ""
    data["locked"] = bool(raw.get("locked"))
    return data


def _inventario_module(project) -> Dict[str, Any]:
    return project.modules.setdefault("inventario_rf", {})


def get_list_metadata(project) -> Dict[str, Any]:
    module = _inventario_module(project)
    return _normalize_metadata(module.get("list_metadata"))


def get_group_metadata(project, group_mode: str, group_key: str) -> Dict[str, Any]:
    module = _inventario_module(project)
    groups = module.setdefault("group_metadata", {})
    if not isinstance(groups, dict):
        groups = {}
        module["group_metadata"] = groups
    mode_bucket = groups.setdefault(group_mode, {})
    if not isinstance(mode_bucket, dict):
        mode_bucket = {}
        groups[group_mode] = mode_bucket
    return _normalize_metadata(mode_bucket.get(group_key))


def update_list_metadata(project, updates: Dict[str, Any]) -> Dict[str, Any]:
    module = _inventario_module(project)
    current = get_list_metadata(project)
    current.update(_coerce_metadata_updates(updates))
    module["list_metadata"] = current
    project.touch_modified()
    return dict(current)


def update_group_metadata(
    project,
    group_mode: str,
    group_key: str,
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    module = _inventario_module(project)
    groups = module.setdefault("group_metadata", {})
    if not isinstance(groups, dict):
        groups = {}
        module["group_metadata"] = groups
    mode_bucket = groups.setdefault(group_mode, {})
    if not isinstance(mode_bucket, dict):
        mode_bucket = {}
        groups[group_mode] = mode_bucket
    current = get_group_metadata(project, group_mode, group_key)
    current.update(_coerce_metadata_updates(updates))
    mode_bucket[group_key] = current
    project.touch_modified()
    return dict(current)


def _coerce_metadata_updates(updates: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    if "notes" in updates:
        result["notes"] = str(updates.get("notes") or "")
    if "color" in updates:
        value = updates.get("color")
        result["color"] = str(value) if value not in (None, "") else ""
    if "locked" in updates:
        result["locked"] = bool(updates.get("locked"))
    return result


def is_list_locked(project) -> bool:
    return bool(get_list_metadata(project).get("locked"))


def is_group_locked(project, group_mode: str, group_key: str) -> bool:
    if is_list_locked(project):
        return True
    return bool(get_group_metadata(project, group_mode, group_key).get("locked"))


def is_equipo_locked(project, item: Dict[str, Any]) -> bool:
    if is_list_locked(project):
        return True
    if bool(item.get("locked")):
        return True
    for mode in GROUP_MODES:
        if mode == GROUP_NONE:
            continue
        gkey = group_key_for_item(item, mode)
        if is_group_locked(project, mode, gkey):
            return True
    return False


def is_direct_equipo_lock(project, item: Dict[str, Any]) -> bool:
    """True si el canal tiene bloqueo propio (no heredado de lista/grupo)."""
    if not bool(item.get("locked")):
        return False
    if is_list_locked(project):
        return False
    for mode in GROUP_MODES:
        if mode == GROUP_NONE:
            continue
        gkey = group_key_for_item(item, mode)
        if gkey and bool(get_group_metadata(project, mode, gkey).get("locked")):
            return False
    return True


def is_inherited_equipo_lock(project, item: Dict[str, Any]) -> bool:
    """True si el canal está bloqueado solo por lista o grupo."""
    return is_equipo_locked(project, item) and not is_direct_equipo_lock(project, item)


def iter_group_metadata_entries(project) -> List[Tuple[str, str, Dict[str, Any]]]:
    module = _inventario_module(project)
    groups = module.get("group_metadata") or {}
    if not isinstance(groups, dict):
        return []
    entries: List[Tuple[str, str, Dict[str, Any]]] = []
    for group_mode, bucket in groups.items():
        if not isinstance(bucket, dict):
            continue
        for group_key, raw in bucket.items():
            entries.append((str(group_mode), str(group_key), _normalize_metadata(raw)))
    return entries
