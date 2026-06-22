"""
menu_bar.py
-----------
Barra de menús principal de CONTROLADORF.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu, QMenuBar

from gui.icon_utils import ICON_SIZE_MENU, get_app_icon
from i18n.json_translation import tr


# Iconos del menú Ver por módulo (panel_id → clave APP_ICONS).
VIEW_PANEL_ICONS: dict[str, dict[str, str]] = {
    "inventario_rf": {
        "lista": "lista",
        "propiedades": "propiedades",
        "acciones": "acciones",
    },
    "monitor": {
        "lista": "spectrum",
        "acciones": "waterfall",
        "propiedades": "device",
    },
    "coordinacion": {
        "lista": "lista",
        "propiedades": "propiedades",
        "acciones": "acciones",
    },
}


class MenuBar(QMenuBar):
    """Barra de menús principal de la aplicación."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._file_menu: Optional[QMenu] = None
        self._edit_menu: Optional[QMenu] = None
        self._view_menu: Optional[QMenu] = None
        self._tools_menu: Optional[QMenu] = None
        self._help_menu: Optional[QMenu] = None
        self._open_menu: Optional[QMenu] = None
        self._panel_actions: Dict[str, QAction] = {}
        self._new_project_action: Optional[QAction] = None
        self._open_project_action: Optional[QAction] = None
        self._save_project_action: Optional[QAction] = None
        self._save_project_as_action: Optional[QAction] = None
        self._rename_project_action: Optional[QAction] = None
        self._import_workbench_action: Optional[QAction] = None
        self._export_project_action: Optional[QAction] = None
        self._project_structure_action: Optional[QAction] = None
        self._channelization_action: Optional[QAction] = None
        self._config_action: Optional[QAction] = None
        self._workspaces_action: Optional[QAction] = None
        self._exit_action: Optional[QAction] = None
        self._help_manual_action: Optional[QAction] = None
        self._help_supervision_action: Optional[QAction] = None
        self._check_updates_action: Optional[QAction] = None
        self._about_action: Optional[QAction] = None
        self._reset_panels_action: Optional[QAction] = None
        self._recent_open_handler: Optional[Callable[[str], None]] = None
        self._view_module_id: str = "inventario_rf"
        self._init_menus()

    def _init_menus(self) -> None:
        self._file_menu = self.addMenu(tr("file"))
        self._edit_menu = self.addMenu(tr("edit"))
        self._view_menu = self.addMenu(tr("view"))
        self._tools_menu = self.addMenu(tr("tools"))
        self._help_menu = self.addMenu(tr("help"))

        self._new_project_action = self._file_menu.addAction(
            get_app_icon("new", ICON_SIZE_MENU), tr("project_new")
        )
        self._open_menu = QMenu(tr("project_open"), self)
        self._open_project_action = self._open_menu.addAction(
            get_app_icon("open", ICON_SIZE_MENU), tr("project_open_file")
        )
        self._open_menu.addSeparator()
        self._file_menu.addMenu(self._open_menu)
        self._file_menu.addSeparator()
        self._save_project_action = self._file_menu.addAction(
            get_app_icon("save", ICON_SIZE_MENU), tr("project_save")
        )
        self._save_project_as_action = self._file_menu.addAction(
            get_app_icon("save", ICON_SIZE_MENU), tr("project_save_as")
        )
        self._rename_project_action = self._file_menu.addAction(
            get_app_icon("edit", ICON_SIZE_MENU), tr("project_rename")
        )
        self._file_menu.addSeparator()
        self._import_workbench_action = self._file_menu.addAction(
            get_app_icon("import", ICON_SIZE_MENU), tr("project_import_workbench")
        )
        self._export_project_action = self._file_menu.addAction(
            get_app_icon("export", ICON_SIZE_MENU), tr("project_export")
        )
        self._file_menu.addSeparator()
        self._exit_action = self._file_menu.addAction(
            get_app_icon("exit", ICON_SIZE_MENU), tr("exit")
        )

        for panel_id, key in (
            ("lista", "panel_lista"),
            ("propiedades", "panel_propiedades"),
            ("acciones", "panel_acciones"),
        ):
            action = self._view_menu.addAction(
                get_app_icon(panel_id, ICON_SIZE_MENU), tr(key)
            )
            action.setCheckable(True)
            action.setChecked(True)
            self._panel_actions[panel_id] = action

        self._view_menu.addSeparator()
        self._reset_panels_action = self._view_menu.addAction(
            get_app_icon("reset_panels", ICON_SIZE_MENU), tr("view_reset_panels")
        )

        self._config_action = self._tools_menu.addAction(
            get_app_icon("settings", ICON_SIZE_MENU), tr("settings")
        )
        self._workspaces_action = self._tools_menu.addAction(
            get_app_icon("workspaces", ICON_SIZE_MENU), tr("workspaces")
        )
        self._tools_menu.addSeparator()
        self._channelization_action = self._tools_menu.addAction(
            get_app_icon("spectrum", ICON_SIZE_MENU), tr("tools_channelization")
        )
        self._project_structure_action = self._tools_menu.addAction(
            get_app_icon("workspaces", ICON_SIZE_MENU), tr("tools_project_structure")
        )

        self._help_manual_action = self._help_menu.addAction(
            get_app_icon("about", ICON_SIZE_MENU), tr("help_manual")
        )
        self._help_supervision_action = self._help_menu.addAction(
            get_app_icon("spectrum", ICON_SIZE_MENU), tr("help_supervision")
        )
        self._help_menu.addSeparator()
        self._check_updates_action = self._help_menu.addAction(
            get_app_icon("refresh", ICON_SIZE_MENU), tr("app_update_check")
        )
        self._about_action = self._help_menu.addAction(
            get_app_icon("about", ICON_SIZE_MENU), tr("about")
        )
        self._apply_help_tooltips()
        self._apply_view_panel_labels()

    def _apply_help_tooltips(self) -> None:
        if self._help_manual_action is not None:
            self._help_manual_action.setToolTip(tr("help_manual_tip"))
        if self._help_supervision_action is not None:
            self._help_supervision_action.setToolTip(tr("help_supervision_tip"))
        if self._check_updates_action is not None:
            self._check_updates_action.setToolTip(tr("app_update_check_tip"))

    def set_view_module(self, module_id: str) -> None:
        """Actualiza textos e iconos del menú Ver según el módulo activo."""
        if module_id:
            self._view_module_id = module_id
        self._apply_view_panel_labels()

    def _view_panel_text_key(self, panel_id: str) -> str:
        return f"{self._view_module_id}_panel_{panel_id}_title"

    def _view_panel_icon_name(self, panel_id: str) -> str:
        module_icons = VIEW_PANEL_ICONS.get(self._view_module_id, {})
        return module_icons.get(panel_id, panel_id)

    def _apply_view_panel_labels(self) -> None:
        for panel_id, action in self._panel_actions.items():
            action.setText(tr(self._view_panel_text_key(panel_id)))
            action.setIcon(
                get_app_icon(self._view_panel_icon_name(panel_id), ICON_SIZE_MENU)
            )

    def set_recent_projects(
        self,
        recents: List[Dict[str, str]],
        open_handler: Callable[[str], None],
    ) -> None:
        self._recent_open_handler = open_handler
        if self._open_menu is None:
            return

        for action in self._open_menu.actions()[2:]:
            self._open_menu.removeAction(action)

        if not recents:
            empty = self._open_menu.addAction(tr("project_recent_empty"))
            empty.setEnabled(False)
            return

        for entry in recents:
            path = entry.get("path", "")
            name = entry.get("name", path)
            action = self._open_menu.addAction(name)
            action.setToolTip(path)
            action.triggered.connect(
                lambda _checked=False, p=path: self._recent_open_handler(p)
                if self._recent_open_handler
                else None
            )

    def refresh_icons(self) -> None:
        icon_map = {
            self._new_project_action: "new",
            self._open_project_action: "open",
            self._save_project_action: "save",
            self._save_project_as_action: "save",
            self._rename_project_action: "edit",
            self._import_workbench_action: "import",
            self._export_project_action: "export",
            self._exit_action: "exit",
            self._config_action: "settings",
            self._workspaces_action: "workspaces",
            self._channelization_action: "spectrum",
            self._project_structure_action: "workspaces",
            self._help_manual_action: "about",
            self._help_supervision_action: "spectrum",
            self._check_updates_action: "refresh",
            self._about_action: "about",
            self._reset_panels_action: "reset_panels",
        }
        for action, name in icon_map.items():
            if action:
                action.setIcon(get_app_icon(name, ICON_SIZE_MENU))
        self._apply_view_panel_labels()

    def get_new_project_action(self) -> Optional[QAction]:
        return self._new_project_action

    def get_open_project_action(self) -> Optional[QAction]:
        return self._open_project_action

    def get_save_project_action(self) -> Optional[QAction]:
        return self._save_project_action

    def get_save_project_as_action(self) -> Optional[QAction]:
        return self._save_project_as_action

    def get_rename_project_action(self) -> Optional[QAction]:
        return self._rename_project_action

    def get_import_workbench_action(self) -> Optional[QAction]:
        return self._import_workbench_action

    def get_project_structure_action(self) -> Optional[QAction]:
        return self._project_structure_action

    def get_channelization_action(self) -> Optional[QAction]:
        return self._channelization_action

    def get_export_project_action(self) -> Optional[QAction]:
        return self._export_project_action

    def get_reset_panels_action(self) -> Optional[QAction]:
        return self._reset_panels_action

    def get_file_menu(self) -> Optional[QMenu]:
        return self._file_menu

    def get_edit_menu(self) -> Optional[QMenu]:
        return self._edit_menu

    def get_view_menu(self) -> Optional[QMenu]:
        return self._view_menu

    def get_tools_menu(self) -> Optional[QMenu]:
        return self._tools_menu

    def get_config_action(self) -> Optional[QAction]:
        return self._config_action

    def get_workspaces_action(self) -> Optional[QAction]:
        return self._workspaces_action

    def get_help_menu(self) -> Optional[QMenu]:
        return self._help_menu

    def get_panel_actions(self) -> Dict[str, QAction]:
        return self._panel_actions

    def get_panel_action(self, panel_id: str) -> Optional[QAction]:
        return self._panel_actions.get(panel_id)

    def get_help_manual_action(self) -> Optional[QAction]:
        return self._help_manual_action

    def get_help_supervision_action(self) -> Optional[QAction]:
        return self._help_supervision_action

    def get_check_updates_action(self) -> Optional[QAction]:
        return self._check_updates_action

    def get_about_action(self) -> Optional[QAction]:
        return self._about_action

    def get_exit_action(self) -> Optional[QAction]:
        return self._exit_action

    def recargar_textos(self) -> None:
        self._file_menu.setTitle(tr("file"))
        self._edit_menu.setTitle(tr("edit"))
        self._view_menu.setTitle(tr("view"))
        self._tools_menu.setTitle(tr("tools"))
        self._help_menu.setTitle(tr("help"))
        self._new_project_action.setText(tr("project_new"))
        self._open_menu.setTitle(tr("project_open"))
        self._open_project_action.setText(tr("project_open_file"))
        self._save_project_action.setText(tr("project_save"))
        self._save_project_as_action.setText(tr("project_save_as"))
        if self._rename_project_action:
            self._rename_project_action.setText(tr("project_rename"))
        if self._import_workbench_action:
            self._import_workbench_action.setText(tr("project_import_workbench"))
        self._export_project_action.setText(tr("project_export"))
        self._config_action.setText(tr("settings"))
        self._workspaces_action.setText(tr("workspaces"))
        if self._channelization_action:
            self._channelization_action.setText(tr("tools_channelization"))
        if self._project_structure_action:
            self._project_structure_action.setText(tr("tools_project_structure"))
        if self._help_manual_action:
            self._help_manual_action.setText(tr("help_manual"))
        if self._help_supervision_action:
            self._help_supervision_action.setText(tr("help_supervision"))
        if self._check_updates_action:
            self._check_updates_action.setText(tr("app_update_check"))
        self._about_action.setText(tr("about"))
        self._apply_help_tooltips()
        self._exit_action.setText(tr("exit"))
        for panel_id, action in self._panel_actions.items():
            action.setText(tr(self._view_panel_text_key(panel_id)))
        if self._reset_panels_action:
            self._reset_panels_action.setText(tr("view_reset_panels"))
        self.refresh_icons()
        self._apply_view_panel_labels()
