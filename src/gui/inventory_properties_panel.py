"""Panel Propiedades editable del canal RF seleccionado."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.inventory_catalog import DEVICE_TYPE_ORDER, _TYPE_I18N, enrich_equipo_metadata
from core.inventory_editor import EDITABLE_FIELDS
from core.inventory_metadata import DEFAULT_METADATA
from core.inventory_selection import FOCUS_CHANNEL, FOCUS_GROUP, FOCUS_LIST, focus_kind
from gui.color_picker_utils import parse_color, pick_color
from gui.icon_utils import ICON_SIZE_BUTTON, get_app_icon
from gui.panel_styles import apply_panel_style, get_panel_colors
from utils.theme_utils import is_dark_mode
from i18n.json_translation import tr


class InventoryPropertiesPanel(QWidget):
    """Formulario editable con Apply/Revert para el canal seleccionado."""

    dirty_changed = pyqtSignal(bool)
    apply_requested = pyqtSignal()
    revert_requested = pyqtSignal()
    duplicate_requested = pyqtSignal(object)
    delete_requested = pyqtSignal(object)
    focus_context_changed = pyqtSignal(bool)
    locked_edit_blocked = pyqtSignal()

    _METADATA_FIELDS = ("notes", "color", "locked")

    _EDITABLE_SECTIONS: Tuple[Tuple[str, Tuple[Tuple[str, str, str], ...]], ...] = (
        (
            "inventory_prop_section_rf",
            (
                ("inventory_prop_channel", "channel_number", "spin"),
                ("inventory_prop_name", "channel_name", "text"),
                ("inventory_prop_frequency", "frequency_mhz", "frequency"),
                ("inventory_prop_band", "band", "text"),
                ("inventory_prop_zone", "zone", "text"),
                ("inventory_prop_network", "network", "text"),
            ),
        ),
        (
            "inventory_prop_section_device",
            (
                ("inventory_prop_type", "device_type", "type"),
                ("inventory_prop_model", "model", "text"),
                ("inventory_prop_series", "series", "text"),
                ("inventory_prop_manufacturer", "manufacturer", "text"),
                ("inventory_prop_device", "device_name", "text"),
            ),
        ),
        (
            "inventory_prop_section_coord",
            (
                ("inventory_prop_coord_include", "coordination_include", "bool"),
                ("inventory_prop_coord_active", "coordination_active", "bool"),
            ),
        ),
    )

    _READONLY_FIELDS: Tuple[Tuple[str, str], ...] = (
        ("inventory_prop_channel_key", "channel_key"),
        ("inventory_prop_workbench_channel", "workbench_channel_id"),
        ("inventory_prop_workbench_device", "workbench_device_id"),
        ("inventory_prop_source", "source"),
        ("inventory_prop_db_id", "db_id"),
    )

    def __init__(
        self,
        module_id: str,
        panel_id: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._module_id = module_id
        self._panel_id = panel_id
        self._style_key = f"{module_id}_{panel_id}"
        self._loaded: Optional[Dict[str, Any]] = None
        self._focus: Optional[Dict[str, Any]] = None
        self._dirty = False
        self._loading = False
        self._color_value = ""

        self._field_labels: Dict[str, QLabel] = {}
        self._editors: Dict[str, QWidget] = {}
        self._readonly_labels: Dict[str, QLabel] = {}
        self._section_titles: Dict[str, QLabel] = {}
        self._channel_hosts: list[QWidget] = []
        self._ids_host: Optional[QWidget] = None
        self._meta_host: Optional[QWidget] = None
        self._dimmed_hosts: list[QWidget] = []

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._empty_label = QLabel()
        self._empty_label.setWordWrap(True)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._locked_banner = QLabel()
        self._locked_banner.setWordWrap(True)
        self._locked_banner.hide()
        self._locked_banner.setObjectName("InventoryLockedBanner")

        self._title = QLabel()
        self._title.setWordWrap(True)
        self._title.hide()

        self._subtitle = QLabel()
        self._subtitle.setWordWrap(True)
        self._subtitle.hide()

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        content_layout.addWidget(self._title)
        content_layout.addWidget(self._subtitle)

        meta_title = QLabel(tr("inventory_prop_section_meta"))
        self._section_titles["inventory_prop_section_meta"] = meta_title
        content_layout.addWidget(meta_title)
        meta_host = QWidget()
        meta_form = QFormLayout(meta_host)
        meta_form.setContentsMargins(0, 0, 0, 0)
        meta_form.setSpacing(6)
        meta_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        self._notes_edit = QTextEdit()
        self._notes_edit.setMaximumHeight(80)
        self._notes_edit.textChanged.connect(self._on_field_edited)
        self._notes_edit.installEventFilter(self)
        self._field_labels["notes"] = QLabel(tr("inventory_prop_notes"))
        meta_form.addRow(self._field_labels["notes"], self._notes_edit)
        color_row = QHBoxLayout()
        self._color_preview = QLabel()
        self._color_preview.setFixedSize(28, 20)
        self._color_preview.setFrameShape(QFrame.Shape.Box)
        self._btn_color = QPushButton()
        self._btn_color.setIcon(get_app_icon("edit", ICON_SIZE_BUTTON))
        self._btn_color.clicked.connect(self._pick_color)
        color_row.addWidget(self._color_preview)
        color_row.addWidget(self._btn_color)
        color_row.addStretch(1)
        color_widget = QWidget()
        color_widget.setLayout(color_row)
        self._field_labels["color"] = QLabel(tr("inventory_prop_color"))
        meta_form.addRow(self._field_labels["color"], color_widget)
        self._locked_check = QCheckBox()
        self._locked_check.stateChanged.connect(self._on_field_edited)
        self._field_labels["locked"] = QLabel(tr("inventory_prop_locked"))
        meta_form.addRow(self._field_labels["locked"], self._locked_check)
        content_layout.addWidget(meta_host)
        self._meta_host = meta_host
        self._dimmed_hosts.append(meta_host)
        meta_line = QFrame()
        meta_line.setFrameShape(QFrame.Shape.HLine)
        content_layout.addWidget(meta_line)

        for section_key, fields in self._EDITABLE_SECTIONS:
            section_title = QLabel(tr(section_key))
            section_title.hide()
            self._section_titles[section_key] = section_title
            content_layout.addWidget(section_title)

            form_host = QWidget()
            form = QFormLayout(form_host)
            form.setContentsMargins(0, 0, 0, 0)
            form.setSpacing(6)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

            for label_key, field, kind in fields:
                name_label = QLabel(tr(label_key))
                editor = self._create_editor(field, kind)
                editor.installEventFilter(self)
                form.addRow(name_label, editor)
                self._field_labels[field] = name_label
                self._editors[field] = editor

            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Plain)
            line.hide()
            content_layout.addWidget(form_host)
            content_layout.addWidget(line)
            form_host.setProperty("section_divider", line)
            self._channel_hosts.append(form_host)
            self._dimmed_hosts.append(form_host)

        ids_title = QLabel(tr("inventory_prop_section_ids"))
        ids_title.hide()
        self._section_titles["inventory_prop_section_ids"] = ids_title
        content_layout.addWidget(ids_title)

        ids_form_host = QWidget()
        ids_form = QFormLayout(ids_form_host)
        ids_form.setContentsMargins(0, 0, 0, 0)
        ids_form.setSpacing(6)
        ids_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        for label_key, field in self._READONLY_FIELDS:
            name_label = QLabel(tr(label_key))
            value = QLabel("—")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            ids_form.addRow(name_label, value)
            self._field_labels[field] = name_label
            self._readonly_labels[field] = value
        content_layout.addWidget(ids_form_host)
        self._ids_host = ids_form_host
        self._dimmed_hosts.append(ids_form_host)

        content_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        self._scroll = scroll

        self._btn_apply = QPushButton()
        self._btn_apply.setIcon(get_app_icon("activate", ICON_SIZE_BUTTON))
        self._btn_apply.clicked.connect(self.apply_requested.emit)
        self._btn_revert = QPushButton()
        self._btn_revert.setIcon(get_app_icon("refresh", ICON_SIZE_BUTTON))
        self._btn_revert.clicked.connect(self.revert_requested.emit)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self._btn_revert)
        buttons.addWidget(self._btn_apply)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self._empty_label)
        layout.addWidget(self._locked_banner)
        layout.addWidget(scroll, stretch=1)
        layout.addLayout(buttons)

        self.load_focus(None)
        self.recargar_textos()
        self.apply_visual_theme()

    def _pick_color(self) -> None:
        if self._is_content_read_only():
            self.locked_edit_blocked.emit()
            return
        chosen = pick_color(self, self._color_value)
        if chosen is None:
            return
        self._color_value = chosen
        self._update_color_preview()
        self._on_field_edited()

    def _update_color_preview(self) -> None:
        color = parse_color(self._color_value)
        if color:
            self._color_preview.setStyleSheet(f"background: {color.name()};")
        else:
            self._color_preview.setStyleSheet("background: transparent;")

    def _create_editor(self, field: str, kind: str) -> QWidget:
        if kind == "spin":
            widget = QSpinBox()
            widget.setRange(0, 9999)
            widget.setSpecialValueText("—")
            widget.valueChanged.connect(self._on_field_edited)
            return widget
        if kind == "frequency":
            widget = QDoubleSpinBox()
            widget.setRange(0.0, 9999.999)
            widget.setDecimals(3)
            widget.setSuffix(" MHz")
            widget.setSpecialValueText("—")
            widget.valueChanged.connect(self._on_field_edited)
            return widget
        if kind == "bool":
            widget = QCheckBox()
            widget.stateChanged.connect(self._on_field_edited)
            return widget
        if kind == "type":
            widget = QComboBox()
            for device_type in DEVICE_TYPE_ORDER:
                i18n_key = _TYPE_I18N.get(device_type, "inventory_type_other")
                widget.addItem(tr(i18n_key), device_type)
            widget.currentIndexChanged.connect(self._on_field_edited)
            return widget
        widget = QLineEdit()
        widget.textChanged.connect(self._on_field_edited)
        return widget

    def load_focus(self, focus: Optional[Dict[str, Any]]) -> None:
        self._loading = True
        self._focus = dict(focus) if focus else None
        kind = focus_kind(self._focus)
        if kind == FOCUS_CHANNEL and self._focus:
            item = self._focus.get("item") or {}
            self._loaded = dict(item)
        elif kind in (FOCUS_LIST, FOCUS_GROUP):
            meta = dict(self._focus.get("meta") or DEFAULT_METADATA)
            self._loaded = meta
        else:
            self._loaded = None
        self._dirty = False
        self._refresh_form()
        self._loading = False
        self.dirty_changed.emit(False)

    def load_equipo(self, item: Optional[Dict[str, Any]]) -> None:
        if not item:
            self.load_focus(None)
            return
        from core.inventory_channel import channel_key as ck

        self.load_focus(
            {
                "kind": FOCUS_CHANNEL,
                "channel_key": ck(item),
                "item": dict(item),
            }
        )

    def mark_clean(self) -> None:
        if self._loaded:
            self._loaded = dict(self._collect_values())
        self._dirty = False
        self.dirty_changed.emit(False)

    def revert_changes(self) -> None:
        self._loading = True
        self._dirty = False
        self._refresh_form()
        self._loading = False
        self.dirty_changed.emit(False)

    def collect_updates(self) -> Dict[str, Any]:
        return self._collect_values()

    def is_dirty(self) -> bool:
        return self._dirty

    def eventFilter(self, watched, event) -> bool:
        editors = list(self._editors.values()) + [self._notes_edit]
        if event.type() == event.Type.FocusIn and watched in editors:
            self.focus_context_changed.emit(True)
            if self._is_content_read_only():
                self.locked_edit_blocked.emit()
        if (
            event.type() == event.Type.MouseButtonPress
            and watched in editors
            and self._is_content_read_only()
        ):
            self.locked_edit_blocked.emit()
        return super().eventFilter(watched, event)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.focus_context_changed.emit(False)

    def _on_field_edited(self, *_args) -> None:
        if self._loading or not self._loaded:
            return
        current = self._collect_values()
        baseline = self._baseline_values()
        fields = list(self._METADATA_FIELDS)
        if focus_kind(self._focus) == FOCUS_CHANNEL:
            fields.extend(EDITABLE_FIELDS)
        dirty = any(current.get(field) != baseline.get(field) for field in fields)
        if dirty != self._dirty:
            self._dirty = dirty
            self.dirty_changed.emit(dirty)
        self._btn_apply.setEnabled(self.can_apply_changes())
        self._btn_revert.setEnabled(dirty)

    def can_apply_changes(self) -> bool:
        if not self._dirty or not self._loaded:
            return False
        if not self._is_content_read_only():
            return True
        current = self._collect_values()
        baseline = self._baseline_values()
        return current.get("locked") != baseline.get("locked")

    def _is_content_read_only(self) -> bool:
        if not self._loaded:
            return True
        kind = focus_kind(self._focus)
        if kind == FOCUS_LIST:
            return False
        if self._focus and self._focus.get("effective_locked"):
            return True
        return bool(self._loaded.get("locked"))

    def _baseline_values(self) -> Dict[str, Any]:
        if not self._loaded:
            return {}
        kind = focus_kind(self._focus)
        if kind == FOCUS_CHANNEL:
            data = enrich_equipo_metadata(dict(self._loaded))
            values = {field: _normalize_value(field, data.get(field)) for field in EDITABLE_FIELDS}
            values.update(_normalize_metadata(self._loaded))
            return values
        return _normalize_metadata(self._loaded)

    def _collect_values(self) -> Dict[str, Any]:
        values = _collect_metadata(self._notes_edit, self._color_value, self._locked_check)
        if focus_kind(self._focus) == FOCUS_CHANNEL:
            for field, editor in self._editors.items():
                values[field] = _read_editor(field, editor)
        return values

    def _refresh_form(self) -> None:
        kind = focus_kind(self._focus)
        has_selection = kind != "none" and self._loaded is not None
        self._empty_label.setVisible(not has_selection)
        self._scroll.setVisible(has_selection)
        self._btn_apply.setVisible(has_selection)
        self._btn_revert.setVisible(has_selection)
        self._section_titles["inventory_prop_section_meta"].setVisible(has_selection)

        channel_mode = kind == FOCUS_CHANNEL
        for host in self._channel_hosts:
            host.setVisible(has_selection and channel_mode)
        for key, title in self._section_titles.items():
            if key in ("inventory_prop_section_meta", "inventory_prop_section_ids"):
                continue
            title.setVisible(has_selection and channel_mode)
        if self._ids_host:
            self._ids_host.setVisible(has_selection and channel_mode)

        if not has_selection:
            self._title.hide()
            self._subtitle.hide()
            self._locked_banner.hide()
            self._set_editors_enabled(False)
            for host in self._dimmed_hosts:
                host.setStyleSheet("")
            return

        if kind == FOCUS_LIST:
            self._title.setText(tr("inventory_properties_list_title"))
            self._subtitle.setText(tr("inventory_properties_list_subtitle"))
        elif kind == FOCUS_GROUP and self._focus:
            self._title.setText(
                tr("inventory_properties_group_title", label=self._focus.get("label") or "—")
            )
            count = len(self._focus.get("items") or [])
            self._subtitle.setText(tr("inventory_properties_group_subtitle", count=count))
        else:
            data = enrich_equipo_metadata(dict(self._loaded))
            self._title.setText(_title_text(data))
            self._subtitle.setText(_subtitle_text(data))
        self._title.show()
        self._subtitle.show()

        read_only = self._is_content_read_only()
        self._set_editors_enabled(not read_only)
        self._notes_edit.setReadOnly(read_only)
        self._btn_color.setEnabled(not read_only)
        inherited_lock = bool(self._focus and self._focus.get("inherited_lock"))
        self._locked_check.setEnabled(not inherited_lock)

        meta = _normalize_metadata(self._loaded)
        self._notes_edit.setPlainText(str(meta.get("notes") or ""))
        self._color_value = str(meta.get("color") or "")
        self._update_color_preview()
        effective_locked = bool(self._focus and self._focus.get("effective_locked"))
        self._locked_check.setChecked(
            effective_locked if inherited_lock else bool(meta.get("locked"))
        )

        if channel_mode:
            data = enrich_equipo_metadata(dict(self._loaded))
            for field, editor in self._editors.items():
                _write_editor(field, editor, data.get(field))
            for field, label in self._readonly_labels.items():
                label.setText(_format_readonly(field, data.get(field)))

        self._btn_apply.setEnabled(False)
        self._btn_revert.setEnabled(False)
        self._btn_color.setText(tr("inventory_action_pick_color"))
        self._update_locked_visual_state()

    def _update_locked_visual_state(self) -> None:
        locked = bool(self._focus and self._focus.get("effective_locked"))
        self._locked_banner.setVisible(locked)
        if locked:
            if self._focus and self._focus.get("inherited_lock"):
                self._locked_banner.setText(tr("inventory_locked_inherited_hint"))
            else:
                self._locked_banner.setText(tr("inventory_locked_edit_hint"))
        dim_style = "opacity: 0.45;" if locked else ""
        for host in self._dimmed_hosts:
            host.setStyleSheet(dim_style)
        if self._meta_host and locked and not bool(self._focus and self._focus.get("inherited_lock")):
            self._meta_host.setStyleSheet("")

    def _set_editors_enabled(self, enabled: bool) -> None:
        for editor in self._editors.values():
            editor.setEnabled(enabled)

    def _show_context_menu(self, pos) -> None:
        if not self._loaded:
            return
        menu = QMenu(self)
        apply_action = menu.addAction(tr("inventory_action_apply"))
        apply_action.setEnabled(self._dirty)
        apply_action.triggered.connect(self.apply_requested.emit)
        revert_action = menu.addAction(tr("inventory_action_revert"))
        revert_action.setEnabled(self._dirty)
        revert_action.triggered.connect(self.revert_requested.emit)
        if self._focus and focus_kind(self._focus) != FOCUS_LIST:
            menu.addSeparator()
            dup_action = menu.addAction(tr("inventory_action_duplicate"))
            dup_action.setEnabled(self._can_focus_duplicate())
            dup_action.triggered.connect(lambda: self.duplicate_requested.emit(self._focus))
            del_action = menu.addAction(tr("inventory_action_delete"))
            del_action.setEnabled(self._can_focus_delete())
            del_action.triggered.connect(lambda: self.delete_requested.emit(self._focus))
        menu.exec(self.mapToGlobal(pos))

    def _can_focus_duplicate(self) -> bool:
        if not self._focus:
            return False
        kind = focus_kind(self._focus)
        if kind == FOCUS_GROUP:
            return not bool((self._focus.get("meta") or {}).get("locked"))
        if kind == FOCUS_CHANNEL:
            return not self._is_content_read_only()
        return False

    def _can_focus_delete(self) -> bool:
        return self._can_focus_duplicate()

    def apply_visual_theme(self, panel_id: str | None = None) -> None:
        key = panel_id or self._style_key
        apply_panel_style(self, key)
        colors = get_panel_colors(key)
        muted = f"color: {colors['text_muted']};"
        self._empty_label.setStyleSheet(muted)
        self._subtitle.setStyleSheet(muted + " font-size: 11px;")
        self._title.setStyleSheet(
            f"color: {colors['fg']}; font-size: 14px; font-weight: 600;"
        )
        for section_title in self._section_titles.values():
            section_title.setStyleSheet(
                f"color: {colors['fg']}; font-weight: 600; padding-top: 4px;"
            )
        for name_label in self._field_labels.values():
            name_label.setStyleSheet(muted + " font-size: 11px;")
        for value_label in self._readonly_labels.values():
            value_label.setStyleSheet(f"color: {colors['fg']};")
        warning_bg = "#3A3118" if is_dark_mode() else "#FFF4CE"
        warning_fg = "#FFD666" if is_dark_mode() else "#7A5C00"
        self._locked_banner.setStyleSheet(
            f"background: {warning_bg}; color: {warning_fg}; padding: 8px; "
            "border-radius: 4px; font-size: 11px;"
        )

    def recargar_textos(self) -> None:
        self._empty_label.setText(tr("inventory_properties_empty"))
        for section_key, fields in self._EDITABLE_SECTIONS:
            self._section_titles[section_key].setText(tr(section_key))
            for label_key, field, kind in fields:
                self._field_labels[field].setText(tr(label_key))
                if kind == "type" and isinstance(self._editors[field], QComboBox):
                    combo: QComboBox = self._editors[field]
                    current = combo.currentData()
                    combo.blockSignals(True)
                    combo.clear()
                    for device_type in DEVICE_TYPE_ORDER:
                        i18n_key = _TYPE_I18N.get(device_type, "inventory_type_other")
                        combo.addItem(tr(i18n_key), device_type)
                    index = combo.findData(current)
                    combo.setCurrentIndex(index if index >= 0 else 0)
                    combo.blockSignals(False)
        self._section_titles["inventory_prop_section_meta"].setText(tr("inventory_prop_section_meta"))
        self._field_labels["notes"].setText(tr("inventory_prop_notes"))
        self._field_labels["color"].setText(tr("inventory_prop_color"))
        self._field_labels["locked"].setText(tr("inventory_prop_locked"))
        self._btn_color.setText(tr("inventory_action_pick_color"))
        for label_key, field in self._READONLY_FIELDS:
            self._field_labels[field].setText(tr(label_key))
        self._btn_apply.setText(tr("inventory_action_apply"))
        self._btn_revert.setText(tr("inventory_action_revert"))
        self._refresh_form()


def _title_text(data: Dict[str, Any]) -> str:
    name = str(data.get("channel_name") or "").strip()
    number = data.get("channel_number")
    if name and number not in (None, ""):
        return tr("inventory_properties_title", name=name, number=number)
    if name:
        return name
    if number not in (None, ""):
        return tr("inventory_properties_title_number", number=number)
    return tr("inventory_properties_title_unknown")


def _subtitle_text(data: Dict[str, Any]) -> str:
    parts = [
        str(data.get("model") or "").strip(),
        str(data.get("device_name") or "").strip(),
    ]
    return " · ".join(part for part in parts if part)


def _normalize_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "notes": str(data.get("notes") or ""),
        "color": str(data.get("color") or ""),
        "locked": bool(data.get("locked")),
    }


def _collect_metadata(notes_edit: QTextEdit, color: str, locked_check: QCheckBox) -> Dict[str, Any]:
    return {
        "notes": notes_edit.toPlainText(),
        "color": color,
        "locked": locked_check.isChecked(),
    }


def _normalize_value(field: str, value: Any) -> Any:
    if field in ("channel_number", "frequency_mhz") and value in (None, ""):
        return None
    if field in ("coordination_include", "coordination_active", "locked"):
        return bool(value)
    if field in ("notes", "color"):
        return "" if value in (None, "") else str(value)
    if field == "device_type":
        return str(value or "")
    if value is None:
        return ""
    return value


def _read_editor(field: str, editor: QWidget) -> Any:
    if isinstance(editor, QSpinBox):
        return None if editor.value() == editor.minimum() and editor.specialValueText() else editor.value()
    if isinstance(editor, QDoubleSpinBox):
        return None if editor.value() == 0.0 and editor.specialValueText() else editor.value()
    if isinstance(editor, QCheckBox):
        return editor.isChecked()
    if isinstance(editor, QComboBox):
        return editor.currentData()
    if isinstance(editor, QLineEdit):
        return editor.text()
    return None


def _write_editor(field: str, editor: QWidget, value: Any) -> None:
    if isinstance(editor, QSpinBox):
        if value in (None, ""):
            editor.setValue(0)
        else:
            editor.setValue(int(value))
        return
    if isinstance(editor, QDoubleSpinBox):
        if value in (None, ""):
            editor.setValue(0.0)
        else:
            editor.setValue(float(value))
        return
    if isinstance(editor, QCheckBox):
        editor.setChecked(bool(value))
        return
    if isinstance(editor, QComboBox):
        index = editor.findData(value)
        editor.setCurrentIndex(index if index >= 0 else 0)
        return
    if isinstance(editor, QLineEdit):
        editor.setText("" if value is None else str(value))


def _format_readonly(field: str, value: Any) -> str:
    if value is None or value == "":
        return "—"
    if field == "db_id":
        return str(int(value))
    return str(value)
