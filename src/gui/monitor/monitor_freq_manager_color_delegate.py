"""Muestra circular de color del inventario (sin teñir el fondo de la celda)."""
from __future__ import annotations

from gui.inventory_color_delegate import InventoryColorDelegate


class MonitorFreqManagerColorDelegate(InventoryColorDelegate):
    """Solo la bola de color, igual que en inventario."""
