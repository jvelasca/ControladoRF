"""Geometría compartida del eje de frecuencia (espectro + waterfall alineados)."""
from __future__ import annotations

from PyQt6.QtCore import QRect

from gui.monitor.monitor_vertical_slider_column import pair_column_width

FREQ_PLOT_LEFT_MARGIN = 52
WATERFALL_SLIDER_PANEL_WIDTH = pair_column_width(columns=2)
DOCK_ESSENTIAL_COLUMNS = 2
DOCK_COLLAPSED_WIDTH = pair_column_width(columns=DOCK_ESSENTIAL_COLUMNS)


def unified_freq_plot_right_gutter(*, dock_width: int) -> int:
    """Ancho reservado a la derecha: dock RF y/o sliders MIN/MAX del waterfall."""
    return max(int(dock_width), int(WATERFALL_SLIDER_PANEL_WIDTH))


def freq_plot_rect(
    widget_rect: QRect,
    *,
    right_gutter: int,
    top: int = 0,
    bottom: int = 0,
) -> QRect:
    """Rectángulo horizontal donde frecuencia izquierda = frecuencia derecha en ambos gráficos."""
    gutter = max(int(right_gutter), int(WATERFALL_SLIDER_PANEL_WIDTH))
    return widget_rect.adjusted(FREQ_PLOT_LEFT_MARGIN, top, -gutter, -bottom)


def freq_plot_column_count(plot_rect: QRect, *, min_columns: int = 256) -> int:
    return max(min_columns, max(2, int(plot_rect.width())))
