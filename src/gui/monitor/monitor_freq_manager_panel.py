"""Gestor de frecuencias — tabla simplificada de supervisión por canal."""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Set, Tuple

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPalette
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.inventory_catalog import DEVICE_TYPE_OTHER, _TYPE_I18N
from core.monitor.monitor_format import format_bw_hz
from core.monitor.supervision.alarm_presets import (
    PRESET_UNSUPERVISED,
    AlarmPreset,
    get_preset,
    list_alarm_threshold_preset_options,
    preset_display_name,
    resolve_active_alarm_preset_id,
)
from core.monitor.supervision.supervision_models import SupervisionState, SupervisionTarget
from core.monitor.supervision.threshold_resolver import (
    set_channel_preset,
    threshold_rows_for_state,
)
from gui.configurable_table_header import (
    restore_header_state,
    save_header_state,
    setup_resizable_header,
)
from gui.inventory_color_delegate import COLOR_SWATCH_ROLE
from gui.monitor.monitor_freq_manager_color_delegate import MonitorFreqManagerColorDelegate
from gui.monitor.monitor_shortcuts import MONITOR_SHORTCUTS
from gui.shortcut_tooltips import tooltip_with_shortcut
from i18n.json_translation import tr

_TOOL_BTN_SIZE = QSize(22, 20)
_TOOL_ICON_SIZE = QSize(14, 14)


