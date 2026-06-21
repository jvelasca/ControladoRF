"""Delegate que centra el icono de bloqueo en la columna Bloq."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTableWidget

from gui.icon_utils import ICON_SIZE_MENU, get_app_icon

LOCK_STATE_ROLE = int(Qt.ItemDataRole.UserRole) + 11
LOCK_ICON_SIZE = ICON_SIZE_MENU


class InventoryLockDelegate(QStyledItemDelegate):
    """Pinta el candado centrado, independiente de la alineación global de la tabla."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        locked = self._is_locked(option, index)
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

        if not locked:
            return

        icon = get_app_icon("lock", LOCK_ICON_SIZE)
        rect = option.rect
        px = icon.pixmap(LOCK_ICON_SIZE, LOCK_ICON_SIZE)
        x = rect.center().x() - px.width() // 2
        y = rect.center().y() - px.height() // 2
        painter.drawPixmap(x, y, px)

    def _is_locked(self, option: QStyleOptionViewItem, index) -> bool:
        widget = option.widget
        if isinstance(widget, QTableWidget):
            item = widget.item(index.row(), index.column())
            if item is not None:
                return bool(item.data(LOCK_STATE_ROLE))
        return bool(index.data(LOCK_STATE_ROLE))

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        _ = option, index
        return QSize(LOCK_ICON_SIZE + 8, LOCK_ICON_SIZE + 8)
