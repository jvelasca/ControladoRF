"""Diálogo de umbrales por ámbito — tabla de frecuencias del equipo o rama."""
from __future__ import annotations

import copy
from typing import Dict, List, Optional, Set

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.monitor.monitor_format import format_bw_hz
from core.monitor.supervision.alarm_presets import (
    AlarmPreset,
    get_preset,
    list_alarm_threshold_preset_options,
    preset_display_name,
    resolve_active_alarm_preset_id,
)
from core.monitor.supervision.supervision_models import SupervisionState
from core.monitor.supervision.threshold_resolver import set_channel_preset, threshold_rows_for_state
from gui.dialog_styles import apply_professional_dialog_style, build_dialog_header
from i18n.json_translation import tr


class MonitorSupervisionScopeFreqDialog(QDialog):
    """Preset de umbrales por canal para un equipo o selección del árbol."""

    _COL_LABEL = 0
    _COL_FREQ = 1
    _COL_BW = 2
    _COL_THRESHOLDS = 3

    def __init__(
        self,
        state: SupervisionState,
        equipos: List[dict],
        channel_keys: List[str],
        *,
        scope_title: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._working = copy.deepcopy(state)
        self._equipos = list(equipos or [])
        key_set = {str(key) for key in channel_keys if key}
        self._channel_keys = sorted(key_set)
        self._scope_title = scope_title.strip() or tr("monitor_supervision_scope_freq_default_title")
        self.setWindowTitle(tr("monitor_supervision_scope_freq_title").format(name=self._scope_title))
        apply_professional_dialog_style(self)
        self.resize(620, 360)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(
            build_dialog_header(
                tr("monitor_supervision_scope_freq_title").format(name=self._scope_title),
                tr("monitor_supervision_scope_freq_intro"),
            )
        )

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            [
                tr("monitor_freq_manager_col_channel"),
                tr("monitor_freq_manager_col_freq"),
                tr("monitor_freq_manager_col_bw"),
                tr("monitor_freq_manager_col_thresholds"),
            ]
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(self._COL_LABEL, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self._COL_THRESHOLDS, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate_table()

    def _user_presets_map(self) -> Dict[str, AlarmPreset]:
        return {
            key: AlarmPreset.from_dict(value)
            for key, value in (self._working.user_presets or {}).items()
            if isinstance(value, dict)
        }

    def _threshold_option_ids(self, user_presets: Dict[str, AlarmPreset]) -> List[str]:
        return list_alarm_threshold_preset_options(user_presets)

    def _channel_preset_id(self, channel_key: str, user_presets: Dict[str, AlarmPreset]) -> str:
        options: Set[str] = set(self._threshold_option_ids(user_presets))
        target = self._find_target(channel_key)
        if target is not None:
            preset_id = str(target.preset_id or "").strip()
            if preset_id in options:
                return preset_id
        return resolve_active_alarm_preset_id(self._working)

    def _find_target(self, channel_key: str):
        for target in self._working.targets:
            if target.channel_key == channel_key:
                return target
        return None

    def _rows_for_scope(self) -> List[dict]:
        rows = threshold_rows_for_state(self._working, self._equipos)
        key_set = set(self._channel_keys)
        return [row for row in rows if str(row.get("channel_key") or "") in key_set]

    def _populate_table(self) -> None:
        user_presets = self._user_presets_map()
        threshold_ids = self._threshold_option_ids(user_presets)
        rows = self._rows_for_scope()
        self._table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            key = str(row.get("channel_key") or "")
            label_item = QTableWidgetItem(str(row.get("label") or key))
            label_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(row_index, self._COL_LABEL, label_item)

            freq_item = QTableWidgetItem(str(row.get("frequency_mhz") or ""))
            freq_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            freq_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(row_index, self._COL_FREQ, freq_item)

            bw_hz = float(row.get("bandwidth_hz") or 0.0)
            bw_item = QTableWidgetItem(format_bw_hz(bw_hz) if bw_hz > 0 else "")
            bw_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            bw_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(row_index, self._COL_BW, bw_item)

            preset_id = self._channel_preset_id(key, user_presets)
            combo = QComboBox(self._table)
            for option_id in threshold_ids:
                preset = get_preset(option_id, user_presets)
                if preset is None:
                    continue
                combo.addItem(preset_display_name(preset, tr=tr), option_id)
            idx = combo.findData(preset_id)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.setProperty("channel_key", key)
            combo.currentIndexChanged.connect(
                lambda _index, widget=combo: self._on_preset_changed(widget)
            )
            self._table.setCellWidget(row_index, self._COL_THRESHOLDS, combo)

    def _on_preset_changed(self, combo: QComboBox) -> None:
        key = str(combo.property("channel_key") or "")
        preset_id = str(combo.currentData() or "")
        if not key or not preset_id:
            return
        set_channel_preset(self._working, key, preset_id, clear_overrides=False)

    def get_state(self) -> SupervisionState:
        return self._working
