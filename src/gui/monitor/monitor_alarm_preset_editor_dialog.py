"""Editor de presets de umbrales de supervisión RF."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.monitor.supervision.alarm_presets import (
    BUILTIN_PRESET_ORDER,
    AlarmPreset,
    clone_preset_checks,
    get_preset,
    list_preset_options,
)
from core.monitor.supervision.supervision_models import SupervisionState
from core.monitor.supervision.threshold_checks import (
    ALL_CHECK_IDS,
    CHECK_CATALOG,
    ThresholdCheckConfig,
)
from gui.dialog_styles import apply_professional_dialog_style, build_dialog_header
from i18n.json_translation import tr


class MonitorAlarmPresetEditorDialog(QDialog):
    """Editor de plantillas de umbrales (builtin + usuario)."""

    def __init__(
        self,
        state: SupervisionState,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._working_presets: Dict[str, AlarmPreset] = {
            key: AlarmPreset.from_dict(value)
            for key, value in (state.user_presets or {}).items()
            if isinstance(value, dict)
        }
        self._current_id = ""
        self._loading = False
        self.setWindowTitle(tr("monitor_preset_editor_title"))
        apply_professional_dialog_style(self)
        self.resize(860, 520)
        self._build_ui()
        self._load_preset_list()
        if BUILTIN_PRESET_ORDER:
            self._select_preset(BUILTIN_PRESET_ORDER[0])

    def get_user_presets(self) -> Dict[str, Dict[str, Any]]:
        return {pid: preset.to_dict() for pid, preset in self._working_presets.items()}

    def get_default_preset_id(self) -> str:
        return str(self._default_combo.currentData() or "analog_standard")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(
            build_dialog_header(
                tr("monitor_preset_editor_title"),
                tr("monitor_preset_editor_intro"),
            )
        )

        default_row = QHBoxLayout()
        default_row.addWidget(QLabel(tr("monitor_preset_editor_default")))
        self._default_combo = QComboBox()
        default_row.addWidget(self._default_combo, stretch=1)
        layout.addLayout(default_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._preset_list = QComboBox()
        self._preset_list.currentIndexChanged.connect(self._on_preset_selected)
        left_layout.addWidget(self._preset_list)
        btn_row = QHBoxLayout()
        self._duplicate_btn = QPushButton(tr("monitor_preset_editor_duplicate"))
        self._duplicate_btn.clicked.connect(self._duplicate_preset)
        self._export_btn = QPushButton(tr("monitor_preset_editor_export"))
        self._export_btn.clicked.connect(self._export_preset)
        self._import_btn = QPushButton(tr("monitor_preset_editor_import"))
        self._import_btn.clicked.connect(self._import_preset)
        btn_row.addWidget(self._duplicate_btn)
        btn_row.addWidget(self._export_btn)
        btn_row.addWidget(self._import_btn)
        left_layout.addLayout(btn_row)
        left_layout.addStretch(1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self._preset_title = QLabel()
        self._preset_title.setObjectName("MonitorPresetEditorTitle")
        font = self._preset_title.font()
        font.setBold(True)
        self._preset_title.setFont(font)
        right_layout.addWidget(self._preset_title)

        self._table = QTableWidget(len(ALL_CHECK_IDS), 6)
        self._table.setHorizontalHeaderLabels(
            [
                tr("monitor_preset_col_check"),
                tr("monitor_preset_col_enabled"),
                tr("monitor_preset_col_warn"),
                tr("monitor_preset_col_crit"),
                tr("monitor_preset_col_warn_clear"),
                tr("monitor_preset_col_debounce"),
            ]
        )
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        right_layout.addWidget(self._table, stretch=1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._editors: List[Dict[str, Any]] = []

    def _load_preset_list(self) -> None:
        self._preset_list.blockSignals(True)
        self._default_combo.blockSignals(True)
        self._preset_list.clear()
        self._default_combo.clear()
        for preset_id in list_preset_options(self._working_presets):
            preset = get_preset(preset_id, self._working_presets)
            if preset is None:
                continue
            label = tr(preset.name_key) if preset.is_builtin else preset.name_key
            self._preset_list.addItem(label, preset_id)
            self._default_combo.addItem(label, preset_id)
        current_default = str(self._state.default_preset_id or "analog_standard")
        idx = self._default_combo.findData(current_default)
        if idx >= 0:
            self._default_combo.setCurrentIndex(idx)
        self._preset_list.blockSignals(False)
        self._default_combo.blockSignals(False)

    def _select_preset(self, preset_id: str) -> None:
        idx = self._preset_list.findData(preset_id)
        if idx >= 0:
            self._preset_list.setCurrentIndex(idx)

    def _on_preset_selected(self) -> None:
        preset_id = str(self._preset_list.currentData() or "")
        if not preset_id:
            return
        if self._current_id and not self._loading:
            self._save_matrix_to_preset(self._current_id)
        self._current_id = preset_id
        self._populate_matrix(preset_id)

    def _populate_matrix(self, preset_id: str) -> None:
        preset = get_preset(preset_id, self._working_presets)
        if preset is None:
            return
        self._loading = True
        label = tr(preset.name_key) if preset.is_builtin else preset.name_key
        readonly = tr("monitor_preset_editor_builtin") if preset.is_builtin else tr("monitor_preset_editor_user")
        self._preset_title.setText(f"{label} — {readonly}")
        self._editors.clear()
        self._table.setRowCount(len(ALL_CHECK_IDS))
        editable = not preset.is_builtin

        for row, check_id in enumerate(ALL_CHECK_IDS):
            definition = CHECK_CATALOG.get(check_id)
            name = tr(definition.i18n_name_key) if definition else check_id
            name_item = QTableWidgetItem(name)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(row, 0, name_item)

            cfg = preset.checks.get(check_id, ThresholdCheckConfig())
            enabled = QCheckBox()
            enabled.setChecked(cfg.enabled)
            enabled.setEnabled(editable)
            enabled_widget = QWidget()
            enabled_layout = QHBoxLayout(enabled_widget)
            enabled_layout.addWidget(enabled)
            enabled_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            enabled_layout.setContentsMargins(0, 0, 0, 0)
            self._table.setCellWidget(row, 1, enabled_widget)

            warn = self._make_spin(cfg.warning_raise, editable and cfg.enabled)
            crit = self._make_spin(cfg.critical_raise, editable and cfg.enabled)
            warn_clear = self._make_spin(cfg.warning_clear, editable and cfg.enabled)
            debounce = QSpinBox()
            debounce.setRange(0, 60_000)
            debounce.setSuffix(" ms")
            debounce.setValue(int(cfg.debounce_ms or (definition.default_debounce_ms if definition else 500)))
            debounce.setEnabled(editable and cfg.enabled)

            self._table.setCellWidget(row, 2, warn)
            self._table.setCellWidget(row, 3, crit)
            self._table.setCellWidget(row, 4, warn_clear)
            self._table.setCellWidget(row, 5, debounce)

            enabled.toggled.connect(
                lambda checked, w=warn, c=crit, wc=warn_clear, d=debounce, ed=editable: self._toggle_row(
                    checked, w, c, wc, d, ed
                )
            )

            self._editors.append(
                {
                    "check_id": check_id,
                    "enabled": enabled,
                    "warn": warn,
                    "crit": crit,
                    "warn_clear": warn_clear,
                    "debounce": debounce,
                }
            )
        self._loading = False

    @staticmethod
    def _make_spin(value: float | None, editable: bool) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 120.0)
        spin.setDecimals(1)
        spin.setSuffix(" dB")
        spin.setEnabled(editable)
        if value is None:
            spin.setValue(0.0)
        else:
            spin.setValue(float(value))
        return spin

    @staticmethod
    def _toggle_row(
        checked: bool,
        warn: QDoubleSpinBox,
        crit: QDoubleSpinBox,
        warn_clear: QDoubleSpinBox,
        debounce: QSpinBox,
        editable: bool,
    ) -> None:
        active = editable and checked
        warn.setEnabled(active)
        crit.setEnabled(active)
        warn_clear.setEnabled(active)
        debounce.setEnabled(active)

    def _save_matrix_to_preset(self, preset_id: str) -> None:
        preset = get_preset(preset_id, self._working_presets)
        if preset is None or preset.is_builtin:
            return
        checks: Dict[str, ThresholdCheckConfig] = {}
        for editor in self._editors:
            check_id = str(editor["check_id"])
            enabled: QCheckBox = editor["enabled"]
            if not enabled.isChecked():
                checks[check_id] = ThresholdCheckConfig(enabled=False)
                continue
            checks[check_id] = ThresholdCheckConfig(
                enabled=True,
                warning_raise=float(editor["warn"].value()),
                critical_raise=float(editor["crit"].value()),
                warning_clear=float(editor["warn_clear"].value()),
                debounce_ms=int(editor["debounce"].value()),
            )
        self._working_presets[preset_id] = AlarmPreset(
            preset_id=preset_id,
            name_key=preset.name_key,
            technology=preset.technology,
            checks=checks,
            is_builtin=False,
        )

    def _duplicate_preset(self) -> None:
        source_id = str(self._preset_list.currentData() or "")
        source = get_preset(source_id, self._working_presets)
        if source is None:
            return
        name, ok = self._prompt_text(tr("monitor_preset_editor_duplicate_name"), f"{tr(source.name_key)} copy")
        if not ok or not name.strip():
            return
        new_id = self._slugify(name)
        if get_preset(new_id, self._working_presets) is not None:
            QMessageBox.warning(self, tr("monitor_preset_editor_title"), tr("monitor_preset_editor_duplicate_exists"))
            return
        self._working_presets[new_id] = AlarmPreset(
            preset_id=new_id,
            name_key=name.strip(),
            technology=source.technology,
            checks=clone_preset_checks(source),
            is_builtin=False,
        )
        self._load_preset_list()
        self._current_id = ""
        self._select_preset(new_id)

    def _export_preset(self) -> None:
        preset_id = str(self._preset_list.currentData() or "")
        preset = get_preset(preset_id, self._working_presets)
        if preset is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("monitor_preset_editor_export"),
            f"{preset_id}.json",
            "JSON (*.json)",
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(preset.to_dict(), handle, indent=2, ensure_ascii=False)

    def _import_preset(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("monitor_preset_editor_import"),
            "",
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("invalid preset")
            preset = AlarmPreset.from_dict(data)
            if not preset.preset_id:
                preset = AlarmPreset.from_dict({**data, "preset_id": self._slugify(path)})
            preset = AlarmPreset(
                preset_id=preset.preset_id,
                name_key=preset.name_key,
                technology=preset.technology,
                checks=clone_preset_checks(preset),
                is_builtin=False,
            )
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            QMessageBox.warning(self, tr("monitor_preset_editor_title"), tr("monitor_preset_editor_import_error"))
            return
        self._working_presets[preset.preset_id] = preset
        self._load_preset_list()
        self._current_id = ""
        self._select_preset(preset.preset_id)

    def _prompt_text(self, title: str, default: str) -> tuple[str, bool]:
        from PyQt6.QtWidgets import QInputDialog

        text, ok = QInputDialog.getText(self, title, tr("monitor_preset_editor_name_label"), text=default)
        return text, ok

    @staticmethod
    def _slugify(text: str) -> str:
        base = "".join(ch if ch.isalnum() else "_" for ch in str(text).lower()).strip("_")
        return base[:48] or "preset_custom"

    def _accept(self) -> None:
        if self._current_id:
            self._save_matrix_to_preset(self._current_id)
        self.accept()
