"""Operaciones masivas sobre grupos del inventario RF."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.inventory_channel import channel_key
from core.inventory_editor import delete_equipo, duplicate_equipo, get_equipos
from core.inventory_exceptions import InventoryLockedError
from core.inventory_metadata import is_group_locked, is_list_locked


def duplicate_group_channels(
    project,
    *,
    group_mode: str,
    group_key: str,
    items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if is_list_locked(project) or is_group_locked(project, group_mode, group_key):
        raise InventoryLockedError(f"group:{group_mode}:{group_key}")
    created: List[Dict[str, Any]] = []
    for item in items:
        key = channel_key(item)
        copy_item = duplicate_equipo(project, key)
        if copy_item:
            created.append(copy_item)
    return created


def delete_group_channels(
    project,
    *,
    group_mode: str,
    group_key: str,
    items: List[Dict[str, Any]],
) -> int:
    if is_list_locked(project) or is_group_locked(project, group_mode, group_key):
        raise InventoryLockedError(f"group:{group_mode}:{group_key}")
    keys = [channel_key(item) for item in items]
    deleted = 0
    for key in keys:
        if delete_equipo(project, key):
            deleted += 1
    return deleted


def channels_in_group(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(item) for item in items if isinstance(item, dict)]
