"""Persistencia de geometría y estado (maximizada) de la ventana principal."""
from __future__ import annotations

from typing import Any, Dict

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMainWindow

from utils.logger import get_logger

logger = get_logger(__name__)


def capture_main_window_layout(window: QMainWindow) -> Dict[str, Any]:
    """Serializa geometría y si la ventana está maximizada."""
    from gui.widget_geometry_utils import encode_widget_geometry

    return {
        "main_window_geometry": encode_widget_geometry(window),
        "main_window_maximized": window.isMaximized(),
    }


def restore_main_window_layout(
    window: QMainWindow,
    config: Dict[str, Any],
    *,
    defer_maximize: bool = False,
) -> None:
    """Restaura geometría y estado maximizado guardados."""
    geo = config.get("main_window_geometry")
    if geo:
        from gui.widget_geometry_utils import decode_widget_geometry

        if not decode_widget_geometry(window, str(geo)):
            logger.error("Error restaurando geometría de ventana: datos inválidos")

    if not config.get("main_window_maximized"):
        return

    if defer_maximize:
        QTimer.singleShot(0, window.showMaximized)
    else:
        window.showMaximized()
