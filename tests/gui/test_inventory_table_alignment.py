"""Tests de alineación uniforme en la tabla de inventario."""
from PyQt6.QtCore import Qt

from gui.inventory_table_alignment import (
    DEFAULT_TABLE_ALIGNMENT,
    TABLE_ALIGN_CENTER,
    TABLE_ALIGN_LEFT,
    TABLE_ALIGN_RIGHT,
    normalize_table_alignment,
    table_alignment_to_qt,
)


def test_normalize_table_alignment_defaults_unknown():
    assert normalize_table_alignment(None) == DEFAULT_TABLE_ALIGNMENT
    assert normalize_table_alignment("invalid") == DEFAULT_TABLE_ALIGNMENT


def test_normalize_table_alignment_accepts_known_modes():
    assert normalize_table_alignment(TABLE_ALIGN_LEFT) == TABLE_ALIGN_LEFT
    assert normalize_table_alignment(TABLE_ALIGN_CENTER) == TABLE_ALIGN_CENTER
    assert normalize_table_alignment(TABLE_ALIGN_RIGHT) == TABLE_ALIGN_RIGHT


def test_table_alignment_to_qt_maps_modes():
    assert table_alignment_to_qt(TABLE_ALIGN_LEFT) == (
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    assert table_alignment_to_qt(TABLE_ALIGN_CENTER) == Qt.AlignmentFlag.AlignCenter
    assert table_alignment_to_qt(TABLE_ALIGN_RIGHT) == (
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
