"""Tests de serialización de geometría Qt."""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from gui.widget_geometry_utils import decode_widget_geometry, encode_widget_geometry


def test_widget_geometry_roundtrip(qapp):
    widget = QWidget()
    widget.resize(480, 320)
    widget.move(40, 60)
    encoded = encode_widget_geometry(widget)
    assert encoded

    other = QWidget()
    assert decode_widget_geometry(other, encoded)
    assert other.size() == widget.size()
    assert other.pos() == widget.pos()
