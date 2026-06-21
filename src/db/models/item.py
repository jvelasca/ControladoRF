"""Modelo de ejemplo para repositorios."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Item:
    """Entidad de ejemplo almacenada en la tabla `items`."""

    id: Optional[int]
    name: str
    description: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
