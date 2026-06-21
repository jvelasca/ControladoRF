"""Pestañas centrales con un espacio de trabajo independiente por módulo."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTabWidget

from core.project_model import MODULE_IDS
from gui.module_panel_frame import ModulePanelFrame
from gui.module_workspace import ModuleWorkspaceWidget
from i18n.json_translation import tr

MODULE_I18N_KEYS = {
    "inventario_rf": "module_inventario_rf",
    "coordinacion": "module_coordinacion",
    "monitor": "module_monitor",
}


class ModuleTabManager:
    """Gestiona las 3 pestañas de trabajo y sus paneles internos."""

    def __init__(
        self,
        *,
        on_module_changed: Optional[Callable[[str, str], None]] = None,
        on_layout_changed: Optional[Callable[[], None]] = None,
    ) -> None:
        self._on_module_changed = on_module_changed
        self._on_layout_changed = on_layout_changed
        self._active_module = MODULE_IDS[0]
        self._pending_module_ui: Dict[str, Dict[str, Any]] = {}

        self._module_tabs = QTabWidget()
        self._module_tabs.setObjectName("ModuleMainTabs")
        self._module_tabs.setDocumentMode(False)
        self._module_tabs.setUsesScrollButtons(True)
        self._module_tabs.setElideMode(Qt.TextElideMode.ElideNone)
        self._module_tabs.currentChanged.connect(self._on_tab_changed)
        self.apply_tab_chrome()

        self._workspaces: Dict[str, ModuleWorkspaceWidget] = {}
        for module_id in MODULE_IDS:
            workspace = ModuleWorkspaceWidget(
                module_id,
                on_layout_changed=self._emit_layout_changed,
            )
            self._workspaces[module_id] = workspace
            self._module_tabs.addTab(workspace, tr(MODULE_I18N_KEYS[module_id]))

    @property
    def active_module(self) -> str:
        return self._active_module

    @property
    def module_tabs(self) -> QTabWidget:
        return self._module_tabs

    def get_workspace(self, module_id: str) -> ModuleWorkspaceWidget:
        return self._workspaces[module_id]

    def get_active_workspace(self) -> ModuleWorkspaceWidget:
        return self._workspaces[self._active_module]

    def get_active_panels(self) -> Dict[str, ModulePanelFrame]:
        return self.get_active_workspace().get_panels()

    def set_active_module(self, module_id: str, *, save_previous: bool = True) -> None:
        if module_id not in MODULE_IDS or module_id == self._active_module:
            return
        if save_previous and self._on_module_changed:
            self._on_module_changed(self._active_module, module_id)
        self._active_module = module_id
        index = MODULE_IDS.index(module_id)
        self._module_tabs.blockSignals(True)
        self._module_tabs.setCurrentIndex(index)
        self._module_tabs.blockSignals(False)

    def save_module_layout(self, module_id: str) -> Dict[str, Any]:
        return self._workspaces[module_id].save_state()

    def save_all_module_layouts(self) -> Dict[str, Dict[str, Any]]:
        return {
            module_id: self.save_module_layout(module_id) for module_id in MODULE_IDS
        }

    def apply_layout_state(
        self,
        module_id: str,
        config: Dict[str, Any],
        *,
        notify: bool = True,
    ) -> None:
        if not config:
            return
        self._workspaces[module_id].restore_state(config)
        if notify:
            self._emit_layout_changed()

    def apply_all_layout_states(
        self,
        states: Dict[str, Dict[str, Any]],
        *,
        notify: bool = False,
    ) -> None:
        for module_id in MODULE_IDS:
            state = states.get(module_id)
            if state:
                self.apply_layout_state(module_id, state, notify=False)
        if notify:
            self._emit_layout_changed()

    def queue_module_ui_state(self, module_id: str, state: Dict[str, Any]) -> None:
        if not state:
            return
        self._workspaces[module_id].restore_state(state)

    def ensure_layout_ready(self) -> None:
        self._pending_module_ui.clear()

    def reset_all_layouts(self) -> None:
        for workspace in self._workspaces.values():
            workspace.reset_layout()
        self._pending_module_ui.clear()

    def reset_active_module_layout(self) -> None:
        self.get_active_workspace().reset_layout()
        self._emit_layout_changed()

    def recargar_textos(self) -> None:
        for index, module_id in enumerate(MODULE_IDS):
            self._module_tabs.setTabText(index, tr(MODULE_I18N_KEYS[module_id]))
        for workspace in self._workspaces.values():
            workspace.recargar_textos()

    def apply_panel_themes(self) -> None:
        for workspace in self._workspaces.values():
            workspace.apply_panel_themes()

    def apply_tab_chrome(self) -> None:
        from gui.app_chrome_styles import apply_module_main_tab_styles

        apply_module_main_tab_styles(self._module_tabs)

    def sync_panel_menu_checks(self, panel_actions: Dict[str, Any]) -> None:
        panels = self.get_active_workspace().get_panels()
        for panel_id, action in panel_actions.items():
            if action and panel_id in panels:
                action.setChecked(not panels[panel_id].isHidden())

    def _on_tab_changed(self, index: int) -> None:
        if index < 0 or index >= len(MODULE_IDS):
            return
        new_module = MODULE_IDS[index]
        if new_module == self._active_module:
            return
        previous = self._active_module
        self._active_module = new_module
        if self._on_module_changed:
            self._on_module_changed(previous, new_module)
        self._workspaces[new_module].ensure_layout_visible()

    def _emit_layout_changed(self) -> None:
        if self._on_layout_changed:
            self._on_layout_changed()


ModuleDockManager = ModuleTabManager