class MonitorFreqManagerPanel(QWidget):
    """Lista de canales del inventario: supervisado + preset de umbrales editables."""

    state_changed = pyqtSignal(object)
    thresholds_requested = pyqtSignal(object)
    capture_reference_requested = pyqtSignal(str)
    capture_reference_bulk_requested = pyqtSignal(object)
    clear_reference_bulk_requested = pyqtSignal(object)

    _COL_ON = 0
    _COL_LABEL = 1
    _COL_FREQ = 2
    _COL_BW = 3
    _COL_TYPE = 4
    _COL_THRESHOLDS = 5
    _COL_COLOR = 6
    _COL_COUNT = 7

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._state = SupervisionState()
        self._rows: List[dict] = []
        self._rows_signature: Tuple = ()
        self._loading = False
        self._get_equipos: Callable[[], list] = lambda: []
        self._on_table_layout_changed: Callable[[], None] | None = None
        self._pending_table_header: str = ""
        self._build_ui()

    def set_equipos_provider(self, provider: Callable[[], list]) -> None:
        self._get_equipos = provider

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(2)

        self._enable_all_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_DialogYesButton,
            "monitor_freq_manager_tool_enable_all",
            shortcut="",
        )
        self._enable_all_btn.clicked.connect(lambda: self._set_all_enabled(True))

        self._disable_all_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_DialogNoButton,
            "monitor_freq_manager_tool_disable_all",
            shortcut="",
        )
        self._disable_all_btn.clicked.connect(lambda: self._set_all_enabled(False))

        self._preset_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "monitor_freq_manager_tool_preset",
            shortcut=MONITOR_SHORTCUTS["thresholds"],
        )
        self._preset_btn.clicked.connect(
            lambda: self.thresholds_requested.emit({"scope": "global"})
        )

        self._bulk_preset_combo = QComboBox()
        self._bulk_preset_combo.setMinimumContentsLength(14)
        self._bulk_preset_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._bulk_preset_combo.setToolTip(tr("monitor_freq_manager_bulk_preset_tip"))

        self._bulk_apply_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_DialogApplyButton,
            "monitor_freq_manager_bulk_preset_apply",
            shortcut="",
        )
        self._bulk_apply_btn.clicked.connect(self._apply_bulk_preset_to_all)

        for btn in (self._enable_all_btn, self._disable_all_btn, self._preset_btn):
            toolbar.addWidget(btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        toolbar.addWidget(self._bulk_preset_combo, alignment=Qt.AlignmentFlag.AlignVCenter)
        toolbar.addWidget(self._bulk_apply_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self._summary = QLabel()
        self._summary.setObjectName("MonitorFreqManagerSummary")
        layout.addWidget(self._summary)

        self._table = QTableWidget(0, self._COL_COUNT)
        self._table.setObjectName("MonitorFreqManagerTable")
        self._table.setAlternatingRowColors(True)
        self._apply_header_labels()
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)
        self._color_delegate = MonitorFreqManagerColorDelegate(self._table)
        self._table.setItemDelegateForColumn(self._COL_COLOR, self._color_delegate)
        table_header = self._table.horizontalHeader()
        setup_resizable_header(
            table_header,
            self._COL_COUNT,
            on_changed=self._notify_table_layout_changed,
        )
        self._configure_table_header_resize()
        self._apply_default_column_widths()
        self._table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._table, stretch=1)

        from gui.app_chrome_styles import apply_monitor_freq_manager_styles

        apply_monitor_freq_manager_styles(self)
        self._reload_bulk_preset_combo()

    def _configure_table_header_resize(self) -> None:
        """Todas las columnas redimensionables; Sup/Color fijas y estrechas."""
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(32)
        for index in range(self._COL_COUNT):
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self._COL_ON, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(self._COL_ON, 40)
        header.setSectionResizeMode(self._COL_COLOR, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(self._COL_COLOR, 44)

    def _apply_default_column_widths(self) -> None:
        header = self._table.horizontalHeader()
        for col, width in (
            (self._COL_LABEL, 160),
            (self._COL_FREQ, 76),
            (self._COL_BW, 72),
            (self._COL_TYPE, 100),
            (self._COL_THRESHOLDS, 180),
        ):
            header.resizeSection(col, width)

    def _make_tool_button(
        self,
        icon: QStyle.StandardPixmap,
        tip_key: str,
        *,
        shortcut: str = "",
    ) -> QToolButton:
        btn = QToolButton(self)
        btn.setObjectName("MonitorSupervisionToolBtn")
        style = self.style()
        if style is not None:
            btn.setIcon(style.standardIcon(icon))
        btn.setIconSize(_TOOL_ICON_SIZE)
        btn.setFixedSize(_TOOL_BTN_SIZE)
        btn.setToolTip(
            tooltip_with_shortcut(tr(tip_key), shortcut) if shortcut else tr(tip_key)
        )
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setAutoRaise(True)
        return btn

    def _apply_header_labels(self) -> None:
        self._table.setHorizontalHeaderLabels(
            [
                tr("monitor_freq_manager_col_on"),
                tr("monitor_freq_manager_col_channel"),
                tr("monitor_freq_manager_col_freq"),
                tr("monitor_freq_manager_col_bw"),
                tr("monitor_freq_manager_col_type"),
                tr("monitor_freq_manager_col_thresholds"),
                tr("inventory_col_color"),
            ]
        )

    def _user_presets_map(self) -> Dict[str, AlarmPreset]:
        return {
            key: AlarmPreset.from_dict(value)
            for key, value in (self._state.user_presets or {}).items()
            if isinstance(value, dict)
        }

    def _threshold_option_ids(self, user_presets: Dict[str, AlarmPreset]) -> Set[str]:
        return set(list_alarm_threshold_preset_options(user_presets))

    def _channel_alarm_preset_id(self, channel_key: str, user_presets: Dict[str, AlarmPreset]) -> str:
        options = self._threshold_option_ids(user_presets)
        target = self._find_target(channel_key)
        if target is not None:
            preset_id = str(target.preset_id or "").strip()
            if preset_id in options:
                return preset_id
            if preset_id == PRESET_UNSUPERVISED:
                return resolve_active_alarm_preset_id(self._state)
        return resolve_active_alarm_preset_id(self._state)

    def set_state(self, state: SupervisionState) -> None:
        new_rows = threshold_rows_for_state(state, self._get_equipos())
        signature = self._compute_signature(new_rows, state)
        if signature == self._rows_signature:
            return
        self._loading = True
        scroll = self._table.verticalScrollBar().value()
        selected = self._selected_channel_keys()
        sort_col = self._table.horizontalHeader().sortIndicatorSection()
        sort_order = self._table.horizontalHeader().sortIndicatorOrder()
        try:
            self._state = state
            self._rows = new_rows
            self._rows_signature = signature
            self._reload_bulk_preset_combo()
            self._rebuild_table()
            self._update_summary()
            if sort_col >= 0:
                self._table.sortItems(sort_col, sort_order)
            self._restore_selection(selected)
            self._table.verticalScrollBar().setValue(scroll)
            self._apply_pending_table_header()
        finally:
            self._loading = False

    def get_state(self) -> SupervisionState:
        return self._state

    def _selected_channel_keys(self) -> List[str]:
        keys: List[str] = []
        for index in self._table.selectionModel().selectedRows():
            item = self._table.item(index.row(), self._COL_ON)
            if item is None:
                continue
            key = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if key:
                keys.append(key)
        return keys

    def _restore_selection(self, keys: List[str]) -> None:
        if not keys:
            return
        key_set = set(keys)
        self._table.clearSelection()
        for row_index in range(self._table.rowCount()):
            item = self._table.item(row_index, self._COL_ON)
            if item is None:
                continue
            key = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if key in key_set:
                self._table.selectRow(row_index)

    def _compute_signature(self, rows: List[dict], state: SupervisionState) -> tuple:
        user_presets = self._user_presets_map()
        return (
            resolve_active_alarm_preset_id(state),
            tuple(
                (
                    str(row.get("channel_key") or ""),
                    bool(row.get("enabled")),
                    float(row.get("bandwidth_hz") or 0.0),
                    str(row.get("label") or ""),
                    str(row.get("frequency_mhz") or ""),
                    str(row.get("device_type") or ""),
                    str(row.get("color") or ""),
                    self._channel_alarm_preset_id(str(row.get("channel_key") or ""), user_presets),
                )
                for row in rows
            ),
        )

    def _reload_bulk_preset_combo(self) -> None:
        user_presets = self._user_presets_map()
        current = self._bulk_preset_combo.currentData()
        self._bulk_preset_combo.blockSignals(True)
        self._bulk_preset_combo.clear()
        for preset_id in list_alarm_threshold_preset_options(user_presets):
            preset = get_preset(preset_id, user_presets)
            if preset is None:
                continue
            self._bulk_preset_combo.addItem(preset_display_name(preset, tr=tr), preset_id)
        preferred = current or resolve_active_alarm_preset_id(self._state)
        idx = self._bulk_preset_combo.findData(preferred)
        if idx >= 0:
            self._bulk_preset_combo.setCurrentIndex(idx)
        elif self._bulk_preset_combo.count() > 0:
            self._bulk_preset_combo.setCurrentIndex(0)
        self._bulk_preset_combo.blockSignals(False)

    def _apply_bulk_preset_to_all(self) -> None:
        preset_id = str(self._bulk_preset_combo.currentData() or "")
        if not preset_id or not self._state.targets:
            return
        for target in self._state.targets:
            key = str(target.channel_key or "")
            if not key:
                continue
            set_channel_preset(self._state, key, preset_id, clear_overrides=False)
            if preset_id == PRESET_UNSUPERVISED:
                target.enabled = False
        self._refresh_rows_and_emit()

    def _rebuild_table(self) -> None:
        sorting = self._table.isSortingEnabled()
        self._table.setSortingEnabled(False)
        self._table.blockSignals(True)
        self._table.setRowCount(len(self._rows))
        user_presets = self._user_presets_map()
        threshold_ids = list_alarm_threshold_preset_options(user_presets)

        for row_index, row in enumerate(self._rows):
            key = str(row.get("channel_key") or "")
            enabled = bool(row.get("enabled"))
            alarm_preset_id = self._channel_alarm_preset_id(key, user_presets)

            on_item = QTableWidgetItem()
            on_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            on_item.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
            on_item.setData(Qt.ItemDataRole.UserRole, key)
            self._table.setItem(row_index, self._COL_ON, on_item)

            label_item = QTableWidgetItem(str(row.get("label") or ""))
            label_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row_index, self._COL_LABEL, label_item)

            freq_mhz = row.get("frequency_mhz")
            freq_text = "—"
            freq_sort = -1.0
            if freq_mhz not in (None, ""):
                try:
                    freq_sort = float(freq_mhz)
                    freq_text = f"{freq_sort:.3f}"
                except (TypeError, ValueError):
                    pass
            freq_item = QTableWidgetItem(freq_text)
            freq_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            freq_item.setData(Qt.ItemDataRole.UserRole, freq_sort)
            freq_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row_index, self._COL_FREQ, freq_item)

            bw_hz = float(row.get("bandwidth_hz") or 0.0)
            bw_item = QTableWidgetItem(format_bw_hz(bw_hz))
            bw_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            bw_item.setData(Qt.ItemDataRole.UserRole, bw_hz)
            bw_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row_index, self._COL_BW, bw_item)

            device_type = str(row.get("device_type") or DEVICE_TYPE_OTHER)
            type_key = _TYPE_I18N.get(device_type, "inventory_type_other")
            type_item = QTableWidgetItem(tr(type_key))
            type_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row_index, self._COL_TYPE, type_item)

            self._table.setCellWidget(
                row_index,
                self._COL_THRESHOLDS,
                self._build_threshold_combo(key, alarm_preset_id, enabled, threshold_ids, user_presets),
            )

            color_value = str(row.get("color") or "")
            color_item = QTableWidgetItem("")
            color_item.setData(COLOR_SWATCH_ROLE, color_value)
            color_item.setData(Qt.ItemDataRole.UserRole, color_value.lower())
            color_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            color_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row_index, self._COL_COLOR, color_item)

            self._apply_row_unsupervised_style(row_index, enabled)

        self._table.blockSignals(False)
        self._table.setSortingEnabled(sorting)

    def _build_threshold_combo(
        self,
        channel_key: str,
        preset_id: str,
        enabled: bool,
        threshold_ids: List[str],
        user_presets: Dict[str, AlarmPreset],
    ) -> QComboBox:
        combo = QComboBox()
        combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        for option_id in threshold_ids:
            preset = get_preset(option_id, user_presets)
            if preset is None:
                continue
            combo.addItem(preset_display_name(preset, tr=tr), option_id)
        idx = combo.findData(preset_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.setProperty("channel_key", channel_key)
        combo.setEnabled(enabled)
        combo.currentIndexChanged.connect(
            lambda _index, widget=combo: self._on_threshold_preset_changed(widget)
        )
        return combo

    def _apply_row_unsupervised_style(self, row_index: int, enabled: bool) -> None:
        normal_brush = self.palette().brush(QPalette.ColorRole.Text)
        threshold_combo = self._table.cellWidget(row_index, self._COL_THRESHOLDS)
        if isinstance(threshold_combo, QComboBox):
            threshold_combo.setEnabled(enabled)

        for col in range(self._COL_COUNT):
            if col in (self._COL_THRESHOLDS, self._COL_COLOR):
                continue
            item = self._table.item(row_index, col)
            if item is None:
                continue
            if enabled:
                font = item.font()
                font.setStrikeOut(False)
                item.setFont(font)
                item.setForeground(normal_brush)
            else:
                self._style_unsupervised(item)

        color_item = self._table.item(row_index, self._COL_COLOR)
        if color_item is not None and not enabled:
            font = color_item.font()
            font.setStrikeOut(True)
            color_item.setFont(font)

    @staticmethod
    def _style_unsupervised(item: QTableWidgetItem) -> None:
        font = item.font()
        font.setStrikeOut(True)
        item.setFont(font)
        item.setForeground(QBrush(QColor("#888888")))

    def _update_summary(self) -> None:
        total = len(self._rows)
        enabled = sum(1 for row in self._rows if row.get("enabled"))
        if total == 0:
            text = tr("monitor_freq_manager_empty")
        else:
            text = tr("monitor_freq_manager_summary").format(enabled=enabled, total=total)
        if self._summary.text() != text:
            self._summary.setText(text)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading or item.column() != self._COL_ON:
            return
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if not key:
            return
        target = self._find_target(key)
        if target is None:
            return

        self._loading = True
        self._table.blockSignals(True)
        try:
            enabled = item.checkState() == Qt.CheckState.Checked
            target.enabled = enabled
            row_data = next(
                (row for row in self._rows if str(row.get("channel_key") or "") == key),
                None,
            )
            if row_data is not None:
                row_data["enabled"] = enabled

            user_presets = self._user_presets_map()
            if not enabled:
                set_channel_preset(self._state, key, PRESET_UNSUPERVISED, clear_overrides=False)
            else:
                alarm_id = self._channel_alarm_preset_id(key, user_presets)
                set_channel_preset(self._state, key, alarm_id, clear_overrides=False)
                combo = self._table.cellWidget(item.row(), self._COL_THRESHOLDS)
                if isinstance(combo, QComboBox):
                    combo.blockSignals(True)
                    combo.setEnabled(True)
                    idx = combo.findData(alarm_id)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                    combo.blockSignals(False)

            self._apply_row_unsupervised_style(item.row(), enabled)
            self._update_summary()
            self._rows = threshold_rows_for_state(self._state, self._get_equipos())
            self._rows_signature = self._compute_signature(self._rows, self._state)
        finally:
            self._table.blockSignals(False)
            self._loading = False

        self.state_changed.emit(self._state)

    def _on_threshold_preset_changed(self, combo: QComboBox) -> None:
        if self._loading:
            return
        key = str(combo.property("channel_key") or "")
        preset_id = str(combo.currentData() or "")
        if not key or not preset_id:
            return
        target = self._find_target(key)
        if target is None:
            return

        self._loading = True
        self._table.blockSignals(True)
        try:
            set_channel_preset(self._state, key, preset_id, clear_overrides=False)
            target.enabled = True
            on_item = self._find_on_item_for_key(key)
            if on_item is not None:
                on_item.setCheckState(Qt.CheckState.Checked)
            row_data = next(
                (row for row in self._rows if str(row.get("channel_key") or "") == key),
                None,
            )
            if row_data is not None:
                row_data["enabled"] = True
            row = self._table_row_for_key(key)
            if row >= 0:
                self._apply_row_unsupervised_style(row, True)
            self._update_summary()
            self._rows = threshold_rows_for_state(self._state, self._get_equipos())
            self._rows_signature = self._compute_signature(self._rows, self._state)
        finally:
            self._table.blockSignals(False)
            self._loading = False

        self.state_changed.emit(self._state)

    def _table_row_for_key(self, channel_key: str) -> int:
        for row_index in range(self._table.rowCount()):
            item = self._table.item(row_index, self._COL_ON)
            if item is None:
                continue
            if str(item.data(Qt.ItemDataRole.UserRole) or "") == channel_key:
                return row_index
        return -1

    def _find_on_item_for_key(self, channel_key: str) -> QTableWidgetItem | None:
        row = self._table_row_for_key(channel_key)
        if row < 0:
            return None
        return self._table.item(row, self._COL_ON)

    def _find_target(self, channel_key: str) -> SupervisionTarget | None:
        for target in self._state.targets:
            if target.channel_key == channel_key:
                return target
        return None

    def _set_all_enabled(self, enabled: bool) -> None:
        user_presets = self._user_presets_map()
        default_alarm = resolve_active_alarm_preset_id(self._state)
        for target in self._state.targets:
            target.enabled = enabled
            if not enabled:
                target.preset_id = PRESET_UNSUPERVISED
            elif str(target.preset_id or "") in ("", PRESET_UNSUPERVISED):
                target.preset_id = default_alarm
            elif str(target.preset_id or "") not in self._threshold_option_ids(user_presets):
                target.preset_id = default_alarm
        self._refresh_rows_and_emit()

    def _refresh_rows_and_emit(self) -> None:
        selected = self._selected_channel_keys()
        self._rows = threshold_rows_for_state(self._state, self._get_equipos())
        self._rows_signature = self._compute_signature(self._rows, self._state)
        sort_col = self._table.horizontalHeader().sortIndicatorSection()
        sort_order = self._table.horizontalHeader().sortIndicatorOrder()
        self._loading = True
        try:
            self._rebuild_table()
            if sort_col >= 0:
                self._table.sortItems(sort_col, sort_order)
            self._restore_selection(selected)
            self._update_summary()
        finally:
            self._loading = False
        self.state_changed.emit(self._state)

    def set_table_layout_changed_callback(self, callback: Callable[[], None] | None) -> None:
        self._on_table_layout_changed = callback

    def save_table_header_state(self) -> str:
        return save_header_state(self._table.horizontalHeader())

    def apply_table_header_state(self, state: str) -> None:
        if not isinstance(state, str) or not state:
            return
        self._pending_table_header = state
        if self._table.rowCount() > 0:
            self._apply_pending_table_header()

    def _apply_pending_table_header(self) -> None:
        if not self._pending_table_header:
            return
        restore_header_state(self._table.horizontalHeader(), self._pending_table_header)
        self._configure_table_header_resize()
        self._pending_table_header = ""

    def _notify_table_layout_changed(self) -> None:
        if self._on_table_layout_changed is not None:
            self._on_table_layout_changed()

    def recargar_textos(self) -> None:
        self._enable_all_btn.setToolTip(tr("monitor_freq_manager_tool_enable_all"))
        self._disable_all_btn.setToolTip(tr("monitor_freq_manager_tool_disable_all"))
        self._preset_btn.setToolTip(
            tooltip_with_shortcut(
                tr("monitor_freq_manager_tool_preset"),
                MONITOR_SHORTCUTS["thresholds"],
            )
        )
        self._bulk_preset_combo.setToolTip(tr("monitor_freq_manager_bulk_preset_tip"))
        self._bulk_apply_btn.setToolTip(tr("monitor_freq_manager_bulk_preset_apply"))
        self._reload_bulk_preset_combo()
        self._apply_header_labels()
        self._update_summary()
        if self._rows:
            self._rows_signature = ()
            self.set_state(self._state)
