"""Orquestación CRUD del inventario RF (lista, propiedades, toolbar)."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from PyQt6.QtCore import QObject, pyqtSignal
from gui.message_box_utils import ask_yes_no

from core.inventory_channel import channel_key
from core.inventory_editor import (
    create_equipo,
    delete_equipo,
    duplicate_equipo,
    update_equipo,
)
from core.inventory_exceptions import InventoryLockedError
from core.inventory_group_ops import delete_group_channels, duplicate_group_channels
from core.inventory_metadata import (
    get_group_metadata,
    get_list_metadata,
    is_equipo_locked,
    is_group_locked,
    is_inherited_equipo_lock,
    is_list_locked,
    update_group_metadata,
    update_list_metadata,
)
from core.inventory_selection import (
    FOCUS_CHANNEL,
    FOCUS_GROUP,
    FOCUS_LIST,
    focus_kind,
)
from i18n.json_translation import tr


class InventoryEditController(QObject):
    """Gestión del inventario vía barra de herramientas, lista y propiedades."""

    focus_changed = pyqtSignal(object)
    dirty_changed = pyqtSignal(bool)

    def __init__(
        self,
        *,
        parent: Optional[QWidget] = None,
        get_project_manager: Callable[[], Any],
        resolve_equipo: Callable[[Optional[Dict[str, Any]]], Optional[Dict[str, Any]]],
        get_list_panel: Callable[[], Any],
        get_properties_panel: Callable[[], Any],
        get_actions_panel: Callable[[], Any],
        refresh_inventory: Callable[[], None],
        mark_dirty: Callable[[], None],
        focus_properties_panel: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._get_project_manager = get_project_manager
        self._resolve_equipo = resolve_equipo
        self._get_list_panel = get_list_panel
        self._get_properties_panel = get_properties_panel
        self._get_actions_panel = get_actions_panel
        self._refresh_inventory = refresh_inventory
        self._mark_dirty = mark_dirty
        self._focus_properties_panel = focus_properties_panel

        self._focus: Optional[Dict[str, Any]] = None
        self._properties_dirty = False
        self._attached = False

    @property
    def focus(self) -> Optional[Dict[str, Any]]:
        return self._focus

    @property
    def selected_key(self) -> Optional[str]:
        if focus_kind(self._focus) != FOCUS_CHANNEL or not self._focus:
            return None
        return str(self._focus.get("channel_key") or "")

    @property
    def properties_dirty(self) -> bool:
        return self._properties_dirty

    def attach(self) -> None:
        if self._attached:
            return
        lista = self._get_list_panel()
        propiedades = self._get_properties_panel()
        acciones = self._get_actions_panel()
        if not lista or not propiedades or not acciones:
            return

        lista.focus_changed.connect(self._on_focus_changed)
        lista.new_requested.connect(self.create_new)
        lista.edit_requested.connect(self._edit_focus)
        lista.duplicate_requested.connect(self.duplicate_focus)
        lista.delete_requested.connect(self.delete_focus)
        lista.cell_edited.connect(self._on_inline_edit)

        propiedades.dirty_changed.connect(self._on_properties_dirty)
        propiedades.apply_requested.connect(self.apply_properties)
        propiedades.revert_requested.connect(self.revert_properties)
        propiedades.duplicate_requested.connect(self.duplicate_focus)
        propiedades.delete_requested.connect(self.delete_focus)
        propiedades.focus_context_changed.connect(lambda _f: self._update_toolbar_states())
        propiedades.locked_edit_blocked.connect(self._on_locked_edit_blocked)

        lista._table.locked_edit_blocked.connect(self._on_locked_edit_blocked)

        self._attached = True
        self._update_toolbar_states()

    def configure_list_panel(self) -> None:
        lista = self._get_list_panel()
        if not lista:
            return
        lista.set_get_project(lambda: self._project())
        lista._table.set_locked_checker(self._is_channel_locked)
        lista._table.set_action_guards(
            can_duplicate=self.can_duplicate,
            can_delete=self.can_delete,
        )

    def _project(self):
        pm = self._get_project_manager()
        return pm.project if pm and pm.has_open_project else None

    def _project_open(self) -> bool:
        pm = self._get_project_manager()
        return bool(pm and pm.has_open_project)

    def _is_channel_locked(self, item: Dict[str, Any]) -> bool:
        project = self._project()
        if not project:
            return False
        return is_equipo_locked(project, item)

    def _enrich_focus(self, focus: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not focus:
            return None
        kind = focus_kind(focus)
        project = self._project()
        if not project:
            return dict(focus)
        if kind == FOCUS_LIST:
            return {**focus, "meta": get_list_metadata(project)}
        if kind == FOCUS_GROUP:
            mode = str(focus.get("group_mode") or "")
            gkey = str(focus.get("group_key") or "")
            return {**focus, "meta": get_group_metadata(project, mode, gkey)}
        if kind == FOCUS_CHANNEL:
            item = focus.get("item")
            if isinstance(item, dict):
                resolved = self._resolve_equipo(item)
                payload = resolved or item
                return {
                    **focus,
                    "item": payload,
                    "channel_key": channel_key(payload or item),
                    "effective_locked": is_equipo_locked(project, payload or item),
                    "inherited_lock": is_inherited_equipo_lock(project, payload or item),
                }
        return dict(focus)

    def _on_focus_changed(self, focus: Optional[Dict[str, Any]]) -> None:
        enriched = self._enrich_focus(focus)
        self._focus = enriched
        propiedades = self._get_properties_panel()
        acciones = self._get_actions_panel()
        propiedades.load_focus(enriched)
        acciones.set_focus(enriched)
        self.focus_changed.emit(enriched)
        self._update_toolbar_states()

    def _on_properties_dirty(self, dirty: bool) -> None:
        self._properties_dirty = dirty
        self.dirty_changed.emit(dirty)
        self._update_toolbar_states()

    def _on_locked_edit_blocked(self) -> None:
        window = self.parent()
        if window is not None and hasattr(window, "get_status_bar"):
            window.get_status_bar().showMessage(tr("inventory_locked_edit_blocked"), 5000)

    def _update_toolbar_states(self) -> None:
        pass

    def can_create(self) -> bool:
        if not self._project_open():
            return False
        project = self._project()
        return project is not None and not is_list_locked(project)

    def can_edit(self) -> bool:
        if not self._project_open():
            return False
        return focus_kind(self._focus) in (FOCUS_CHANNEL, FOCUS_GROUP, FOCUS_LIST)

    def can_duplicate(self, focus: Optional[Dict[str, Any]] = None) -> bool:
        target = focus or self._focus
        kind = focus_kind(target)
        project = self._project()
        if not project or not target:
            return False
        if kind == FOCUS_CHANNEL:
            item = target.get("item") or {}
            return isinstance(item, dict) and not is_equipo_locked(project, item)
        if kind == FOCUS_GROUP:
            mode = str(target.get("group_mode") or "")
            gkey = str(target.get("group_key") or "")
            return not is_group_locked(project, mode, gkey)
        return False

    def can_delete(self, focus: Optional[Dict[str, Any]] = None) -> bool:
        return self.can_duplicate(focus)

    def can_apply(self) -> bool:
        if not self.can_edit() or not self._properties_dirty:
            return False
        propiedades = self._get_properties_panel()
        if propiedades and hasattr(propiedades, "can_apply_changes"):
            return propiedades.can_apply_changes()
        kind = focus_kind(self._focus)
        if kind == FOCUS_LIST:
            return True
        if kind == FOCUS_GROUP and self._focus:
            project = self._project()
            if not project:
                return False
            mode = str(self._focus.get("group_mode") or "")
            gkey = str(self._focus.get("group_key") or "")
            return not is_group_locked(project, mode, gkey)
        if kind == FOCUS_CHANNEL and self._focus:
            item = self._focus.get("item") or {}
            project = self._project()
            return bool(project and isinstance(item, dict) and not is_equipo_locked(project, item))
        return False

    def can_revert(self) -> bool:
        return self._properties_dirty and self.can_edit()

    def _edit_focus(self, focus: Optional[Dict[str, Any]] = None) -> None:
        if focus:
            self._on_focus_changed(focus)
        if not self.can_edit():
            return
        self._focus_properties_panel()

    def create_new(self) -> None:
        if not self.can_create():
            return
        pm = self._get_project_manager()
        try:
            item = create_equipo(pm.project)
        except InventoryLockedError:
            return
        self._mark_dirty()
        self._refresh_inventory()
        self._select_key(channel_key(item))

    def duplicate_focus(self, focus: Optional[Dict[str, Any]] = None) -> None:
        if focus:
            self._on_focus_changed(focus)
        if not self.can_duplicate():
            return
        pm = self._get_project_manager()
        kind = focus_kind(self._focus)
        try:
            if kind == FOCUS_CHANNEL and self._focus:
                key = str(self._focus.get("channel_key") or "")
                item = duplicate_equipo(pm.project, key)
                if item:
                    self._mark_dirty()
                    self._refresh_inventory()
                    self._select_key(channel_key(item))
            elif kind == FOCUS_GROUP and self._focus:
                created = duplicate_group_channels(
                    pm.project,
                    group_mode=str(self._focus.get("group_mode") or ""),
                    group_key=str(self._focus.get("group_key") or ""),
                    items=list(self._focus.get("items") or []),
                )
                if created:
                    self._mark_dirty()
                    self._refresh_inventory()
                    self._select_key(channel_key(created[-1]))
        except InventoryLockedError:
            return

    def delete_focus(self, focus: Optional[Dict[str, Any]] = None) -> None:
        if focus:
            self._on_focus_changed(focus)
        if not self.can_delete():
            return
        pm = self._get_project_manager()
        kind = focus_kind(self._focus)
        if kind == FOCUS_CHANNEL and self._focus:
            item = self._focus.get("item") or {}
            name = str(item.get("channel_name") or item.get("channel_number") or "—")
            message = tr("inventory_delete_confirm", name=name)
        elif kind == FOCUS_GROUP and self._focus:
            count = len(self._focus.get("items") or [])
            label = str(self._focus.get("label") or "—")
            message = tr("inventory_delete_group_confirm", label=label, count=count)
        else:
            return
        if not ask_yes_no(
            self.parent() or None,
            tr("inventory_delete_title"),
            message,
        ):
            return
        try:
            if kind == FOCUS_CHANNEL and self._focus:
                delete_equipo(pm.project, str(self._focus.get("channel_key") or ""))
            elif kind == FOCUS_GROUP and self._focus:
                delete_group_channels(
                    pm.project,
                    group_mode=str(self._focus.get("group_mode") or ""),
                    group_key=str(self._focus.get("group_key") or ""),
                    items=list(self._focus.get("items") or []),
                )
        except InventoryLockedError:
            return
        self._focus = None
        self._mark_dirty()
        self._refresh_inventory()

    def apply_properties(self) -> None:
        propiedades = self._get_properties_panel()
        if not propiedades or not propiedades.can_apply_changes() or not self._focus:
            return
        pm = self._get_project_manager()
        if not pm or not pm.project:
            return
        updates = propiedades.collect_updates()
        kind = focus_kind(self._focus)
        try:
            if kind == FOCUS_LIST:
                update_list_metadata(pm.project, updates)
            elif kind == FOCUS_GROUP:
                update_group_metadata(
                    pm.project,
                    str(self._focus.get("group_mode") or ""),
                    str(self._focus.get("group_key") or ""),
                    updates,
                )
            elif kind == FOCUS_CHANNEL:
                key = str(self._focus.get("channel_key") or "")
                updated = update_equipo(pm.project, key, updates)
                new_key = channel_key(updated)
                self._focus = {**self._focus, "channel_key": new_key, "item": updated}
        except (KeyError, InventoryLockedError):
            self._refresh_inventory()
            return
        self._mark_dirty()
        self._refresh_inventory()
        if kind == FOCUS_CHANNEL:
            self._select_key(self.selected_key)
        else:
            self._on_focus_changed(self._focus)
        propiedades.mark_clean()

    def revert_properties(self) -> None:
        self._get_properties_panel().revert_changes()

    def _on_inline_edit(self, key: str, field: str, value: Any) -> None:
        pm = self._get_project_manager()
        if not pm or not pm.has_open_project:
            return
        try:
            update_equipo(pm.project, key, {field: value})
        except InventoryLockedError:
            self._refresh_inventory()
            return
        self._mark_dirty()
        self._refresh_inventory()
        self._select_key(key)

    def _select_key(self, key: Optional[str]) -> None:
        lista = self._get_list_panel()
        if not lista:
            return
        if key:
            lista.select_channel_key(key)
        else:
            lista.clear_selection()
