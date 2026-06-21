"""
workspace_manager.py
-------------------
Diálogo profesional de gestión de workspaces (estilo IDE).
"""
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from gui.dialog_styles import apply_professional_dialog_style
from gui.icon_utils import ICON_SIZE_BUTTON, ICON_SIZE_TOOLBAR, get_app_icon
from gui.message_box_utils import ask_yes_no
from i18n.json_translation import tr
from utils.logger import get_logger, log_error
from workspace.controller import WorkspaceController
from workspace.model import Workspace


class WorkspaceManagerDialog(QDialog):
    """Gestor visual de workspaces con tabla, barra de herramientas y persistencia de layout."""

    workspace_changed = pyqtSignal(str)
    DEFAULT_NAME = "Default"
    COL_NAME = 0
    COL_DESCRIPTION = 1
    COL_ACTIVE = 2
    COL_ACTIONS = 3

    def __init__(self, controller: WorkspaceController, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(820, 460)
        self._logger = get_logger(__name__)
        self.controller = controller
        self._registered = False
        self._setup_ui()
        self.recargar_textos()
        self._apply_dialog_theme()
        self._load_workspaces()
        self.table.cellChanged.connect(self._cell_edited)
        self.table.horizontalHeader().sectionResized.connect(self._save_table_state)
        self._register_if_needed()

    def _register_if_needed(self) -> None:
        if not self._registered:
            self.controller.register_component(self)
            self._registered = True

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._toolbar = QToolBar()
        self._btn_new = QPushButton()
        self._btn_new.clicked.connect(self._on_new_workspace)
        self._btn_import = QPushButton()
        self._btn_import.clicked.connect(self._on_import_workspace)
        self._toolbar.addWidget(self._btn_new)
        self._toolbar.addWidget(self._btn_import)
        layout.addWidget(self._toolbar)

        self.table = QTableWidget(0, 4)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_DESCRIPTION, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_ACTIVE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_ACTIONS, QHeaderView.ResizeMode.Interactive)
        header.setSectionsMovable(True)
        header.setMinimumSectionSize(48)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.SelectedClicked
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=1)

        self._status_label = QLabel()
        self._status_label.setObjectName("DialogStatusLabel")
        layout.addWidget(self._status_label)

        self._button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._button_box.rejected.connect(self.reject)
        layout.addWidget(self._button_box)

    def _apply_dialog_theme(self) -> None:
        apply_professional_dialog_style(self)

    def _make_action_button(self, tooltip_key: str, icon_name: str, slot) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(get_app_icon(icon_name, ICON_SIZE_BUTTON))
        btn.setToolTip(tr(tooltip_key))
        btn.setProperty("i18n_key", tooltip_key)
        btn.setProperty("icon_name", icon_name)
        btn.setFlat(True)
        btn.clicked.connect(slot)
        return btn

    def _refresh_action_icons(self) -> None:
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, self.COL_ACTIONS)
            if not widget:
                continue
            for btn in widget.findChildren(QPushButton):
                icon_name = btn.property("icon_name")
                if icon_name:
                    btn.setIcon(get_app_icon(str(icon_name), ICON_SIZE_BUTTON))

    def recargar_textos(self) -> None:
        self.setWindowTitle(tr("ws_manager_title"))
        self._btn_new.setText(tr("ws_btn_new"))
        self._btn_new.setIcon(get_app_icon("new", ICON_SIZE_TOOLBAR))
        self._btn_import.setText(tr("ws_btn_import"))
        self._btn_import.setIcon(get_app_icon("import", ICON_SIZE_TOOLBAR))
        self.table.setHorizontalHeaderLabels([
            tr("ws_col_name"),
            tr("ws_col_description"),
            tr("ws_col_active"),
            tr("ws_col_actions"),
        ])
        close_btn = self._button_box.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.setText(tr("close"))
        self._update_status_label()
        self._refresh_action_tooltips()
        self._refresh_action_icons()

    def _update_status_label(self) -> None:
        active = self.controller.active_workspace
        if active:
            self._status_label.setText(tr("ws_status_active", name=active.name))
        else:
            self._status_label.setText(tr("ws_status_none"))

    def _refresh_action_tooltips(self) -> None:
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, self.COL_ACTIONS)
            if not widget:
                continue
            for btn in widget.findChildren(QPushButton):
                key = btn.property("i18n_key")
                if key:
                    btn.setToolTip(tr(key))

    def _load_workspaces(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for ws in self.controller.get_all_workspaces():
            self._add_workspace_row(ws)
        self.table.blockSignals(False)
        self._restore_table_state()
        self._update_status_label()

    def _active_text(self, ws: Workspace) -> str:
        active = self.controller.active_workspace
        is_active = active is not None and active.name == ws.name
        return tr("ws_yes") if is_active else tr("ws_no")

    def _add_workspace_row(self, ws: Workspace) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        is_default = ws.is_default

        name_item = QTableWidgetItem(ws.name)
        name_item.setData(Qt.ItemDataRole.UserRole, ws.name)
        if is_default:
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.table.setItem(row, self.COL_NAME, name_item)

        desc_item = QTableWidgetItem(ws.description)
        if is_default:
            desc_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.table.setItem(row, self.COL_DESCRIPTION, desc_item)

        active_item = QTableWidgetItem(self._active_text(ws))
        active_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        active_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, self.COL_ACTIVE, active_item)

        actions = QWidget(self.table)
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(2, 0, 2, 0)
        actions_layout.setSpacing(2)
        actions.setLayout(actions_layout)

        btn_activate = self._make_action_button(
            "ws_tooltip_activate",
            "activate",
            lambda _, r=row: self._on_activate(r),
        )
        btn_activate.setCheckable(True)
        btn_activate.setChecked(
            self.controller.active_workspace is not None
            and self.controller.active_workspace.name == ws.name
        )
        actions_layout.addWidget(btn_activate)

        if is_default:
            actions_layout.addWidget(
                self._make_action_button(
                    "ws_tooltip_import",
                    "import",
                    self._on_import_default,
                )
            )

        actions_layout.addWidget(
            self._make_action_button(
                "ws_tooltip_duplicate",
                "duplicate",
                lambda _, r=row: self._on_duplicate(r),
            )
        )
        actions_layout.addWidget(
            self._make_action_button(
                "ws_tooltip_export",
                "export",
                lambda _, r=row: self._on_export(r),
            )
        )

        if not is_default:
            actions_layout.addWidget(
                self._make_action_button(
                    "ws_tooltip_delete",
                    "delete",
                    lambda _, r=row: self._on_delete(r),
                )
            )

        actions_layout.addStretch(1)
        self.table.setCellWidget(row, self.COL_ACTIONS, actions)
        self.table.setRowHeight(row, 40)

    def _workspace_name_at(self, row: int) -> str:
        item = self.table.item(row, self.COL_NAME)
        return item.text().strip() if item else ""

    def _on_new_workspace(self) -> None:
        name, ok = QInputDialog.getText(
            self,
            tr("ws_new_title"),
            tr("ws_new_prompt"),
            QLineEdit.EchoMode.Normal,
        )
        if not ok or not name.strip():
            return
        description, _ = QInputDialog.getText(
            self,
            tr("ws_new_desc_title"),
            tr("ws_new_desc_prompt"),
            QLineEdit.EchoMode.Normal,
        )
        if self.controller.create_workspace(name.strip(), description.strip()):
            self._load_workspaces()
            self.workspace_changed.emit(name.strip())
            QMessageBox.information(self, tr("ws_created_title"), tr("ws_created_message", name=name.strip()))
        else:
            QMessageBox.warning(self, tr("error_title"), tr("ws_error_create"))

    def _on_activate(self, row: int) -> None:
        try:
            name = self._workspace_name_at(row)
            if self.controller.set_active_workspace(name):
                self._load_workspaces()
                self.workspace_changed.emit(name)
            else:
                QMessageBox.warning(self, tr("error_title"), tr("ws_error_activate", name=name))
        except Exception as exc:
            log_error("[WorkspaceManagerDialog] Error al activar workspace", exc)
            QMessageBox.critical(self, tr("error_title"), tr("ws_error_activate_unexpected", error=str(exc)))

    def _on_duplicate(self, row: int) -> None:
        source_name = self._workspace_name_at(row)
        if not source_name:
            return
        new_name, ok = QInputDialog.getText(
            self,
            tr("ws_duplicate_title"),
            tr("ws_duplicate_prompt"),
            QLineEdit.EchoMode.Normal,
            f"{source_name}_copy",
        )
        if not ok or not new_name.strip():
            return
        if self.controller.duplicate_workspace(source_name, new_name.strip()):
            self.controller.set_active_workspace(new_name.strip())
            self._load_workspaces()
            self.workspace_changed.emit(new_name.strip())
            QMessageBox.information(
                self,
                tr("ws_duplicated_title"),
                tr("ws_duplicated_message", name=new_name.strip()),
            )
        else:
            QMessageBox.warning(self, tr("error_title"), tr("ws_error_duplicate"))

    def _on_export(self, row: int) -> None:
        name = self._workspace_name_at(row)
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("ws_export_title"),
            f"{name}.json",
            tr("ws_export_filter"),
        )
        if not path:
            return
        if self.controller.export_workspace(name, path):
            QMessageBox.information(self, tr("ws_exported_title"), tr("ws_exported_message"))
        else:
            QMessageBox.warning(self, tr("error_title"), tr("ws_error_export"))

    def _on_delete(self, row: int) -> None:
        name = self._workspace_name_at(row)
        if name == self.DEFAULT_NAME:
            QMessageBox.warning(self, tr("error_title"), tr("ws_error_delete_default"))
            return
        if not ask_yes_no(self, tr("ws_delete_title"), tr("ws_delete_confirm", name=name)):
            return
        if self.controller.delete_workspace(name):
            self._load_workspaces()
            self.workspace_changed.emit(self.controller.active_workspace.name)
            QMessageBox.information(self, tr("ws_deleted_title"), tr("ws_deleted_message", name=name))
        else:
            QMessageBox.warning(self, tr("error_title"), tr("ws_error_delete"))

    def _on_import_workspace(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("ws_import_file_title"),
            "",
            tr("ws_export_filter"),
        )
        if not path:
            return
        ok, name = self.controller.import_workspace(path, merge_default=False)
        if ok:
            self.controller.set_active_workspace(name)
            self._load_workspaces()
            self.workspace_changed.emit(name)
            QMessageBox.information(self, tr("ws_imported_title"), tr("ws_imported_message", name=name))
        else:
            QMessageBox.warning(self, tr("error_title"), tr("ws_error_import"))

    def _on_import_default(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("ws_import_title"),
            "",
            tr("ws_export_filter"),
        )
        if not path:
            return
        ok, name = self.controller.import_workspace(path, merge_default=True)
        if ok:
            self._load_workspaces()
            self.workspace_changed.emit(name)
            QMessageBox.information(self, tr("ws_imported_title"), tr("ws_imported_default_message"))
        else:
            QMessageBox.warning(self, tr("error_title"), tr("ws_error_import"))

    def _cell_edited(self, row: int, col: int) -> None:
        if col not in (self.COL_NAME, self.COL_DESCRIPTION):
            return
        try:
            name_item = self.table.item(row, self.COL_NAME)
            if not name_item:
                return
            old_name = name_item.data(Qt.ItemDataRole.UserRole) or name_item.text().strip()
            new_name = name_item.text().strip()
            new_desc = self.table.item(row, self.COL_DESCRIPTION).text().strip()
            if not new_name:
                QMessageBox.warning(self, tr("error_title"), tr("ws_error_name_empty"))
                self._load_workspaces()
                return
            if new_name != old_name:
                if not self.controller.rename_workspace(old_name, new_name, new_desc):
                    QMessageBox.warning(self, tr("error_title"), tr("ws_error_name_invalid"))
                    self._load_workspaces()
                    return
            else:
                ws = self.controller.get_workspace(old_name)
                if ws and new_desc != ws.description:
                    self.controller.update_workspace_description(old_name, new_desc)
            self._load_workspaces()
        except Exception as exc:
            log_error("[WorkspaceManagerDialog] Error al editar workspace", exc)
            QMessageBox.critical(self, tr("error_title"), tr("ws_error_edit_unexpected", error=str(exc)))

    def closeEvent(self, event) -> None:
        self._save_table_state()
        if self._registered:
            self.controller.unregister_component(self)
            self._registered = False
        super().closeEvent(event)

    def _restore_table_state(self) -> None:
        ws = self.controller.active_workspace
        if ws:
            self.restore_state(ws.config)

    def _save_table_state(self, *args) -> None:
        ws = self.controller.active_workspace
        if ws:
            ws.config.update(self.save_state())
            self.controller.store.save(ws)

    def save_state(self) -> dict:
        return {
            "workspace_table_column_widths": [
                self.table.columnWidth(i) for i in range(self.table.columnCount())
            ],
            "workspace_table_column_order": [
                self.table.horizontalHeader().visualIndex(i)
                for i in range(self.table.columnCount())
            ],
            "workspace_table_selection": [
                idx.row() for idx in self.table.selectionModel().selectedRows()
            ],
        }

    def restore_state(self, config: dict) -> None:
        if not config:
            return
        order = config.get("workspace_table_column_order")
        if order and isinstance(order, list) and len(order) == self.table.columnCount():
            try:
                for logical, visual in enumerate(order):
                    self.table.horizontalHeader().moveSection(
                        self.table.horizontalHeader().visualIndex(logical),
                        visual,
                    )
            except Exception as exc:
                log_error("[restore_state] Error restaurando orden de columnas", exc)
        widths = config.get("workspace_table_column_widths")
        if widths and isinstance(widths, list) and len(widths) == self.table.columnCount():
            for i, width in enumerate(widths):
                if i < self.table.columnCount():
                    self.table.setColumnWidth(i, width)
        selection = config.get("workspace_table_selection")
        if selection and isinstance(selection, list):
            self.table.clearSelection()
            for row in selection:
                if 0 <= row < self.table.rowCount():
                    self.table.selectRow(row)
