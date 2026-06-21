"""Modelo de foco/selección del inventario RF (canal, grupo o lista)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

FOCUS_NONE = "none"
FOCUS_LIST = "list"
FOCUS_GROUP = "group"
FOCUS_CHANNEL = "channel"
FOCUS_PROPERTIES = "properties"


def list_focus() -> Dict[str, Any]:
    return {"kind": FOCUS_LIST}


def group_focus(
    *,
    group_mode: str,
    group_key: str,
    label: str,
    items: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return {
        "kind": FOCUS_GROUP,
        "group_mode": group_mode,
        "group_key": group_key,
        "label": label,
        "items": list(items or []),
    }


def channel_focus(item: Dict[str, Any], *, channel_key_value: str) -> Dict[str, Any]:
    return {
        "kind": FOCUS_CHANNEL,
        "channel_key": channel_key_value,
        "item": dict(item),
    }


def focus_kind(focus: Optional[Dict[str, Any]]) -> str:
    if not focus:
        return FOCUS_NONE
    return str(focus.get("kind") or FOCUS_NONE)
