"""Operaciones CRUD sobre `project.modules.inventario_rf.equipos`."""
from __future__ import annotations

import copy
import uuid
from typing import Any, Dict, List, Optional

from core.inventory_catalog import DEVICE_TYPE_OTHER, enrich_equipo_metadata
from core.inventory_channel import channel_key, find_equipo_in_list, normalize_equipo
from core.inventory_exceptions import InventoryLockedError
from core.inventory_metadata import is_direct_equipo_lock, is_equipo_locked, is_list_locked

EDITABLE_FIELDS = (
    "channel_number",
    "channel_name",
    "frequency_mhz",
    "band",
    "zone",
    "network",
    "model",
    "series",
    "manufacturer",
    "device_name",
    "device_type",
    "coordination_include",
    "coordination_active",
    "notes",
    "color",
    "locked",
)


def get_equipos(project) -> List[Dict[str, Any]]:
    """Lista mutable de equipos del módulo inventario."""
    module = project.modules.setdefault("inventario_rf", {})
    equipos = module.get("equipos")
    if not isinstance(equipos, list):
        equipos = []
        module["equipos"] = equipos
    return equipos


def find_equipo_index(project, key: str) -> int:
    equipos = get_equipos(project)
    for index, item in enumerate(equipos):
        if isinstance(item, dict) and channel_key(item) == key:
            return index
    return -1


def _new_manual_key() -> str:
    return f"manual:{uuid.uuid4().hex[:12]}"


def _default_equipo() -> Dict[str, Any]:
    return normalize_equipo(
        {
            "source": "manual",
            "channel_key": _new_manual_key(),
            "channel_number": None,
            "channel_name": "",
            "frequency_mhz": None,
            "band": "",
            "zone": "Default",
            "network": "Default",
            "model": "",
            "series": "—",
            "manufacturer": "",
            "device_name": "",
            "device_type": DEVICE_TYPE_OTHER,
            "coordination_include": True,
            "coordination_active": True,
            "notes": "",
            "color": "",
            "locked": False,
        }
    )


def _finalize_equipo(
    item: Dict[str, Any],
    *,
    explicit_device_type: Optional[str] = None,
) -> Dict[str, Any]:
    data = enrich_equipo_metadata(dict(item))
    if explicit_device_type is not None:
        data["device_type"] = explicit_device_type
    data["channel_key"] = channel_key(data) or _new_manual_key()
    return data


def _coerce_updates(updates: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for field in EDITABLE_FIELDS:
        if field not in updates:
            continue
        value = updates[field]
        if field == "channel_number":
            if value in (None, ""):
                result[field] = None
            else:
                result[field] = int(value)
        elif field == "frequency_mhz":
            if value in (None, ""):
                result[field] = None
            else:
                result[field] = float(value)
        elif field in ("coordination_include", "coordination_active", "locked"):
            result[field] = bool(value)
        elif field in ("notes", "color"):
            result[field] = "" if value in (None, "") else str(value)
        elif field == "device_type":
            result[field] = str(value or DEVICE_TYPE_OTHER)
        else:
            result[field] = "" if value is None else str(value)
    return result


def create_equipo(project, *, template: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Añade un canal nuevo al inventario."""
    if is_list_locked(project):
        raise InventoryLockedError("list")
    equipos = get_equipos(project)
    if template:
        item = _finalize_equipo(
            {
                **copy.deepcopy(template),
                "source": "manual",
                "channel_key": _new_manual_key(),
                "workbench_channel_id": None,
                "workbench_device_id": None,
                "workbench_dcid": None,
                "workbench_dev_types": None,
                "db_id": None,
            }
        )
    else:
        item = _default_equipo()
    equipos.append(item)
    project.touch_modified()
    return dict(item)


def update_equipo(project, key: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Actualiza campos editables de un canal existente."""
    index = find_equipo_index(project, key)
    if index < 0:
        raise KeyError(key)

    equipos = get_equipos(project)
    current = dict(equipos[index])
    coerced = _coerce_updates(updates)
    if is_equipo_locked(project, current):
        unlocking = is_direct_equipo_lock(project, current) and coerced.get("locked") is False
        if not unlocking:
            raise InventoryLockedError(key)
    explicit_type = coerced.pop("device_type", None)
    merged = {**current, **coerced}
    if explicit_type is not None:
        merged["device_type"] = explicit_type
    if merged.get("source") != "workbench":
        merged["channel_key"] = merged.get("channel_key") or _new_manual_key()

    updated = _finalize_equipo(merged, explicit_device_type=explicit_type)
    equipos[index] = updated
    project.touch_modified()
    return dict(updated)


def delete_equipo(project, key: str) -> bool:
    """Elimina un canal del inventario."""
    index = find_equipo_index(project, key)
    if index < 0:
        return False
    item = get_equipos(project)[index]
    if isinstance(item, dict) and is_equipo_locked(project, item):
        raise InventoryLockedError(key)
    get_equipos(project).pop(index)
    project.touch_modified()
    return True


def duplicate_equipo(project, key: str) -> Optional[Dict[str, Any]]:
    """Duplica un canal con clave nueva y sin vínculo Workbench."""
    source = find_equipo_in_list(get_equipos(project), key)
    if not source:
        return None
    if is_equipo_locked(project, source):
        raise InventoryLockedError(key)

    copy_item = copy.deepcopy(source)
    copy_item.pop("db_id", None)
    copy_item["source"] = "manual"
    copy_item["channel_key"] = _new_manual_key()
    for wb_field in (
        "workbench_channel_id",
        "workbench_device_id",
        "workbench_dcid",
        "workbench_dev_types",
    ):
        copy_item.pop(wb_field, None)

    name = str(copy_item.get("channel_name") or "").strip()
    if name:
        copy_item["channel_name"] = f"{name} (copia)"

    explicit_type = copy_item.get("device_type")
    item = _finalize_equipo(copy_item, explicit_device_type=str(explicit_type or DEVICE_TYPE_OTHER))
    get_equipos(project).append(item)
    project.touch_modified()
    return dict(item)
