"""Panel CRUD de items (fase 4) consumiendo ApplicationServices."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from gui.message_box_utils import ask_yes_no
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.exceptions import CoreError, DuplicateNameError, ValidationError
from db.exceptions import RecordNotFoundError
from gui.icon_utils import ICON_SIZE_BUTTON, get_app_icon
from gui.item_edit_dialog import ItemEditDialog
from gui.panel_styles import apply_panel_style, get_panel_colors
from i18n.json_translation import tr

COL_ID = 0
COL_NAME = 1
COL_DESCRIPTION = 2


class ItemsPanelWidget(QWidget):
    """Tabla y acciones CRUD sobre items vía ItemService."""

    def __init__(
        self,
        app_services=None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._app_services = app_services
        self._panel_id = "panel1"
        self._setup_ui()
        self.recargar_textos()
        self.reload_items()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        toolbar = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.returnPressed.connect(self._on_search)
        self._btn_search = QPushButton()
        self._btn_search.clicked.connect(self._on_search)
        self._btn_refresh = QPushButton()
        self._btn_refresh.clicked.connect(self.reload_items)
        self._btn_add = QPushButton()
        self._btn_add.clicked.connect(self._on_add)
        self._btn_edit = QPushButton()
        self._btn_edit.clicked.connect(self._on_edit)
        self._btn_delete = QPushButton()
        self._btn_delete.clicked.connect(self._on_delete)
        for btn, icon in (
            (self._btn_refresh, "refresh"),
            (self._btn_add, "new"),
            (self._btn_edit, "edit"),
            (self._btn_delete, "delete"),
        ):
            btn.setIcon(get_app_icon(icon, ICON_SIZE_BUTTON))
        toolbar.addWidget(self._search_edit, stretch=1)
        toolbar.addWidget(self._btn_search)
        toolbar.addWidget(self._btn_refresh)
        toolbar.addWidget(self._btn_add)
        toolbar.addWidget(self._btn_edit)
        toolbar.addWidget(self._btn_delete)
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, 3)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_edit)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(COL_ID, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_DESCRIPTION, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table, stretch=1)

        self._count_label = QLabel()
        layout.addWidget(self._count_label)

    def apply_visual_theme(self, panel_id: str) -> None:
        self._panel_id = panel_id
        apply_panel_style(self, panel_id)
        colors = get_panel_colors(panel_id)
        self._status_label.setStyleSheet(f"color: {colors['fg']}; font-size: 11px;")
        self._count_label.setStyleSheet(f"color: {colors['fg']}; font-size: 11px;")

    def recargar_textos(self) -> None:
        self._search_edit.setPlaceholderText(tr("items_search_placeholder"))
        self._btn_search.setText(tr("items_btn_search"))
        self._btn_refresh.setText(tr("items_btn_refresh"))
        self._btn_add.setText(tr("items_btn_add"))
        self._btn_edit.setText(tr("items_btn_edit"))
        self._btn_delete.setText(tr("items_btn_delete"))
        self._table.setHorizontalHeaderLabels(
            [
                tr("items_col_id"),
                tr("items_col_name"),
                tr("items_col_description"),
            ]
        )
        self._update_status_message()

    def set_app_services(self, app_services) -> None:
        self._app_services = app_services
        self.reload_items()

    def reload_items(self) -> None:
        self._table.setRowCount(0)
        if self._app_services is None:
            self._update_status_message()
            self._set_actions_enabled(False)
            return

        self._set_actions_enabled(True)
        query = self._search_edit.text().strip()
        try:
            items = (
                self._app_services.items.search_items(query)
                if query
                else self._app_services.items.list_items()
            )
        except CoreError as exc:
            self._show_error(str(exc))
            return

        for row, item in enumerate(items):
            self._table.insertRow(row)
            id_item = QTableWidgetItem(str(item.id))
            id_item.setData(Qt.ItemDataRole.UserRole, item.id)
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, COL_ID, id_item)
            self._table.setItem(row, COL_NAME, QTableWidgetItem(item.name))
            self._table.setItem(row, COL_DESCRIPTION, QTableWidgetItem(item.description))

        total = self._app_services.items.count_items()
        self._count_label.setText(tr("items_count_label", shown=len(items), total=total))
        self._update_status_message()

    def _update_status_message(self) -> None:
        if self._app_services is None:
            self._status_label.setText(tr("items_msg_no_services"))
        else:
            self._status_label.setText(tr("items_panel_hint"))

    def _set_actions_enabled(self, enabled: bool) -> None:
        for widget in (
            self._search_edit,
            self._btn_search,
            self._btn_refresh,
            self._btn_add,
            self._btn_edit,
            self._btn_delete,
            self._table,
        ):
            widget.setEnabled(enabled)

    def _selected_item_id(self) -> Optional[int]:
        row = self._table.currentRow()
        if row < 0:
            return None
        cell = self._table.item(row, COL_ID)
        if cell is None:
            return None
        value = cell.data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    def _on_search(self) -> None:
        self.reload_items()

    def _on_add(self) -> None:
        if self._app_services is None:
            return
        dlg = ItemEditDialog(self, title_key="items_dialog_add_title")
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        name, description = dlg.get_values()
        try:
            self._app_services.items.create_item(name, description)
            self.reload_items()
            self._show_info(tr("items_msg_created_title"), tr("items_msg_created"))
        except (ValidationError, DuplicateNameError) as exc:
            self._show_error(str(exc))

    def _on_edit(self) -> None:
        if self._app_services is None:
            return
        item_id = self._selected_item_id()
        if item_id is None:
            self._show_info(tr("items_msg_select_title"), tr("items_msg_select_row"))
            return
        try:
            item = self._app_services.items.get_item(item_id)
        except RecordNotFoundError as exc:
            self._show_error(str(exc))
            self.reload_items()
            return

        dlg = ItemEditDialog(
            self,
            name=item.name,
            description=item.description,
            title_key="items_dialog_edit_title",
        )
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        name, description = dlg.get_values()
        try:
            self._app_services.items.update_item(item_id, name, description)
            self.reload_items()
            self._show_info(tr("items_msg_updated_title"), tr("items_msg_updated"))
        except (ValidationError, DuplicateNameError) as exc:
            self._show_error(str(exc))

    def _on_delete(self) -> None:
        if self._app_services is None:
            return
        item_id = self._selected_item_id()
        if item_id is None:
            self._show_info(tr("items_msg_select_title"), tr("items_msg_select_row"))
            return
        row = self._table.currentRow()
        name = self._table.item(row, COL_NAME).text() if row >= 0 else ""
        if not ask_yes_no(
            self,
            tr("items_delete_title"),
            tr("items_delete_confirm", name=name),
        ):
            return
        try:
            self._app_services.items.delete_item(item_id)
            self.reload_items()
            self._show_info(tr("items_msg_deleted_title"), tr("items_msg_deleted"))
        except RecordNotFoundError as exc:
            self._show_error(str(exc))
            self.reload_items()

    def _show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, tr("error_title"), message)
