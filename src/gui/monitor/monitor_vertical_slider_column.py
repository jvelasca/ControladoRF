"""Columna vertical alineada: rótulo + slider + menú … (espectro / waterfall)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QToolButton, QVBoxLayout, QWidget

COLUMN_WIDTH = 48
LABEL_HEIGHT = 14
READOUT_HEIGHT = 16
MENU_WIDTH = 20
MENU_HEIGHT = 18
SLIDER_TRACK_WIDTH = 14


def build_vertical_slider_column(
    parent: QWidget,
    *,
    label: QLabel,
    slider: QSlider,
    readout: QLabel | None = None,
    menu_btn: QToolButton | None = None,
) -> QVBoxLayout:
    """Apila rótulo, slider y lectura o botón menú centrados en columna."""
    label.setFixedHeight(LABEL_HEIGHT)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    slider.setFixedWidth(SLIDER_TRACK_WIDTH)
    if readout is not None:
        readout.setFixedHeight(READOUT_HEIGHT)
        readout.setMinimumWidth(COLUMN_WIDTH - 8)
        readout.setMaximumWidth(COLUMN_WIDTH + 4)
    if menu_btn is not None:
        menu_btn.setFixedSize(MENU_WIDTH, MENU_HEIGHT)

    layout = QVBoxLayout(parent)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(3)
    layout.addWidget(label, 0, Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(slider, 1, Qt.AlignmentFlag.AlignHCenter)
    if readout is not None:
        layout.addWidget(readout, 0, Qt.AlignmentFlag.AlignHCenter)
    elif menu_btn is not None:
        layout.addWidget(menu_btn, 0, Qt.AlignmentFlag.AlignHCenter)
    else:
        layout.addSpacing(READOUT_HEIGHT)
    return layout


def pair_column_width(*, columns: int = 2, gap: int = 4, padding: int = 4) -> int:
    if columns <= 0:
        return padding
    return columns * COLUMN_WIDTH + max(0, columns - 1) * gap + padding
