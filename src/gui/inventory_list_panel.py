"""Panel Lista de equipos RF (Inventario) con agrupación estilo Workbench."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QMenu, QVBoxLayout, QWidget

from core.inventory_catalog import GROUP_MODES, GROUP_NONE, build_inventory_groups, filter_equipos
from core.inventory_metadata import DEFAULT_METADATA, get_group_metadata, get_list_metadata
from core.inventory_selection import FOCUS_LIST, list_focus
from gui.inventory_channel_table import InventoryChannelTable
from gui.panel_styles import apply_panel_style, get_panel_colors
from i18n.json_translation import tr


class InventoryListPanel(QWidget):
    """Lista de canales RF: tabla plana por defecto; secciones al agrupar."""

    selection_changed = pyqtSignal(object)
    focus_changed = pyqtSignal(object)
    new_requested = pyqtSignal()
    edit_requested = pyqtSignal(object)
    duplicate_requested = pyqtSignal(object)
    delete_requested = pyqtSignal(object)
    cell_edited = pyqtSignal(str, str, object)

    def __init__(
        self,
        module_id: str,
        panel_id: str,
        parent: Optional[QWidget] = None,
        *,
        on_state_changed: Optional[Callable[[], None]] = None,
        is_locked: Optional[Callable[[Dict[str, Any]], bool]] = None,
        get_project: Optional[Callable[[], Any]] = None,
    ) -> None:
        super().__init__(parent)
        self._module_id = module_id
        self._panel_id = panel_id
        self._style_key = f"{module_id}_{panel_id}"
        self._on_state_changed = on_state_changed
        self._is_locked = is_locked
        self._get_project = get_project

        self._equipos: List[Dict[str, Any]] = []
        self._group_mode = GROUP_NONE
        self._search_text = ""
        self._header_state: Optional[str] = None
        self._pending_header_state: Optional[str] = None
        self._pending_text_alignment: Optional[str] = None
        self._pending_group_mode: Optional[str] = None
        self._pending_search_text: Optional[str] = None

        self._summary = QLabel()
        self._group_label = QLabel(tr("inventory_group_by"))
        self._group_combo = QComboBox()
        self._search = QLineEdit()
        self._search.setClearButtonEnabled(True)
        self._search.setPlaceholderText(tr("inventory_search_placeholder"))

        for mode in GROUP_MODES:
            self._group_combo.addItem(tr(_group_i18n_key(mode)), mode)
        self._group_combo.currentIndexChanged.connect(self._on_group_changed)
        self._search.textChanged.connect(self._on_search_changed)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        toolbar.addWidget(self._group_label)
        toolbar.addWidget(self._group_combo)
        toolbar.addWidget(self._search, stretch=1)

        self._table = InventoryChannelTable(
            on_header_changed=self._on_table_header_changed,
            is_locked=is_locked,
        )
        self._table.focus_changed.connect(self._on_table_focus)
        self._table.edit_requested.connect(self.edit_requested.emit)
        self._table.duplicate_requested.connect(self.duplicate_requested.emit)
        self._table.delete_requested.connect(self.delete_requested.emit)
        self._table.cell_edited.connect(self.cell_edited.emit)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addLayout(toolbar)
        layout.addWidget(self._summary)
        layout.addWidget(self._table, stretch=1)

        self.set_equipos([])
        self.recargar_textos()
        self.apply_visual_theme()

    def set_get_project(self, callback: Optional[Callable[[], Any]]) -> None:
        self._get_project = callback

    def set_on_state_changed(self, callback: Optional[Callable[[], None]]) -> None:
        self._on_state_changed = callback

    def _emit_state_changed(self) -> None:
        if self._on_state_changed:
            self._on_state_changed()

    def save_content_state(self) -> Dict[str, Any]:
        self._header_state = self._table.save_header_state()
        return {
            "table_header": self._header_state,
            "table_text_alignment": self._table.get_text_alignment(),
            "group_by": self._group_mode,
            "search_text": self._search_text,
        }

    def restore_content_state(self, state: Optional[Dict[str, Any]]) -> None:
        if not state:
            return
        header_state = state.get("table_header")
        if isinstance(header_state, str) and header_state:
            self._pending_header_state = header_state

        text_alignment = state.get("table_text_alignment")
        if isinstance(text_alignment, str):
            self._pending_text_alignment = text_alignment

        group_by = state.get("group_by")
        if isinstance(group_by, str) and group_by in GROUP_MODES:
            self._pending_group_mode = group_by

        search_text = state.get("search_text")
        if isinstance(search_text, str):
            self._pending_search_text = search_text

        self._apply_pending_ui_state()
        self._rebuild_view()

    def _apply_pending_ui_state(self) -> None:
        if self._pending_group_mode:
            index = self._group_combo.findData(self._pending_group_mode)
            if index >= 0:
                self._group_combo.blockSignals(True)
                self._group_combo.setCurrentIndex(index)
                self._group_combo.blockSignals(False)
                self._group_mode = self._pending_group_mode
            self._pending_group_mode = None

        if self._pending_search_text is not None:
            self._search.blockSignals(True)
            self._search.setText(self._pending_search_text)
            self._search.blockSignals(False)
            self._search_text = self._pending_search_text
            self._pending_search_text = None

    def set_equipos(
        self,
        equipos: List[Dict[str, Any]],
        *,
        preserve_selection_key: Optional[str] = None,
    ) -> None:
        self._equipos = list(equipos)
        self._rebuild_view(preserve_selection_key=preserve_selection_key)

    def select_channel_key(self, key: str) -> bool:
        return self._table.select_by_channel_key(key)

    def clear_selection(self) -> None:
        self._table.clear_selection()
        self._emit_list_focus()

    def _emit_list_focus(self) -> None:
        focus = list_focus()
        self.focus_changed.emit(focus)
        self.selection_changed.emit(None)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        if not self._table.get_current_focus():
            self._emit_list_focus()

    def _on_table_focus(self, focus: Optional[Dict[str, Any]]) -> None:
        if focus:
            self.focus_changed.emit(focus)
            if focus.get("kind") == "channel":
                self.selection_changed.emit(focus.get("item"))
            else:
                self.selection_changed.emit(None)
        else:
            self._emit_list_focus()

    def _on_group_changed(self, index: int) -> None:
        mode = self._group_combo.itemData(index)
        if not isinstance(mode, str):
            return
        self._group_mode = mode
        self._rebuild_view()
        self._emit_state_changed()

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text
        self._rebuild_view()
        self._emit_state_changed()

    def _apply_header_state(self) -> None:
        header_state = self._pending_header_state or self._header_state
        if header_state:
            self._table.apply_header_state(header_state)
            if self._pending_header_state:
                self._header_state = header_state
                self._pending_header_state = None
        if self._pending_text_alignment:
            self._table.set_text_alignment(self._pending_text_alignment, notify=False)
            self._pending_text_alignment = None

    def _rebuild_view(self, *, preserve_selection_key: Optional[str] = None) -> None:
        if not preserve_selection_key:
            self._table.clear_selection()
            self._emit_list_focus()

        filtered = filter_equipos(self._equipos, self._search_text)
        self._apply_header_state()

        if self._group_mode == GROUP_NONE:
            self._table.set_flat_equipos(filtered)
        else:
            groups = build_inventory_groups(filtered, group_mode=self._group_mode, tr=tr)
            project = self._get_project() if self._get_project else None
            grouped = []
            for gkey, label, items in groups:
                if not items:
                    continue
                meta = (
                    get_group_metadata(project, self._group_mode, gkey)
                    if project
                    else dict(DEFAULT_METADATA)
                )
                grouped.append((gkey, label, items, meta))
            self._table.set_grouped_equipos(grouped, group_mode=self._group_mode)

        if preserve_selection_key:
            if not self._table.select_by_channel_key(preserve_selection_key):
                self._emit_list_focus()

        visible_count = len(filtered)
        total = len(self._equipos)
        if self._search_text.strip():
            self._summary.setText(
                tr("inventory_summary_filtered", visible=visible_count, total=total)
            )
        else:
            self._summary.setText(tr("inventory_summary", count=visible_count))

    def _on_table_header_changed(self) -> None:
        if not getattr(self, "_table", None):
            return
        self._header_state = self._table.save_header_state()
        self._emit_state_changed()

    def _show_context_menu(self, pos) -> None:
        focus = self._table.get_current_focus()
        menu = QMenu(self)
        new_action = menu.addAction(tr("inventory_action_new"))
        new_action.triggered.connect(self.new_requested.emit)
        if focus and focus.get("kind") != "list":
            menu.addSeparator()
            edit_action = menu.addAction(tr("inventory_action_edit"))
            edit_action.triggered.connect(lambda: self.edit_requested.emit(focus))
            if self._table._can_duplicate(focus):
                dup_action = menu.addAction(tr("inventory_action_duplicate"))
                dup_action.triggered.connect(lambda: self.duplicate_requested.emit(focus))
            if self._table._can_delete(focus):
                menu.addSeparator()
                del_action = menu.addAction(tr("inventory_action_delete"))
                del_action.triggered.connect(lambda: self.delete_requested.emit(focus))
        menu.exec(self.mapToGlobal(pos))

    def show_columns_dialog(self, parent=None) -> None:
        self._table.show_columns_dialog(parent)

    def apply_visual_theme(self, panel_id: str | None = None) -> None:
        key = panel_id or self._style_key
        apply_panel_style(self, key)
        colors = get_panel_colors(key)
        self._summary.setStyleSheet(f"color: {colors['text_muted']}; font-size: 11px;")
        self._group_label.setStyleSheet(f"color: {colors['text_muted']};")
        strip = get_panel_colors(f"{self._module_id}_propiedades")
        self._table.set_group_header_colors(strip["bg"], strip["fg"], strip["border"])
        if self._equipos or self._group_mode != GROUP_NONE:
            self._rebuild_view()

    def recargar_textos(self) -> None:
        saved_group = self._group_mode
        saved_search = self._search_text

        self._group_label.setText(tr("inventory_group_by"))
        self._search.setPlaceholderText(tr("inventory_search_placeholder"))

        self._group_combo.blockSignals(True)
        self._group_combo.clear()
        for mode in GROUP_MODES:
            self._group_combo.addItem(tr(_group_i18n_key(mode)), mode)
        index = self._group_combo.findData(saved_group)
        self._group_combo.setCurrentIndex(index if index >= 0 else 0)
        self._group_combo.blockSignals(False)
        self._group_mode = self._group_combo.currentData() or GROUP_NONE

        self._search.blockSignals(True)
        self._search.setText(saved_search)
        self._search.blockSignals(False)

        self._table.recargar_textos()
        self._rebuild_view()


def _group_i18n_key(mode: str) -> str:
    from core.inventory_catalog import _GROUP_I18N

    return _GROUP_I18N.get(mode, "inventory_group_none")
