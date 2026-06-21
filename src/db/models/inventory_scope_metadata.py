"""Modelo de metadatos de lista/grupo del inventario RF."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InventoryScopeMetadata:
    id: int | None
    project_key: str
    scope_type: str
    group_mode: str = ""
    group_key: str = ""
    notes: str = ""
    color: str = ""
    locked: bool = False
    updated_at: str | None = None
