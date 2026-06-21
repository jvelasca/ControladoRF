"""Tabla de canales RF con cabecera configurable (plana o agrupada)."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import Qt, QPoint, QEvent, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QKeyEvent
from PyQt6.QtWidgets import QHeaderView, QMenu, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from core.inventory_channel import channel_key
from core.inventory_selection import FOCUS_CHANNEL, FOCUS_GROUP, channel_focus, group_focus
from gui.color_picker_utils import parse_color
from gui.configurable_table_header import (
    restore_header_state,
    save_header_state,
    setup_resizable_header,
)
from gui.inventory_color_delegate import COLOR_SWATCH_ROLE, InventoryColorDelegate
from gui.inventory_lock_delegate import LOCK_STATE_ROLE, InventoryLockDelegate
from gui.inventory_table_alignment import (
    DEFAULT_TABLE_ALIGNMENT,
    normalize_table_alignment,
    table_alignment_to_qt,
)
from i18n.json_translation import tr

ROW_DATA_ROLE = int(Qt.ItemDataRole.UserRole)
ROW_KIND_ROLE = int(Qt.ItemDataRole.UserRole) + 1
ROW_KIND_DATA = "data"
ROW_KIND_GROUP = "group"

# Orden lógico de columnas (visibilidad configurable desde diálogo o barra de herramientas).
COLUMNS: Tuple[str, ...] = (
    "inventory_col_channel",
    "inventory_col_name",
    "inventory_col_model",
    "inventory_col_band",
    "inventory_col_frequency",
    "inventory_col_zone",
    "inventory_col_device",
    "inventory_col_locked",
    "inventory_col_color",
    "inventory_col_notes",
)

# Campo del equipo asociado a cada columna (None = solo visualización).
COLUMN_FIELD: Dict[str, Optional[str]] = {
    "inventory_col_channel": "channel_number",
    "inventory_col_name": "channel_name",
    "inventory_col_model": "model",
    "inventory_col_band": "band",
    "inventory_col_frequency": "frequency_mhz",
    "inventory_col_zone": "zone",
    "inventory_col_device": "device_name",
    "inventory_col_locked": None,
    "inventory_col_color": None,
    "inventory_col_notes": "notes",
}

METADATA_COLUMNS: Tuple[str, ...] = (
    "inventory_col_locked",
    "inventory_col_color",
    "inventory_col_notes",
)

DEFAULT_HIDDEN_COLUMNS: frozenset[str] = frozenset({"inventory_col_notes"})

GROUP_ROW_HEIGHT = 32
GROUP_ROW_HEIGHT_FIRST = 36
NARROW_COLUMN_WIDTH = 36


class InventoryChannelTable(QWidget):
    """Tabla de canales; cabecera configurable, metadatos opcionales, edición inline."""

    focus_changed = pyqtSignal(object)
    cell_edited = pyqtSignal(str, str, object)
    edit_requested = pyqtSignal(object)
    duplicate_requested = pyqtSignal(object)
    delete_requested = pyqtSignal(object)
    locked_edit_blocked = pyqtSignal()

    def __init__(
        self,
        *,
        on_header_changed: Optional[Callable[[], None]] = None,
        is_locked: Optional[Callable[[Dict[str, Any]], bool]] = None,
        can_duplicate: Optional[Callable[[Optional[Dict[str, Any]]], bool]] = None,
        can_delete: Optional[Callable[[Optional[Dict[str, Any]]], bool]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._on_header_changed = on_header_changed
        self._is_locked = is_locked or (lambda _item: False)
        self._can_duplicate = can_duplicate or (lambda _focus: True)
        self._can_delete = can_delete or (lambda _focus: True)
        self._suppress_selection_signal = False
        self._suppress_item_signal = False
        self._group_mode = "none"
        self._group_header_bg = QColor("#ECECEC")
        self._group_header_fg = QColor("#1E1E1E")
        self._group_header_accent = QColor("#CCCEDB")
        self._text_alignment = DEFAULT_TABLE_ALIGNMENT

        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
            | QTableWidget.EditTrigger.AnyKeyPressed
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(False)
        self._table.setShowGrid(True)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.cellDoubleClicked.connect(self._on_double_click)
        self._table.cellClicked.connect(self._on_cell_clicked)

        self._color_delegate = InventoryColorDelegate(self._table)
        self._lock_delegate = InventoryLockDelegate(self._table)

        header = self._table.horizontalHeader()
        setup_resizable_header(header, len(COLUMNS), on_changed=self._emit_header_changed)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_header_context_menu)
        header.blockSignals(True)
        self._apply_headers()
        self._apply_default_column_layout()
        header.blockSignals(False)
        self._table.setItemDelegateForColumn(
            self._col_index("inventory_col_color"), self._color_delegate
        )
        self._table.setItemDelegateForColumn(
            self._col_index("inventory_col_locked"), self._lock_delegate
        )
        self._table.viewport().installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table)

    def set_locked_checker(self, checker: Callable[[Dict[str, Any]], bool]) -> None:
        self._is_locked = checker

    def set_action_guards(
        self,
        *,
        can_duplicate: Callable[[Optional[Dict[str, Any]]], bool],
        can_delete: Callable[[Optional[Dict[str, Any]]], bool],
    ) -> None:
        self._can_duplicate = can_duplicate
        self._can_delete = can_delete

    def set_group_mode(self, group_mode: str) -> None:
        self._group_mode = group_mode

    def _col_index(self, key: str) -> int:
        return COLUMNS.index(key)

    def _metadata_start_index(self) -> int:
        return self._col_index(METADATA_COLUMNS[0])

    def _emit_header_changed(self) -> None:
        if self._on_header_changed:
            self._on_header_changed()

    def get_text_alignment(self) -> str:
        return self._text_alignment

    def set_text_alignment(self, mode: str, *, notify: bool = True) -> None:
        self._text_alignment = normalize_table_alignment(mode)
        header = self._table.horizontalHeader()
        header.setDefaultAlignment(table_alignment_to_qt(self._text_alignment))
        self._style_metadata_header_items()
        self._reapply_cell_alignments()
        if notify:
            self._emit_header_changed()

    def reset_text_alignment(self, *, notify: bool = True) -> None:
        self.set_text_alignment(DEFAULT_TABLE_ALIGNMENT, notify=notify)

    def _cell_alignment(self) -> Qt.AlignmentFlag:
        return table_alignment_to_qt(self._text_alignment)

    def _fixed_center_columns(self) -> frozenset[int]:
        return frozenset(
            {
                self._col_index("inventory_col_locked"),
                self._col_index("inventory_col_color"),
            }
        )

    def _style_metadata_header_items(self) -> None:
        center = Qt.AlignmentFlag.AlignCenter
        for key in ("inventory_col_locked", "inventory_col_color"):
            item = self._table.horizontalHeaderItem(self._col_index(key))
            if item is not None:
                item.setTextAlignment(center)

    def _style_cell(self, cell: QTableWidgetItem, *, center: bool = False) -> None:
        if center:
            cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            cell.setTextAlignment(self._cell_alignment())

    def _reapply_cell_alignments(self) -> None:
        align = self._cell_alignment()
        center_cols = self._fixed_center_columns()
        for row in range(self._table.rowCount()):
            for col in range(self._table.columnCount()):
                item = self._table.item(row, col)
                if item is None:
                    continue
                if col in center_cols:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                else:
                    item.setTextAlignment(align)

    def eventFilter(self, watched, event) -> bool:
        if watched is self._table.viewport() and event.type() == QEvent.Type.KeyPress:
            if isinstance(event, QKeyEvent) and self._is_edit_key_on_readonly_cell(event):
                self.locked_edit_blocked.emit()
                return True
        return super().eventFilter(watched, event)

    def _is_edit_key_on_readonly_cell(self, event: QKeyEvent) -> bool:
        item = self._table.currentItem()
        if item is None or (item.flags() & Qt.ItemFlag.ItemIsEditable):
            return False
        if item.data(ROW_KIND_ROLE) != ROW_KIND_DATA:
            return False
        payload = item.data(ROW_DATA_ROLE)
        if not isinstance(payload, dict) or not self._is_locked(payload):
            return False
        if event.key() == Qt.Key.Key_F2:
            return True
        text = event.text()
        return bool(text and text.isprintable() and not event.modifiers() & Qt.KeyboardModifier.ControlModifier)

    def _apply_headers(self) -> None:
        for index, key in enumerate(COLUMNS):
            self._table.setHorizontalHeaderItem(index, QTableWidgetItem(tr(key)))
        header = self._table.horizontalHeader()
        header.setDefaultAlignment(self._cell_alignment())
        self._style_metadata_header_items()
        header.setStretchLastSection(True)
        for key in METADATA_COLUMNS:
            idx = self._col_index(key)
            header.setSectionResizeMode(idx, QHeaderView.ResizeMode.Fixed)
            width = 120 if key == "inventory_col_notes" else NARROW_COLUMN_WIDTH
            header.resizeSection(idx, width)

    def _apply_default_column_layout(self) -> None:
        header = self._table.horizontalHeader()
        for key in DEFAULT_HIDDEN_COLUMNS:
            header.setSectionHidden(self._col_index(key), True)

    def set_group_header_colors(self, bg: str, fg: str, accent: str = "") -> None:
        self._group_header_bg = QColor(bg)
        self._group_header_fg = QColor(fg)
        if accent:
            self._group_header_accent = QColor(accent)

    def set_flat_equipos(self, equipos: List[Dict[str, Any]]) -> None:
        self._group_mode = "none"
        self._populate_rows(flat=equipos, grouped=[])

    def set_grouped_equipos(
        self,
        groups: Sequence[Tuple[str, str, List[Dict[str, Any]], Dict[str, Any]]],
        *,
        group_mode: str,
    ) -> None:
        self._group_mode = group_mode
        self._populate_rows(flat=[], grouped=list(groups))

    def _populate_rows(
        self,
        *,
        flat: List[Dict[str, Any]],
        grouped: List[Tuple[str, str, List[Dict[str, Any]], Dict[str, Any]]],
    ) -> None:
        self._suppress_item_signal = True
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        if grouped:
            self._table.setAlternatingRowColors(False)
            row = 0
            first_group = True
            for group_key, label, items, meta in grouped:
                if not items:
                    continue
                self._table.insertRow(row)
                self._fill_group_row(
                    row,
                    label,
                    len(items),
                    group_mode=self._group_mode,
                    group_key=group_key,
                    meta=meta,
                    first_group=first_group,
                )
                first_group = False
                row += 1
                for item in items:
                    self._table.insertRow(row)
                    self._fill_data_row(row, item)
                    row += 1
        else:
            self._table.setAlternatingRowColors(True)
            for row, item in enumerate(flat):
                self._table.insertRow(row)
                self._fill_data_row(row, item)
        self._suppress_item_signal = False

    def _fill_group_row(
        self,
        row: int,
        label: str,
        count: int,
        *,
        group_mode: str,
        group_key: str,
        meta: Dict[str, Any],
        first_group: bool,
    ) -> None:
        title = tr("inventory_group_header", label=label, count=count)
        payload = {
            "group_mode": group_mode,
            "group_key": group_key,
            "label": label,
            "items": [],
            "meta": dict(meta),
        }
        meta_start = self._metadata_start_index()
        title_cell = QTableWidgetItem(f"  {title}")
        title_cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        title_cell.setData(ROW_DATA_ROLE, payload)
        title_cell.setData(ROW_KIND_ROLE, ROW_KIND_GROUP)
        bg = parse_color(str(meta.get("color") or "")) or self._group_header_bg
        fg = self._group_header_fg
        title_cell.setBackground(QBrush(bg))
        title_cell.setForeground(QBrush(fg))
        font = title_cell.font()
        font.setBold(True)
        title_cell.setFont(font)
        self._style_cell(title_cell)
        self._table.setItem(row, 0, title_cell)
        if meta_start > 1:
            self._table.setSpan(row, 0, 1, meta_start)
        for col in range(1, meta_start):
            filler = QTableWidgetItem()
            filler.setFlags(Qt.ItemFlag.ItemIsSelectable)
            filler.setData(ROW_DATA_ROLE, payload)
            filler.setData(ROW_KIND_ROLE, ROW_KIND_GROUP)
            filler.setBackground(QBrush(bg))
            self._table.setItem(row, col, filler)
        self._set_lock_cell(
            row,
            self._col_index("inventory_col_locked"),
            bool(meta.get("locked")),
            payload,
            ROW_KIND_GROUP,
        )
        self._set_color_cell(
            row,
            self._col_index("inventory_col_color"),
            str(meta.get("color") or ""),
            payload,
            ROW_KIND_GROUP,
        )
        notes_cell = QTableWidgetItem(str(meta.get("notes") or ""))
        notes_cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        notes_cell.setData(ROW_DATA_ROLE, payload)
        notes_cell.setData(ROW_KIND_ROLE, ROW_KIND_GROUP)
        self._style_cell(notes_cell)
        self._table.setItem(row, self._col_index("inventory_col_notes"), notes_cell)
        height = GROUP_ROW_HEIGHT_FIRST if first_group else GROUP_ROW_HEIGHT
        self._table.setRowHeight(row, height)

    def _fill_data_row(self, row: int, item: Dict[str, Any]) -> None:
        locked = self._is_locked(item)
        read_only = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        editable = read_only | Qt.ItemFlag.ItemIsEditable

        for col, col_key in enumerate(COLUMNS):
            field = COLUMN_FIELD.get(col_key)
            cell = QTableWidgetItem()
            cell.setData(ROW_DATA_ROLE, item)
            cell.setData(ROW_KIND_ROLE, ROW_KIND_DATA)

            if col_key == "inventory_col_locked":
                self._set_lock_cell(
                    row,
                    col,
                    locked or bool(item.get("locked")),
                    item,
                    ROW_KIND_DATA,
                )
                continue
            if col_key == "inventory_col_color":
                self._set_color_cell(
                    row,
                    col,
                    str(item.get("color") or ""),
                    item,
                    ROW_KIND_DATA,
                )
                continue

            value = _format_cell_value(col_key, field, item)
            cell.setText(value)
            self._style_cell(cell)
            if field and not locked:
                cell.setFlags(editable)
            else:
                cell.setFlags(read_only)
            self._table.setItem(row, col, cell)

    def _set_lock_cell(
        self,
        row: int,
        col: int,
        locked: bool,
        payload: Any,
        kind: str,
    ) -> None:
        cell = QTableWidgetItem()
        cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self._style_cell(cell, center=True)
        cell.setData(ROW_DATA_ROLE, payload)
        cell.setData(ROW_KIND_ROLE, kind)
        cell.setData(LOCK_STATE_ROLE, bool(locked))
        self._table.setItem(row, col, cell)

    def _set_color_cell(
        self,
        row: int,
        col: int,
        color_value: str,
        payload: Any,
        kind: str,
    ) -> None:
        cell = QTableWidgetItem()
        cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self._style_cell(cell, center=True)
        cell.setData(ROW_DATA_ROLE, payload)
        cell.setData(ROW_KIND_ROLE, kind)
        normalized = str(color_value or "").strip()
        if normalized and parse_color(normalized):
            cell.setData(COLOR_SWATCH_ROLE, normalized)
        self._table.setItem(row, col, cell)

    def resize_columns_to_contents(self) -> None:
        header = self._table.horizontalHeader()
        for col in range(self._table.columnCount()):
            if header.isSectionHidden(col):
                continue
            self._table.resizeColumnToContents(col)
        for key in METADATA_COLUMNS:
            idx = self._col_index(key)
            if header.isSectionHidden(idx):
                continue
            minimum = 120 if key == "inventory_col_notes" else NARROW_COLUMN_WIDTH
            if header.sectionSize(idx) < minimum:
                header.resizeSection(idx, minimum)
        self._emit_header_changed()

    def clear_selection(self) -> None:
        self._suppress_selection_signal = True
        self._table.clearSelection()
        self._suppress_selection_signal = False

    def select_by_channel_key(self, key: str) -> bool:
        if not key:
            return False
        self._suppress_selection_signal = True
        self._table.clearSelection()
        found = False
        for row in range(self._table.rowCount()):
            cell = self._table.item(row, 0)
            if cell is None or cell.data(ROW_KIND_ROLE) != ROW_KIND_DATA:
                continue
            item = cell.data(ROW_DATA_ROLE)
            if isinstance(item, dict) and channel_key(item) == key:
                self._table.selectRow(row)
                found = True
                break
        self._suppress_selection_signal = False
        if found:
            self._on_selection_changed()
        return found

    def get_current_focus(self) -> Optional[Dict[str, Any]]:
        selected = self._table.selectedItems()
        if not selected:
            return None
        first = selected[0]
        kind = first.data(ROW_KIND_ROLE)
        data = first.data(ROW_DATA_ROLE)
        if kind == ROW_KIND_GROUP and isinstance(data, dict):
            return group_focus(
                group_mode=str(data.get("group_mode") or self._group_mode),
                group_key=str(data.get("group_key") or ""),
                label=str(data.get("label") or ""),
                items=self._group_items_for_row(first.row()),
            )
        if kind == ROW_KIND_DATA and isinstance(data, dict):
            item = dict(data)
            return channel_focus(item, channel_key_value=channel_key(item))
        return None

    def _group_items_for_row(self, group_row: int) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        row = group_row + 1
        while row < self._table.rowCount():
            cell = self._table.item(row, 0)
            if cell is None:
                break
            if cell.data(ROW_KIND_ROLE) == ROW_KIND_GROUP:
                break
            if cell.data(ROW_KIND_ROLE) == ROW_KIND_DATA:
                payload = cell.data(ROW_DATA_ROLE)
                if isinstance(payload, dict):
                    items.append(dict(payload))
            row += 1
        return items

    def save_header_state(self) -> str:
        return save_header_state(self._table.horizontalHeader())

    def apply_header_state(self, state_b64: str) -> None:
        if state_b64:
            restore_header_state(self._table.horizontalHeader(), state_b64)
        else:
            self._apply_default_column_layout()

    def show_columns_dialog(self, parent=None) -> None:
        from gui.inventory_table_columns_dialog import InventoryTableColumnsDialog

        dlg = InventoryTableColumnsDialog(
            parent or self.window(),
            self._table.horizontalHeader(),
            COLUMNS,
            on_changed=self._emit_header_changed,
            on_fit_contents=self.resize_columns_to_contents,
            get_column_label=tr,
            get_text_alignment=self.get_text_alignment,
            set_text_alignment=lambda mode: self.set_text_alignment(mode, notify=True),
            reset_text_alignment=lambda: self.reset_text_alignment(notify=True),
        )
        dlg.exec()

    def recargar_textos(self) -> None:
        saved = save_header_state(self._table.horizontalHeader())
        self._apply_headers()
        restore_header_state(self._table.horizontalHeader(), saved)

    def _on_selection_changed(self) -> None:
        if self._suppress_selection_signal:
            return
        self.focus_changed.emit(self.get_current_focus())

    def _on_item_changed(self, cell: QTableWidgetItem) -> None:
        if self._suppress_item_signal:
            return
        if cell.data(ROW_KIND_ROLE) != ROW_KIND_DATA:
            return
        item = cell.data(ROW_DATA_ROLE)
        if not isinstance(item, dict):
            return
        if self._is_locked(item):
            self.locked_edit_blocked.emit()
            return
        col = cell.column()
        if col < 0 or col >= len(COLUMNS):
            return
        col_key = COLUMNS[col]
        field = COLUMN_FIELD.get(col_key)
        if not field:
            return
        parsed = _parse_inline_value(field, cell.text())
        self.cell_edited.emit(channel_key(item), field, parsed)

    def _show_header_context_menu(self, pos: QPoint) -> None:
        header = self._table.horizontalHeader()
        menu = QMenu(self)
        columns_action = menu.addAction(tr("inventory_table_columns_menu"))
        columns_action.triggered.connect(lambda: self.show_columns_dialog(self.window()))
        menu.exec(header.mapToGlobal(pos))

    def _show_context_menu(self, pos: QPoint) -> None:
        item = self._table.itemAt(pos)
        if item is None:
            return
        self._table.selectRow(item.row())
        focus = self.get_current_focus()
        if not focus:
            return
        menu = QMenu(self)
        edit_action = menu.addAction(tr("inventory_action_edit"))
        edit_action.triggered.connect(lambda: self.edit_requested.emit(focus))
        if self._can_duplicate(focus):
            dup_action = menu.addAction(tr("inventory_action_duplicate"))
            dup_action.triggered.connect(lambda: self.duplicate_requested.emit(focus))
        if self._can_delete(focus):
            if self._can_duplicate(focus):
                menu.addSeparator()
            del_action = menu.addAction(tr("inventory_action_delete"))
            del_action.triggered.connect(lambda: self.delete_requested.emit(focus))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if col < 0 or col >= len(COLUMNS):
            return
        col_key = COLUMNS[col]
        if col_key not in ("inventory_col_locked", "inventory_col_color"):
            return
        cell = self._table.item(row, col)
        if cell is None:
            return
        self._table.selectRow(row)
        focus = self.get_current_focus()
        if focus:
            self.edit_requested.emit(focus)

    def _on_double_click(self, row: int, col: int) -> None:
        cell = self._table.item(row, 0)
        if cell is None:
            return
        col_key = COLUMNS[col] if 0 <= col < len(COLUMNS) else ""
        if col_key in ("inventory_col_locked", "inventory_col_color"):
            focus = self.get_current_focus()
            if focus:
                self.edit_requested.emit(focus)
            return
        if cell.data(ROW_KIND_ROLE) == ROW_KIND_GROUP:
            focus = self.get_current_focus()
            if focus:
                self.edit_requested.emit(focus)
            return
        if cell.data(ROW_KIND_ROLE) != ROW_KIND_DATA:
            return
        field = COLUMN_FIELD.get(col_key)
        item = cell.data(ROW_DATA_ROLE)
        if not isinstance(item, dict):
            return
        if field and not self._is_locked(item):
            return
        self.edit_requested.emit(
            channel_focus(dict(item), channel_key_value=channel_key(item))
        )


def _format_cell_value(col_key: str, field: Optional[str], item: Dict[str, Any]) -> str:
    if not field:
        return ""
    if field == "channel_number":
        number = item.get("channel_number")
        return "" if number in (None, "") else str(number)
    if field == "frequency_mhz":
        freq = item.get("frequency_mhz")
        return f"{freq:.3f}" if isinstance(freq, (int, float)) else ""
    value = item.get(field)
    return "" if value is None else str(value)


def _parse_inline_value(field: str, text: str) -> Any:
    cleaned = text.strip()
    if field == "channel_number":
        if not cleaned:
            return None
        try:
            return int(cleaned)
        except ValueError:
            return None
    if field == "frequency_mhz":
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return cleaned
