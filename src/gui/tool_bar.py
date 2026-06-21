"""Barra de herramientas contextual por módulo activo."""
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QSizePolicy, QToolBar, QWidget

from gui.icon_utils import ICON_SIZE_TOOLBAR, get_app_icon
from i18n.json_translation import tr


class ToolBar(QToolBar):
    """
    Barra de herramientas principal de la aplicación.

    Responsabilidad:
    - Accesos rápidos según el módulo activo (Inventario, Coordinación, Monitor).
    - Widget Monitor persistente entre cambios de pestaña (no usar QToolBar.clear()).
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._actions: List[QAction] = []
        self._module_actions: Dict[str, List[QAction]] = {}
        self._active_module = "inventario_rf"
        self._project_indicator: Optional[QWidget] = None
        self._end_spacer: Optional[QWidget] = None
        self._monitor_toolbar: Optional[QWidget] = None

        self._new_action: Optional[QAction] = None
        self._edit_action: Optional[QAction] = None
        self._duplicate_action: Optional[QAction] = None
        self._delete_action: Optional[QAction] = None
        self._apply_action: Optional[QAction] = None
        self._revert_action: Optional[QAction] = None
        self._columns_action: Optional[QAction] = None
        self._import_action: Optional[QAction] = None
        self._export_action: Optional[QAction] = None

        self._build_module_actions()
        self.set_active_module(self._active_module)

    def _build_module_actions(self) -> None:
        self._new_action = QAction(get_app_icon("new", ICON_SIZE_TOOLBAR), tr("inventory_action_new"))
        self._edit_action = QAction(get_app_icon("edit", ICON_SIZE_TOOLBAR), tr("inventory_action_edit"))
        self._duplicate_action = QAction(
            get_app_icon("duplicate", ICON_SIZE_TOOLBAR), tr("inventory_action_duplicate")
        )
        self._delete_action = QAction(get_app_icon("delete", ICON_SIZE_TOOLBAR), tr("inventory_action_delete"))
        self._apply_action = QAction(get_app_icon("activate", ICON_SIZE_TOOLBAR), tr("inventory_action_apply"))
        self._revert_action = QAction(get_app_icon("refresh", ICON_SIZE_TOOLBAR), tr("inventory_action_revert"))
        self._columns_action = QAction(
            get_app_icon("columns", ICON_SIZE_TOOLBAR), tr("inventory_table_columns_toolbar")
        )
        self._import_action = QAction(get_app_icon("import", ICON_SIZE_TOOLBAR), tr("toolbar_import"))
        self._export_action = QAction(get_app_icon("export", ICON_SIZE_TOOLBAR), tr("inventory_toolbar_export"))
        self._export_action.setToolTip(tr("inventory_export_title"))

        for action in (
            self._new_action,
            self._edit_action,
            self._duplicate_action,
            self._delete_action,
            self._apply_action,
            self._revert_action,
        ):
            action.setEnabled(False)

        self._import_action.setEnabled(True)
        self._export_action.setEnabled(False)
        self._columns_action.setEnabled(True)

        self._module_actions = {
            "inventario_rf": [
                self._new_action,
                self._edit_action,
                self._duplicate_action,
                self._delete_action,
                self._apply_action,
                self._revert_action,
                self._columns_action,
                self._import_action,
                self._export_action,
            ],
            "coordinacion": [],
            "monitor": [],
        }

        from gui.monitor.monitor_toolbar import MonitorToolBarWidget

        self._monitor_toolbar = MonitorToolBarWidget(parent=self)

    def set_project_indicator(self, widget: QWidget) -> None:
        self._project_indicator = widget
        self._end_spacer = QWidget()
        self._end_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._rebuild_toolbar()

    def set_active_module(self, module_id: str) -> None:
        self._active_module = module_id
        self._rebuild_toolbar()

    def _detach_persistent_widgets(self) -> None:
        """Evita que removeAction destruya widgets reutilizables del Monitor."""
        for widget in (self._monitor_toolbar, self._end_spacer, self._project_indicator):
            if widget is not None:
                widget.hide()
                widget.setParent(self)

    def _clear_toolbar_layout(self) -> None:
        """Vacía acciones y widgets del layout sin QToolBar.clear()."""
        self._detach_persistent_widgets()
        for action in list(self.actions()):
            self.removeAction(action)
        self._actions.clear()

    def _add_persistent_widget(self, widget: QWidget) -> None:
        widget.setParent(self)
        widget.setVisible(True)
        widget.show()
        self.addWidget(widget)

    def _rebuild_toolbar(self) -> None:
        self._clear_toolbar_layout()
        if self._active_module == "monitor" and self._monitor_toolbar is not None:
            self._monitor_toolbar.setVisible(True)
            self._add_persistent_widget(self._monitor_toolbar)
            return

        inventory_actions = self._module_actions.get(self._active_module, [])
        for index, action in enumerate(inventory_actions):
            if index in (4, 6, 7):
                self.addSeparator()
            self.addAction(action)
            self._actions.append(action)
        if self._end_spacer is not None and self._project_indicator is not None:
            self._add_persistent_widget(self._end_spacer)
            self._add_persistent_widget(self._project_indicator)

    def update_inventory_actions(
        self,
        *,
        project_open: bool,
        has_selection: bool,
        properties_dirty: bool,
        can_create: bool = False,
        can_duplicate: bool = False,
        can_delete: bool = False,
        can_apply: bool = False,
        can_revert: bool = False,
    ) -> None:
        if self._new_action:
            self._new_action.setEnabled(can_create if project_open else False)
        if self._edit_action:
            self._edit_action.setEnabled(project_open and has_selection)
        if self._duplicate_action:
            self._duplicate_action.setEnabled(project_open and can_duplicate)
        if self._delete_action:
            self._delete_action.setEnabled(project_open and can_delete)
        if self._apply_action:
            self._apply_action.setEnabled(project_open and can_apply)
        if self._revert_action:
            self._revert_action.setEnabled(project_open and can_revert)
        _ = properties_dirty

    def get_toolbar_actions(self) -> List[QAction]:
        return self._actions

    def get_new_action(self) -> Optional[QAction]:
        return self._new_action

    def get_edit_action(self) -> Optional[QAction]:
        return self._edit_action

    def get_duplicate_action(self) -> Optional[QAction]:
        return self._duplicate_action

    def get_delete_action(self) -> Optional[QAction]:
        return self._delete_action

    def get_apply_action(self) -> Optional[QAction]:
        return self._apply_action

    def get_revert_action(self) -> Optional[QAction]:
        return self._revert_action

    def get_columns_action(self) -> Optional[QAction]:
        return self._columns_action

    def get_import_action(self) -> Optional[QAction]:
        return self._import_action

    def get_export_action(self) -> Optional[QAction]:
        return self._export_action

    def get_monitor_toolbar(self):
        return self._monitor_toolbar

    def refresh_icons(self) -> None:
        mapping = (
            ("new", self._new_action),
            ("edit", self._edit_action),
            ("duplicate", self._duplicate_action),
            ("delete", self._delete_action),
            ("activate", self._apply_action),
            ("refresh", self._revert_action),
            ("columns", self._columns_action),
            ("import", self._import_action),
            ("export", self._export_action),
        )
        for name, action in mapping:
            if action:
                action.setIcon(get_app_icon(name, ICON_SIZE_TOOLBAR))

    def recargar_textos(self) -> None:
        if self._new_action:
            self._new_action.setText(tr("inventory_action_new"))
        if self._edit_action:
            self._edit_action.setText(tr("inventory_action_edit"))
        if self._duplicate_action:
            self._duplicate_action.setText(tr("inventory_action_duplicate"))
        if self._delete_action:
            self._delete_action.setText(tr("inventory_action_delete"))
        if self._apply_action:
            self._apply_action.setText(tr("inventory_action_apply"))
        if self._revert_action:
            self._revert_action.setText(tr("inventory_action_revert"))
        if self._columns_action:
            self._columns_action.setText(tr("inventory_table_columns_toolbar"))
        if self._import_action:
            self._import_action.setText(tr("toolbar_import"))
        if self._export_action:
            self._export_action.setText(tr("inventory_toolbar_export"))
            self._export_action.setToolTip(tr("inventory_export_title"))
        if self._monitor_toolbar and hasattr(self._monitor_toolbar, "recargar_textos"):
            self._monitor_toolbar.recargar_textos()
        self.refresh_icons()
