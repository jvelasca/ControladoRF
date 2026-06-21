"""Visor de ayuda de supervisión Monitor (F1)."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QWidget

from gui.help_dialog import show_help_dialog


def show_supervision_help_dialog(parent: Optional[QWidget] = None) -> None:
    show_help_dialog("supervision", parent=parent)
