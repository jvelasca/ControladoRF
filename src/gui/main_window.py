"""
MainWindow
==========
Ventana principal de CONTROLADORF.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
)

from core.project_io import (
    PROJECT_FILE_FILTER,
    ProjectIOError,
    default_project_filename,
    normalize_project_path,
)
from core.project_manager import ProjectManager
from i18n.json_translation import tr
from utils.logger import get_logger
from utils.theme_utils import apply_system_appearance
from workspace.aware import WorkspaceAware

from .menu_bar import MenuBar
from .module_tab_manager import ModuleTabManager
from .project_title_widget import ProjectTitleWidget
from .status_bar import StatusBar
from .tool_bar import ToolBar


class MainWindow(QMainWindow, WorkspaceAware):
    """Ventana principal con módulos por pestañas y gestión de proyectos."""

    def __init__(
        self,
        workspace_controller=None,
        database_service=None,
        app_services=None,
        project_manager: Optional[ProjectManager] = None,
    ) -> None:
        self._closing = False
        self._layout_restored = False
        self._pending_restore_config: Optional[Dict[str, Any]] = None
        self._logger = get_logger(__name__)
        self._database_service = database_service
        self._app_services = app_services
        self._project_manager = project_manager

        super().__init__()
        self._workspace_controller = workspace_controller

        from gui.app_branding import apply_app_window_icon

        self.setWindowTitle(tr("app_title"))
        apply_app_window_icon(self)
        self.resize(1200, 800)

        self._menu_bar = MenuBar(self)
        self._tool_bar = ToolBar(self)
        self._tool_bar.setObjectName("MainToolBar")
        self._status_bar = StatusBar(self)
        self._status_bar.setObjectName("MainStatusBar")
        self._workspace_label = None
        self._project_title = ProjectTitleWidget(self)
        self._project_file_label = None
        self._project_ui_restored = False
        self._pending_inventory_table_header: Optional[str] = None
        self._inventory_controller = None
        self._shortcut_refs: list = []
        self._update_worker = None

        self._init_ui()

        self._module_tab_manager = ModuleTabManager(
            on_module_changed=self._on_module_switched,
            on_layout_changed=self._on_layout_changed,
        )
        self.setCentralWidget(self._module_tab_manager.module_tabs)

        self._connect_project_actions()
        self._connect_module_actions()
        self._setup_inventory_controller()
        self._setup_monitor_toolbar()
        self._setup_monitor_shortcuts()
        self._setup_shared_keyboard_shortcuts()

        if self._workspace_controller:
            self._workspace_controller.register_component(self)

        ws = self._workspace_controller.active_workspace if self._workspace_controller else None
        if ws and ws.config:
            pending: Dict[str, Any] = {}
            if geo := ws.config.get("main_window_geometry"):
                pending["main_window_geometry"] = geo
            if ws.config.get("main_window_maximized"):
                pending["main_window_maximized"] = True
            if table_header := ws.config.get("inventory_table_header"):
                pending["inventory_table_header"] = table_header
            if table_alignment := ws.config.get("inventory_table_text_alignment"):
                pending["inventory_table_text_alignment"] = table_alignment
            if pending:
                self._pending_restore_config = pending

        if self._workspace_controller:
            self._workspace_controller.subscribe(self._update_workspace_label)

        if self._project_manager:
            self._project_manager.subscribe(self._update_project_title)
            self._update_project_title()
            self._tool_bar.set_project_indicator(self._project_title)
            self._tool_bar.set_active_module(self._module_tab_manager.active_module)
            self._update_project_actions_state()

        self.recargar_textos()
        self._sync_module_chrome()
        apply_system_appearance()

    def _init_ui(self) -> None:
        self.setMenuBar(self._menu_bar)
        self.addToolBar(self._tool_bar)
        self.setStatusBar(self._status_bar)

        from gui.app_status_bar_panel import AppStatusBarPanel

        self._status_bar_panel = AppStatusBarPanel(self)
        self._status_bar.addPermanentWidget(self._status_bar_panel, 1)
        self._project_file_label = self._status_bar_panel.project_label
        self._workspace_label = self._status_bar_panel.workspace_label
        self._supervision_status_bar = self._status_bar_panel.supervision

        if self._workspace_controller:
            self._update_workspace_label(self._workspace_controller.active_workspace)

        self._menu_bar.get_config_action().triggered.connect(self._show_config_dialog)
        self._menu_bar.get_workspaces_action().triggered.connect(self._show_workspace_manager)
        help_manual = self._menu_bar.get_help_manual_action()
        if help_manual:
            help_manual.triggered.connect(self._show_help_manual)
        help_supervision = self._menu_bar.get_help_supervision_action()
        if help_supervision:
            help_supervision.triggered.connect(self._show_help_supervision)
        check_updates = self._menu_bar.get_check_updates_action()
        if check_updates:
            check_updates.triggered.connect(lambda: self.check_for_updates(manual=True))
        self._menu_bar.get_about_action().triggered.connect(self._show_about_dialog)
        reset_action = self._menu_bar.get_reset_panels_action()
        if reset_action:
            reset_action.triggered.connect(self._reset_panels_layout)

    def _connect_project_actions(self) -> None:
        mb = self._menu_bar
        mb.get_new_project_action().triggered.connect(self._on_new_project)
        mb.get_open_project_action().triggered.connect(self._on_open_project)
        mb.get_save_project_action().triggered.connect(self._on_save_project)
        mb.get_save_project_as_action().triggered.connect(self._on_save_project_as)
        rename_action = mb.get_rename_project_action()
        if rename_action:
            rename_action.triggered.connect(self._on_rename_project)
        mb.get_export_project_action().triggered.connect(self._on_export_project)
        import_wb = mb.get_import_workbench_action()
        if import_wb:
            import_wb.triggered.connect(self._on_import_workbench)
        structure_action = mb.get_project_structure_action()
        if structure_action:
            structure_action.triggered.connect(self._show_project_structure)
        mb.get_exit_action().triggered.connect(self._on_exit_requested)

        import_toolbar = self._tool_bar.get_import_action()
        if import_toolbar:
            import_toolbar.triggered.connect(self._on_import_workbench)

    def _connect_module_actions(self) -> None:
        for panel_id in ("lista", "propiedades", "acciones"):
            action = self._menu_bar.get_panel_action(panel_id)
            if action:
                action.triggered.connect(
                    lambda checked, pid=panel_id: self._set_panel_visible(pid, checked)
                )

    def _setup_inventory_controller(self) -> None:
        from gui.inventory_edit_controller import InventoryEditController

        workspace = self._module_tab_manager.get_workspace("inventario_rf")

        def _get_panels():
            return workspace.get_inventory_panel_contents()

        self._inventory_controller = InventoryEditController(
            parent=self,
            get_project_manager=lambda: self._project_manager,
            resolve_equipo=self._resolve_inventory_equipo,
            get_list_panel=lambda: _get_panels()[0],
            get_properties_panel=lambda: _get_panels()[1],
            get_actions_panel=lambda: _get_panels()[2],
            refresh_inventory=self._refresh_inventory_panel,
            mark_dirty=lambda: (
                self._project_manager.mark_dirty() if self._project_manager else None
            ),
            focus_properties_panel=workspace.focus_properties_panel,
        )
        self._inventory_controller.attach()
        self._inventory_controller.configure_list_panel()

        tb = self._tool_bar
        mapping = (
            (tb.get_new_action(), self._inventory_controller.create_new),
            (tb.get_edit_action(), self._inventory_controller._edit_focus),
            (tb.get_duplicate_action(), self._inventory_controller.duplicate_focus),
            (tb.get_delete_action(), self._inventory_controller.delete_focus),
            (tb.get_apply_action(), self._inventory_controller.apply_properties),
            (tb.get_revert_action(), self._inventory_controller.revert_properties),
        )
        for action, slot in mapping:
            if action:
                action.triggered.connect(slot)

        columns_action = tb.get_columns_action()
        if columns_action:
            columns_action.triggered.connect(self._show_inventory_columns_dialog)

        export_action = tb.get_export_action()
        if export_action:
            export_action.triggered.connect(self._on_export_inventory_list)

        self._inventory_controller.dirty_changed.connect(self._sync_inventory_toolbar)
        self._inventory_controller.focus_changed.connect(
            lambda _focus: self._sync_inventory_toolbar()
        )
        self._setup_inventory_shortcuts()
        self._sync_inventory_toolbar()

    def _setup_monitor_toolbar(self) -> None:
        monitor_ws = self._module_tab_manager.get_workspace("monitor")
        controller = monitor_ws.get_monitor_controller()
        toolbar = self._tool_bar.get_monitor_toolbar()
        if not controller or not toolbar:
            return
        from core.monitor.monitor_export_paths import configure_monitor_export_paths

        if self._project_manager is not None:
            configure_monitor_export_paths(
                self._project_manager._store_get_config,
                self._project_manager._store_set_config,
                default_dir=self._default_projects_dir,
            )
            controller._config.bind_developer_access(
                self._project_manager._store_get_config,
                self._project_manager._store_set_config,
            )
        toolbar.params_changed.connect(controller.apply_params)
        controller.params_updated.connect(toolbar.set_params)
        controller.toolbar_sync_requested.connect(toolbar.set_params)
        controller.bind_toolbar(toolbar)
        controller.transport_changed.connect(toolbar.set_running)
        toolbar.play_requested.connect(controller.start)
        toolbar.stop_requested.connect(controller.stop)
        toolbar.operating_mode_changed.connect(controller.set_operating_mode)
        toolbar.trigger_requested.connect(controller.arm_trigger)
        controller.operating_mode_changed.connect(toolbar.set_operating_mode)
        if toolbar._export_btn is not None:
            toolbar._export_btn.bind_host(controller)
        toolbar.set_params(controller.get_params())
        if self._project_manager is not None:
            controller.bind_project(lambda: self._project_manager)
        if self._database_service is not None:
            controller.bind_database(lambda: self._database_service)
        controller.bind_app_status_bar(self._supervision_status_bar)
        controller.bind_main_window_actions(focus_monitor_alarms=self._focus_monitor_alarms)

    def _focus_monitor_alarms(self) -> None:
        self._module_tab_manager.set_active_module("monitor")
        self._sync_module_chrome("monitor")
        monitor_ws = self._module_tab_manager.get_workspace("monitor")
        controller = monitor_ws.get_monitor_controller() if monitor_ws else None
        if controller is None:
            return
        controller.show_supervision_alarms_window()

    def _setup_monitor_shortcuts(self) -> None:
        from gui.monitor.monitor_shortcuts import setup_monitor_shortcuts

        def _controller():
            ws = self._module_tab_manager.get_workspace("monitor")
            return ws.get_monitor_controller() if ws else None

        def _active() -> bool:
            return self._module_tab_manager.active_module == "monitor"

        setup_monitor_shortcuts(
            self,
            get_controller=_controller,
            is_monitor_active=_active,
        )

    def _setup_shared_keyboard_shortcuts(self) -> None:
        """Atajos compartidos entre módulos (p. ej. F2 Inventario/Monitor)."""
        from PyQt6.QtGui import QKeySequence, QShortcut

        def _on_f2() -> None:
            module = self._module_tab_manager.active_module
            if module == "monitor":
                ws = self._module_tab_manager.get_workspace("monitor")
                ctrl = ws.get_monitor_controller() if ws else None
                if ctrl is not None:
                    ctrl.toggle_transport()
            elif module == "inventario_rf" and self._inventory_controller is not None:
                self._inventory_controller._edit_focus()

        shortcut = QShortcut(QKeySequence("F2"), self)
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(_on_f2)
        self._shortcut_refs.append(shortcut)

    def _when_inventory_module(self, slot):
        def wrapped() -> None:
            if self._module_tab_manager.active_module != "inventario_rf":
                return
            slot()

        return wrapped

    def _show_inventory_columns_dialog(self) -> None:
        workspace = self._module_tab_manager.get_workspace("inventario_rf")
        if workspace is None:
            return
        panels = workspace.get_inventory_panel_contents()
        if panels:
            panels[0].show_columns_dialog(self)

    def _setup_inventory_shortcuts(self) -> None:
        from PyQt6.QtGui import QKeySequence, QShortcut

        controller = self._inventory_controller
        tb = self._tool_bar
        if not controller:
            return
        guard = self._when_inventory_module
        shortcuts = (
            (QKeySequence.StandardKey.New, guard(controller.create_new)),
            (QKeySequence("Ctrl+D"), guard(controller.duplicate_focus)),
            (QKeySequence(Qt.Key.Key_Delete), guard(controller.delete_focus)),
            (QKeySequence.StandardKey.Save, guard(controller.apply_properties)),
            (QKeySequence.StandardKey.Cancel, guard(controller.revert_properties)),
        )
        for sequence, slot in shortcuts:
            shortcut = QShortcut(sequence, self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(slot)
            self._shortcut_refs.append(shortcut)
        tips = (
            (tb.get_new_action(), "inventory_shortcut_new"),
            (tb.get_edit_action(), "inventory_shortcut_edit"),
            (tb.get_duplicate_action(), "inventory_shortcut_duplicate"),
            (tb.get_delete_action(), "inventory_shortcut_delete"),
            (tb.get_apply_action(), "inventory_shortcut_apply"),
            (tb.get_revert_action(), "inventory_shortcut_revert"),
        )
        for action, key in tips:
            if action:
                action.setToolTip(tr(key))

    def _sync_inventory_toolbar(self) -> None:
        if not self._inventory_controller:
            return
        controller = self._inventory_controller
        self._tool_bar.update_inventory_actions(
            project_open=controller._project_open(),
            has_selection=controller.can_edit(),
            properties_dirty=controller.properties_dirty,
            can_create=controller.can_create(),
            can_duplicate=controller.can_duplicate(),
            can_delete=controller.can_delete(),
            can_apply=controller.can_apply(),
            can_revert=controller.can_revert(),
        )

    def _set_panel_visible(self, panel_id: str, visible: bool) -> None:
        self._module_tab_manager.get_active_workspace().set_panel_visible(panel_id, visible)
        self._sync_module_chrome()

    def _sync_module_chrome(self, module_id: Optional[str] = None) -> None:
        """Toolbar, menú Ver y checks de paneles según el módulo activo."""
        module = module_id or self._module_tab_manager.active_module
        self._tool_bar.set_active_module(module)
        self._menu_bar.set_view_module(module)
        self._module_tab_manager.sync_panel_menu_checks(self._menu_bar.get_panel_actions())

    def _on_module_switched(self, previous_module_id: str, new_module_id: str) -> None:
        self._flush_module_layout(previous_module_id, mark_dirty=True)
        self._sync_module_chrome(new_module_id)
        if self._project_manager:
            state = self._project_manager.get_module_ui_state(new_module_id)
            if state:
                self._module_tab_manager.apply_layout_state(new_module_id, state, notify=False)
            self._project_manager.set_active_module(new_module_id, mark_dirty=False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._finalize_window_layout)

    def _finalize_window_layout(self) -> None:
        self._module_tab_manager.ensure_layout_ready()

        if self._pending_restore_config:
            config = self._pending_restore_config
            self._pending_restore_config = None
            from gui.window_state_utils import restore_main_window_layout

            restore_main_window_layout(self, config, defer_maximize=True)
            self._layout_restored = True
            lista_state: Dict[str, Any] = {}
            table_header = config.get("inventory_table_header")
            if isinstance(table_header, str) and table_header:
                lista_state["table_header"] = table_header
            table_alignment = config.get("inventory_table_text_alignment")
            if isinstance(table_alignment, str):
                lista_state["table_text_alignment"] = table_alignment
            self._apply_inventory_list_state(lista_state)

        if self._project_manager and not self._project_ui_restored:
            if not self._project_manager.has_open_project:
                last_path = self._project_manager.get_last_opened_project_path()
                if last_path:
                    try:
                        self._project_manager.open_project(last_path)
                        self._restore_project_ui()
                    except ProjectIOError as exc:
                        self._logger.warning(
                            "No se pudo reabrir el último proyecto (%s): %s",
                            last_path,
                            exc,
                        )
            elif self._project_manager.has_open_project:
                self._restore_project_ui()
            self._project_ui_restored = True

        self._sync_module_chrome()

    def _prepare_project_ui_restore(self) -> None:
        if not self._project_manager or not self._project_manager.project:
            return
        from core.project_model import MODULE_IDS

        active_module = self._project_manager.get_active_module()
        self._module_tab_manager.set_active_module(active_module, save_previous=False)
        self._sync_module_chrome(active_module)

    def _flush_module_layout(self, module_id: str, *, mark_dirty: bool = True) -> None:
        if not self._project_manager or not self._project_manager.project:
            return
        state = self._module_tab_manager.save_module_layout(module_id)
        self._project_manager.set_module_ui_state(module_id, state, mark_dirty=mark_dirty)

    def _flush_all_module_layouts(self, *, mark_dirty: bool = True) -> None:
        if not self._project_manager or not self._project_manager.project:
            return
        layouts = self._module_tab_manager.save_all_module_layouts()
        self._project_manager.replace_all_module_ui(
            layouts,
            active_module=self._module_tab_manager.active_module,
        )
        if mark_dirty:
            self._project_manager.mark_dirty()

    def _on_layout_changed(self) -> None:
        self._sync_module_chrome()
        if self._project_manager:
            self._flush_module_layout(self._module_tab_manager.active_module, mark_dirty=True)

    def _restore_project_ui(self) -> None:
        if not self._project_manager or not self._project_manager.project:
            return
        from core.project_model import MODULE_IDS

        active_module = self._project_manager.get_active_module()
        self._module_tab_manager.set_active_module(active_module, save_previous=False)

        states = {
            module_id: self._project_manager.get_module_ui_state(module_id)
            for module_id in MODULE_IDS
        }
        self._module_tab_manager.apply_all_layout_states(states, notify=False)
        self._sync_module_chrome(active_module)
        self._refresh_inventory_panel()

    def _refresh_inventory_panel(self, *, preserve_selection_key: Optional[str] = None) -> None:
        from gui.inventory_list_panel import InventoryListPanel

        workspace = self._module_tab_manager.get_workspace("inventario_rf")
        workspace.set_inventory_resolver(self._resolve_inventory_equipo)
        content = workspace.get_panel("lista").content
        if not isinstance(content, InventoryListPanel):
            return

        if not self._project_manager or not self._project_manager.has_open_project:
            content.set_equipos([])
            self._sync_inventory_toolbar()
            monitor_ws = self._module_tab_manager.get_workspace("monitor")
            monitor_ctrl = monitor_ws.get_monitor_controller() if monitor_ws else None
            if monitor_ctrl is not None:
                monitor_ctrl.reload_supervision_from_project()
            return

        selection_key = preserve_selection_key
        if selection_key is None and self._inventory_controller:
            selection_key = self._inventory_controller.selected_key

        equipos = self._project_manager.project.modules.get("inventario_rf", {}).get(
            "equipos", []
        )
        content.set_equipos(equipos, preserve_selection_key=selection_key)
        self._sync_inventory_to_database()
        self._sync_inventory_toolbar()
        monitor_ws = self._module_tab_manager.get_workspace("monitor")
        monitor_ctrl = monitor_ws.get_monitor_controller() if monitor_ws else None
        if monitor_ctrl is not None:
            monitor_ctrl.reload_supervision_from_project()

    def _resolve_inventory_equipo(self, item: Optional[Dict[str, Any]]):
        from core.inventory_catalog import enrich_equipo_metadata

        if not item:
            return None
        if not self._project_manager or not self._project_manager.has_open_project:
            return enrich_equipo_metadata(dict(item))
        if self._app_services:
            return self._app_services.inventory.resolve_equipo(
                self._project_manager.project,
                dict(item),
                file_path=self._project_manager.file_path,
            )
        from core.inventory_channel import find_equipo_in_project, channel_key

        key = channel_key(item)
        found = find_equipo_in_project(self._project_manager.project, key)
        return enrich_equipo_metadata(dict(found or item))

    def _sync_inventory_to_database(self) -> None:
        if not self._app_services or not self._project_manager:
            return
        if not self._project_manager.has_open_project:
            return
        try:
            count = self._app_services.inventory.sync_project(
                self._project_manager.project,
                self._project_manager.file_path,
            )
            if self._database_service:
                db_path = self._database_service.settings.resolved_path(
                    self._database_service.data_dir
                )
                self._status_bar.showMessage(
                    tr("inventory_db_synced", count=count, path=str(db_path)),
                    5000,
                )
            self._logger.debug("Inventario sincronizado en BD: %s canales", count)
        except Exception as exc:
            self._logger.warning("No se pudo sincronizar inventario en BD: %s", exc)

    def _on_import_workbench(self) -> None:
        if not self._project_manager:
            return

        from gui.busy_overlay import busy_dialog
        from gui.workbench_import_dialog import WorkbenchImportDialog
        from importers.workbench_parser import (
            WORKBENCH_FILE_FILTER,
            WorkbenchImportError,
            apply_workbench_coordination_to_project,
            apply_workbench_inventory_to_project,
            parse_workbench_show,
        )

        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("workbench_import_file_title"),
            self._default_projects_dir(),
            WORKBENCH_FILE_FILTER,
        )
        if not path:
            return

        try:
            with busy_dialog(
                self,
                title=tr("workbench_import_busy_title"),
                message=tr("workbench_import_busy_parsing"),
            ):
                show = parse_workbench_show(path)
        except WorkbenchImportError as exc:
            QMessageBox.critical(
                self, tr("error_title"), tr("workbench_import_error", error=str(exc))
            )
            return

        has_project = self._project_manager.has_open_project
        dialog = WorkbenchImportDialog(show, self, allow_replace=has_project)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        if dialog.selected_mode == WorkbenchImportDialog.MODE_NEW_PROJECT:
            if has_project and not self._confirm_discard_changes():
                return
            if has_project:
                self._flush_all_module_layouts(mark_dirty=False)
            self._project_manager.new_project(show.info.name or tr("project_untitled_show"))
            self._module_tab_manager.reset_all_layouts()
        elif self._project_manager.is_dirty and not self._confirm_discard_changes():
            return

        try:
            with busy_dialog(
                self,
                title=tr("workbench_import_busy_title"),
                message=tr("workbench_import_busy_applying"),
            ):
                apply_workbench_inventory_to_project(self._project_manager.project, show)
                if dialog.import_coordination:
                    apply_workbench_coordination_to_project(
                        self._project_manager.project, show
                    )
                self._project_manager.mark_dirty()
                self._module_tab_manager.set_active_module("inventario_rf", save_previous=False)
                self._sync_module_chrome("inventario_rf")
                self._refresh_inventory_panel()
                self._update_project_actions_state()
        except Exception as exc:
            self._logger.exception("Error aplicando import Workbench")
            QMessageBox.critical(
                self, tr("error_title"), tr("workbench_import_error", error=str(exc))
            )
            return

        self._status_bar.showMessage(
            tr("workbench_import_done", name=show.info.name, channels=show.channel_count),
            6000,
        )

    def _show_project_structure(self) -> None:
        from gui.project_structure_dialog import ProjectStructureDialog

        dlg = ProjectStructureDialog(
            self._project_manager,
            self._module_tab_manager,
            self,
        )
        dlg.setModal(True)
        dlg.exec()

    def _on_rename_project(self) -> None:
        if not self._project_manager or not self._project_manager.project:
            return
        current = self._project_manager.get_project_name()
        name, ok = QInputDialog.getText(
            self,
            tr("project_rename_title"),
            tr("project_rename_prompt"),
            text=current,
        )
        if not ok:
            return
        cleaned = name.strip()
        if not cleaned or cleaned == current:
            return
        self._project_manager.update_project_name(cleaned)
        self._status_bar.showMessage(tr("project_renamed", name=cleaned), 3000)

    def _update_project_title(self) -> None:
        self.setWindowTitle(tr("app_title"))

        if not self._project_manager:
            self._project_title.set_state(show_name="", dirty=False, has_project=False)
            if self._project_file_label:
                self._project_file_label.setText("")
            self._update_project_actions_state()
            return

        pm = self._project_manager
        has_project = pm.has_open_project
        self._project_title.set_state(
            show_name=pm.get_project_name() if has_project else "",
            dirty=pm.is_dirty,
            has_project=has_project,
            file_path=pm.get_file_path(),
        )
        if self._project_file_label is not None:
            if has_project and (path := pm.get_file_path()):
                self._project_file_label.setText(path)
                self._project_file_label.setToolTip(path)
            elif has_project:
                self._project_file_label.setText(tr("project_file_unsaved"))
                self._project_file_label.setToolTip(tr("project_file_unsaved_hint"))
            else:
                self._project_file_label.setText("")
                self._project_file_label.setToolTip("")
        self._update_project_actions_state()

    def _update_project_actions_state(self) -> None:
        mb = self._menu_bar
        has_project = bool(
            self._project_manager and self._project_manager.has_open_project
        )
        for getter in (
            mb.get_save_project_action,
            mb.get_save_project_as_action,
            mb.get_rename_project_action,
            mb.get_export_project_action,
        ):
            action = getter()
            if action:
                action.setEnabled(has_project)
        structure_action = mb.get_project_structure_action()
        if structure_action:
            structure_action.setEnabled(has_project)
        if self._tool_bar.get_export_action():
            self._tool_bar.get_export_action().setEnabled(has_project)

    def _on_new_project(self) -> None:
        if not self._project_manager:
            return
        if self._project_manager.has_open_project:
            if not self._confirm_discard_changes():
                return
            self._flush_all_module_layouts(mark_dirty=False)
        self._project_manager.new_project()
        self._module_tab_manager.reset_all_layouts()
        self._module_tab_manager.set_active_module("inventario_rf", save_previous=False)
        self._sync_module_chrome("inventario_rf")
        self._refresh_inventory_panel()
        self._status_bar.showMessage(tr("project_created"), 4000)

    def _on_open_project(self) -> None:
        if not self._confirm_discard_changes():
            return
        start_dir = self._default_projects_dir()
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("project_open_title"),
            start_dir,
            PROJECT_FILE_FILTER,
        )
        if path:
            self._open_project_path(path)

    def _open_project_path(self, path: str) -> None:
        if not self._project_manager:
            return
        try:
            if self._project_manager.has_open_project:
                self._flush_all_module_layouts(mark_dirty=False)
            self._project_manager.open_project(path)
            self._restore_project_ui()
            monitor_ws = self._module_tab_manager.get_workspace("monitor")
            monitor_ctrl = monitor_ws.get_monitor_controller() if monitor_ws else None
            if monitor_ctrl is not None:
                monitor_ctrl.bind_project(lambda: self._project_manager)
            opened_name = self._project_manager.get_project_name()
            self._status_bar.showMessage(tr("project_opened", name=opened_name), 4000)
        except ProjectIOError as exc:
            QMessageBox.critical(self, tr("error_title"), tr("project_open_error", error=str(exc)))

    def _on_save_project(self) -> None:
        if not self._project_manager or not self._project_manager.project:
            return
        self._flush_all_module_layouts(mark_dirty=False)
        self._project_manager.set_active_module(
            self._module_tab_manager.active_module,
            mark_dirty=False,
        )
        if self._project_manager.file_path:
            if self._project_manager.save_project():
                self._status_bar.showMessage(tr("project_saved"), 4000)
            return
        self._on_save_project_as()

    def _on_save_project_as(self) -> None:
        if not self._project_manager or not self._project_manager.project:
            return
        self._flush_all_module_layouts(mark_dirty=False)
        self._project_manager.set_active_module(
            self._module_tab_manager.active_module,
            mark_dirty=False,
        )
        default_name = default_project_filename(self._project_manager.get_project_name())
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("project_save_as_title"),
            os.path.join(self._default_projects_dir(), default_name),
            PROJECT_FILE_FILTER,
        )
        if not path:
            return
        path = normalize_project_path(path)
        try:
            self._project_manager.save_project_as(path)
            self._status_bar.showMessage(tr("project_saved"), 4000)
        except ProjectIOError as exc:
            QMessageBox.critical(self, tr("error_title"), tr("project_save_error", error=str(exc)))

    def _on_export_project(self) -> None:
        if not self._project_manager or not self._project_manager.project:
            return
        self._flush_all_module_layouts(mark_dirty=True)
        default_name = default_project_filename(
            self._project_manager.get_project_name(), export=True
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("project_export_title"),
            os.path.join(self._default_projects_dir(), default_name),
            PROJECT_FILE_FILTER,
        )
        if not path:
            return
        path = normalize_project_path(path)
        try:
            self._project_manager.export_project(path)
            self._status_bar.showMessage(tr("project_exported"), 4000)
        except ProjectIOError as exc:
            QMessageBox.critical(self, tr("error_title"), tr("project_save_error", error=str(exc)))

    def _on_export_inventory_list(self) -> None:
        if not self._project_manager or not self._project_manager.project:
            return
        from gui.inventory_export_dialog import InventoryExportDialog

        dialog = InventoryExportDialog(
            self,
            project=self._project_manager.project,
            project_name=self._project_manager.get_project_name(),
            default_dir=self._default_projects_dir(),
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self._status_bar.showMessage(tr("inventory_export_done"), 5000)

    def _on_exit_requested(self) -> None:
        if self._confirm_close():
            self.close()

    def _confirm_discard_changes(self) -> bool:
        if (
            not self._project_manager
            or not self._project_manager.has_open_project
            or not self._project_manager.is_dirty
        ):
            return True
        from gui.message_box_utils import SaveDiscardCancel, ask_save_discard_cancel

        answer = ask_save_discard_cancel(
            self,
            tr("project_unsaved_title"),
            tr("project_unsaved_discard"),
        )
        if answer == SaveDiscardCancel.CANCEL:
            return False
        if answer == SaveDiscardCancel.SAVE:
            self._on_save_project()
            return not self._project_manager.is_dirty
        return True

    def _confirm_close(self) -> bool:
        if (
            not self._project_manager
            or not self._project_manager.has_open_project
            or not self._project_manager.is_dirty
        ):
            return True
        from gui.message_box_utils import SaveDiscardCancel, ask_save_discard_cancel

        answer = ask_save_discard_cancel(
            self,
            tr("project_unsaved_title"),
            tr("project_unsaved_close"),
        )
        if answer == SaveDiscardCancel.CANCEL:
            return False
        if answer == SaveDiscardCancel.SAVE:
            self._on_save_project()
            return not self._project_manager.is_dirty
        return True

    def _default_projects_dir(self) -> str:
        if self._project_manager and self._project_manager.file_path:
            return os.path.dirname(self._project_manager.file_path)
        return os.path.expanduser("~/Documents")

    def open_recent_project(self, path: str) -> None:
        if self._confirm_discard_changes():
            self._open_project_path(path)

    def refresh_recent_projects_menu(self) -> None:
        if not self._project_manager:
            return
        self._menu_bar.set_recent_projects(
            self._project_manager.get_recent_projects(),
            self.open_recent_project,
        )

    def _show_config_dialog(self) -> None:
        from gui.config_dialog import ConfigDialog

        dlg = ConfigDialog(self._workspace_controller, self._database_service, self)
        dlg.setModal(True)
        dlg.exec()

    def _show_workspace_manager(self) -> None:
        from gui.workspace_manager import WorkspaceManagerDialog

        dlg = WorkspaceManagerDialog(self._workspace_controller, self)
        dlg.setModal(True)
        dlg.exec()

    def check_for_updates(self, *, manual: bool = False) -> None:
        from core.app_update import UpdateInfo, check_for_update, load_update_config
        from gui.app_branding import get_app_version
        from gui.app_update_dialog import AppUpdateDialog
        from gui.app_update_worker import AppUpdateCheckWorker

        config = load_update_config()
        if not config.get("enabled") and manual:
            QMessageBox.information(
                self,
                tr("app_update_title"),
                tr("app_update_error"),
            )
            return

        if self._update_worker is not None and self._update_worker.isRunning():
            return

        if manual:
            info = check_for_update()
            self._present_update_result(info, manual=True)
            return

        self._update_worker = AppUpdateCheckWorker(self)
        self._update_worker.finished_check.connect(
            lambda result: self._present_update_result(result, manual=False)
        )
        self._update_worker.start()

    def _present_update_result(self, info, *, manual: bool) -> None:
        from core.app_update import UpdateInfo
        from gui.app_branding import get_app_version
        from gui.app_update_dialog import AppUpdateDialog

        self._update_worker = None
        if isinstance(info, UpdateInfo):
            AppUpdateDialog(info, parent=self).exec()
            return
        if manual:
            QMessageBox.information(
                self,
                tr("app_update_title"),
                tr("app_update_none").format(version=get_app_version()),
            )

    def schedule_startup_update_check(self) -> None:
        from core.app_update import load_update_config

        config = load_update_config()
        if not config.get("enabled") or not config.get("check_on_startup", True):
            return
        QTimer.singleShot(4000, lambda: self.check_for_updates(manual=False))

    def _show_about_dialog(self) -> None:
        from gui.about_dialog import AboutDialog

        dlg = AboutDialog(self)
        dlg.exec()

    def _show_help_manual(self) -> None:
        from gui.help_dialog import show_help_dialog

        show_help_dialog("manual", parent=self)

    def _show_help_supervision(self) -> None:
        from gui.help_dialog import show_help_dialog

        show_help_dialog("supervision", parent=self)

    def _reset_panels_layout(self) -> None:
        self._module_tab_manager.reset_active_module_layout()
        self._module_tab_manager.sync_panel_menu_checks(self._menu_bar.get_panel_actions())
        if self._workspace_controller:
            self._workspace_controller.save_active_workspace()
        self._status_bar.showMessage(tr("view_reset_panels_done"), 4000)

    def _get_inventory_list_state(self) -> Dict[str, Any]:
        from gui.inventory_list_panel import InventoryListPanel

        workspace = self._module_tab_manager.get_workspace("inventario_rf")
        content = workspace.get_panel("lista").content
        if isinstance(content, InventoryListPanel):
            return content.save_content_state()
        return {}

    def _get_inventory_table_header_state(self) -> str:
        return str(self._get_inventory_list_state().get("table_header") or "")

    def _apply_inventory_list_state(self, state: Dict[str, Any]) -> None:
        from gui.inventory_list_panel import InventoryListPanel

        if not state:
            return
        workspace = self._module_tab_manager.get_workspace("inventario_rf")
        content = workspace.get_panel("lista").content
        if isinstance(content, InventoryListPanel):
            content.restore_content_state(state)

    def _apply_inventory_table_header_state(self, header_state: str) -> None:
        self._apply_inventory_list_state({"table_header": header_state})

    def save_state(self) -> Dict[str, Any]:
        from gui.window_state_utils import capture_main_window_layout

        state = capture_main_window_layout(self)
        lista_state = self._get_inventory_list_state()
        if header := lista_state.get("table_header"):
            state["inventory_table_header"] = header
        if alignment := lista_state.get("table_text_alignment"):
            state["inventory_table_text_alignment"] = alignment
        return state

    def restore_state(self, config: Dict[str, Any]) -> None:
        from gui.window_state_utils import restore_main_window_layout

        restore_main_window_layout(self, config, defer_maximize=True)
        lista_state: Dict[str, Any] = {}
        table_header = config.get("inventory_table_header")
        if isinstance(table_header, str) and table_header:
            lista_state["table_header"] = table_header
        table_alignment = config.get("inventory_table_text_alignment")
        if isinstance(table_alignment, str):
            lista_state["table_text_alignment"] = table_alignment
        self._apply_inventory_list_state(lista_state)

    def apply_panel_themes(self) -> None:
        self._module_tab_manager.apply_panel_themes()

    def refresh_appearance(self) -> None:
        apply_system_appearance()
        self._module_tab_manager.apply_tab_chrome()
        self.apply_panel_themes()
        from gui.app_chrome_styles import apply_project_title_styles

        apply_project_title_styles(self._project_title)
        if self._menu_bar and hasattr(self._menu_bar, "refresh_icons"):
            self._menu_bar.refresh_icons()
        if self._tool_bar and hasattr(self._tool_bar, "refresh_icons"):
            self._tool_bar.refresh_icons()

    def get_menu_bar(self) -> MenuBar:
        return self._menu_bar

    def get_tool_bar(self) -> ToolBar:
        return self._tool_bar

    def get_status_bar(self) -> StatusBar:
        return self._status_bar

    def recargar_textos(self) -> None:
        if self._menu_bar:
            self._menu_bar.recargar_textos()
        if self._tool_bar:
            self._tool_bar.recargar_textos()
        if self._status_bar:
            self._status_bar.recargar_textos()
        if hasattr(self, "_supervision_status_bar") and self._supervision_status_bar is not None:
            self._supervision_status_bar.recargar_textos()
        self._module_tab_manager.recargar_textos()
        self._sync_module_chrome()
        self.apply_panel_themes()
        if self._workspace_controller:
            self._update_workspace_label(self._workspace_controller.active_workspace)
        self.refresh_recent_projects_menu()
        self._update_project_title()

    def closeEvent(self, event) -> None:
        if not getattr(self, "_closing", False):
            if not self._confirm_close():
                event.ignore()
                return
            self._closing = True
            if self._project_manager and self._project_manager.has_open_project:
                self._flush_all_module_layouts(mark_dirty=False)
                self._project_manager.set_active_module(
                    self._module_tab_manager.active_module,
                    mark_dirty=False,
                )
                if self._project_manager.is_dirty and self._project_manager.file_path:
                    try:
                        self._project_manager.save_project()
                    except ProjectIOError as exc:
                        self._logger.error("Auto-guardado al cerrar falló: %s", exc)
            if self._workspace_controller:
                self._workspace_controller.save_active_workspace()
            self._shutdown_module_controllers()
        super().closeEvent(event)

    def _shutdown_module_controllers(self) -> None:
        monitor_ws = self._module_tab_manager.get_workspace("monitor")
        if monitor_ws is None:
            return
        controller = monitor_ws.get_monitor_controller()
        if controller is not None:
            controller.shutdown()

    def _update_workspace_label(self, ws) -> None:
        if self._workspace_label is None:
            return
        if ws is not None:
            self._workspace_label.setText(tr("active_workspace", name=ws.name))
        else:
            self._workspace_label.setText(tr("active_workspace_none"))
