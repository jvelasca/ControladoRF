"""Explorador de estructura del proyecto (árbol)."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from core.project_structure import ProjectStructureNode, build_project_structure_tree
from gui.dialog_styles import apply_professional_dialog_style
from gui.message_box_utils import localize_dialog_button_box
from i18n.json_translation import tr


class ProjectStructureDialog(QDialog):
    """Ventana modal con árbol de la estructura del proyecto actual."""

    def __init__(
        self,
        project_manager,
        module_tab_manager,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._project_manager = project_manager
        self._module_tab_manager = module_tab_manager

        self.setWindowTitle(tr("structure_dialog_title"))
        self.resize(640, 520)
        apply_professional_dialog_style(self)

        self._hint = QLabel(tr("structure_dialog_hint"))
        self._hint.setWordWrap(True)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([tr("structure_col_name"), tr("structure_col_detail")])
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(True)
        self._tree.header().setStretchLastSection(True)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._buttons.rejected.connect(self.reject)
        self._buttons.accepted.connect(self.accept)
        close_btn = self._buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.clicked.connect(self.accept)
        localize_dialog_button_box(self._buttons)

        refresh_row = QHBoxLayout()
        refresh_row.addStretch(1)
        refresh_btn = self._buttons.addButton(
            tr("structure_refresh"), QDialogButtonBox.ButtonRole.ActionRole
        )
        refresh_btn.clicked.connect(self.refresh_tree)

        layout = QVBoxLayout(self)
        layout.addWidget(self._hint)
        layout.addWidget(self._tree, stretch=1)
        layout.addLayout(refresh_row)
        layout.addWidget(self._buttons)

        self.refresh_tree()

    def refresh_tree(self) -> None:
        self._tree.clear()
        if not self._project_manager or not self._project_manager.project:
            empty = QTreeWidgetItem([tr("project_none"), ""])
            self._tree.addTopLevelItem(empty)
            return

        root_node = build_project_structure_tree(
            self._project_manager.project,
            file_path=self._project_manager.get_file_path() or None,
            is_dirty=self._project_manager.is_dirty,
            active_module=self._module_tab_manager.active_module,
        )
        root_item = self._add_node(None, root_node)
        if root_item is not None:
            self._tree.addTopLevelItem(root_item)
            self._tree.expandToDepth(1)

    def _add_node(
        self,
        parent_item: Optional[QTreeWidgetItem],
        node: ProjectStructureNode,
    ) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node.label, node.detail])
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        for child in node.children:
            self._add_node(item, child)
        if parent_item is not None:
            parent_item.addChild(item)
        return item

    def recargar_textos(self) -> None:
        self.setWindowTitle(tr("structure_dialog_title"))
        self._hint.setText(tr("structure_dialog_hint"))
        self._tree.setHeaderLabels([tr("structure_col_name"), tr("structure_col_detail")])
        localize_dialog_button_box(self._buttons)
        self.refresh_tree()
