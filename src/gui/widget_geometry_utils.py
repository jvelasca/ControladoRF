"""Serialización base64 de geometría Qt (saveGeometry / restoreGeometry)."""
from __future__ import annotations

from PyQt6.QtCore import QByteArray
from PyQt6.QtWidgets import QWidget


def encode_widget_geometry(widget: QWidget) -> str:
    return widget.saveGeometry().toBase64().data().decode("ascii")


def decode_widget_geometry(widget: QWidget, geometry_b64: str) -> bool:
    if not geometry_b64:
        return False
    try:
        data = QByteArray.fromBase64(geometry_b64.encode("ascii"))
    except Exception:
        return False
    if data.isEmpty():
        return False
    return bool(widget.restoreGeometry(data))
