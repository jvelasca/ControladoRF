"""Utilidades de selección de color (Qt estándar)."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog, QWidget


def parse_color(value: str) -> Optional[QColor]:
    if not value:
        return None
    color = QColor(str(value))
    return color if color.isValid() else None


def color_to_hex(color: QColor) -> str:
    return color.name(QColor.NameFormat.HexRgb).upper()


def pick_color(parent: Optional[QWidget], current: str = "") -> Optional[str]:
    """Abre QColorDialog y devuelve hex #RRGGBB o None si cancela."""
    initial = parse_color(current) or QColor("#FFFFFF")
    chosen = QColorDialog.getColor(initial, parent)
    if not chosen.isValid():
        return None
    return color_to_hex(chosen)
