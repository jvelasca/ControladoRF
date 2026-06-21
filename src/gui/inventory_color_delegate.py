"""Delegate que pinta una muestra circular de color en la tabla de inventario."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTableWidget

COLOR_SWATCH_ROLE = int(Qt.ItemDataRole.UserRole) + 10
SWATCH_DIAMETER = 14


class InventoryColorDelegate(QStyledItemDelegate):
    """Pinta un círculo con el color asignado al canal o grupo."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        color_value = self._color_value(option, index)
        if not color_value:
            super().paint(painter, option, index)
            return

        color = QColor(str(color_value))
        if not color.isValid():
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        widget = option.widget
        if widget is not None:
            widget.style().drawPrimitive(
                QStyle.PrimitiveElement.PE_PanelItemViewItem,
                opt,
                painter,
                widget,
            )

        rect = option.rect.adjusted(4, 4, -4, -4)
        diameter = min(rect.width(), rect.height(), SWATCH_DIAMETER)
        x = rect.center().x() - diameter // 2
        y = rect.center().y() - diameter // 2

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#808080"), 1))
        painter.setBrush(color)
        painter.drawEllipse(x, y, diameter, diameter)
        painter.restore()

    def _color_value(self, option: QStyleOptionViewItem, index) -> object:
        widget = option.widget
        if isinstance(widget, QTableWidget):
            item = widget.item(index.row(), index.column())
            if item is not None:
                value = item.data(COLOR_SWATCH_ROLE)
                if value:
                    return value
        return index.data(COLOR_SWATCH_ROLE)

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        _ = option, index
        return QSize(SWATCH_DIAMETER + 8, SWATCH_DIAMETER + 8)
