"""Alineación uniforme de celdas en la tabla de inventario RF."""
from __future__ import annotations

from PyQt6.QtCore import Qt

TABLE_ALIGN_LEFT = "left"
TABLE_ALIGN_CENTER = "center"
TABLE_ALIGN_RIGHT = "right"
DEFAULT_TABLE_ALIGNMENT = TABLE_ALIGN_LEFT

_TABLE_ALIGNMENTS = (
    TABLE_ALIGN_LEFT,
    TABLE_ALIGN_CENTER,
    TABLE_ALIGN_RIGHT,
)


def normalize_table_alignment(value: str | None) -> str:
    if value in _TABLE_ALIGNMENTS:
        return value
    return DEFAULT_TABLE_ALIGNMENT


def table_alignment_to_qt(value: str | None) -> Qt.AlignmentFlag:
    mode = normalize_table_alignment(value)
    vertical = Qt.AlignmentFlag.AlignVCenter
    if mode == TABLE_ALIGN_CENTER:
        return Qt.AlignmentFlag.AlignCenter
    if mode == TABLE_ALIGN_RIGHT:
        return Qt.AlignmentFlag.AlignRight | vertical
    return Qt.AlignmentFlag.AlignLeft | vertical
