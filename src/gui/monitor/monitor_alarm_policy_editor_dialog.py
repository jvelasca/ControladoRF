"""Editor modal de política de alarmas por preset (filas × severidad).

Columnas: Comentario · Menor · Aviso · Crítica (prioridad 4→1).
Cada fila define una condición medible y la severidad que dispara.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
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
    QRadioButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.monitor.supervision.alarm_policy_rules import (
    BELOW_CONDITIONS,
    CONDITION_I18N,
    COND_SYNC_LOST,
    DROP_CONDITIONS,
    AlarmPolicyRule,
    checks_from_rules,
    default_conditions_for_mode,
    ensure_preset_rules,
    format_rule_label,
    new_rule_id,
)
from core.monitor.supervision.alarm_presets import (
    BUILTIN_PRESET_ORDER,
    AlarmPreset,
    clone_preset_rules,
    get_preset,
    list_preset_options,
)
from core.monitor.supervision.alarm_severity import EDITOR_SEVERITY_COLUMNS, SEVERITY_I18N_KEY
from core.monitor.supervision.supervision_models import SupervisionState
from gui.dialog_styles import apply_professional_dialog_style, build_dialog_header
from i18n.json_translation import tr


class MonitorAlarmPolicyEditorDialog(QDialog):
    """Editor modal de plantillas de alarmas (integradas solo lectura)."""

    _COL_LABEL = 0
    _COL_THRESHOLD = 1
    _COL_FIRST_SEV = 2
    _COL_COUNT = 6

    def __init__(
        self,
        state: SupervisionState,
        *,
        parent: Optional[QWidget] = None,
        initial_preset_id: str = "",
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
        self._row_widgets: List[dict] = []
        self.setWindowTitle(tr("monitor_policy_editor_title"))
        apply_professional_dialog_style(self)
        self.resize(980, 620)
        self._build_ui()
        self._load_preset_list()
        start = initial_preset_id or (BUILTIN_PRESET_ORDER[0] if BUILTIN_PRESET_ORDER else "")
        if start:
            self._select_preset(start)

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
                tr("monitor_policy_editor_title"),
                tr("monitor_policy_editor_intro"),
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

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel(tr("monitor_policy_editor_mode")))
        self._mode_combo = QComboBox()
        self._mode_combo.addItem(tr("monitor_threshold_mode_noise"), "noise_relative")
        self._mode_combo.addItem(tr("monitor_threshold_mode_nominal"), "nominal_delta")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo, stretch=1)
        left_layout.addLayout(mode_row)

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
        font = self._preset_title.font()
        font.setBold(True)
        self._preset_title.setFont(font)
        right_layout.addWidget(self._preset_title)

        tool_row = QHBoxLayout()
        self._add_rule_btn = QPushButton(tr("monitor_policy_editor_add_rule"))
        self._add_rule_btn.clicked.connect(self._add_rule_row)
        self._remove_rule_btn = QPushButton(tr("monitor_policy_editor_remove_rule"))
        self._remove_rule_btn.clicked.connect(self._remove_selected_rules)
        tool_row.addWidget(self._add_rule_btn)
        tool_row.addWidget(self._remove_rule_btn)
        tool_row.addStretch(1)
        right_layout.addLayout(tool_row)

        self._table = QTableWidget(0, self._COL_COUNT)
        self._apply_headers()
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(self._COL_LABEL, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self._COL_THRESHOLD, QHeaderView.ResizeMode.ResizeToContents)
        for col in range(self._COL_FIRST_SEV, self._COL_COUNT):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
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

    def _apply_headers(self) -> None:
        headers = [tr("monitor_policy_col_alarm"), tr("monitor_policy_col_threshold")]
        for sev in EDITOR_SEVERITY_COLUMNS:
            headers.append(tr(SEVERITY_I18N_KEY[sev]))
        self._table.setHorizontalHeaderLabels(headers)

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
        idx = self._default_combo.findData(str(self._state.default_preset_id or "analog_standard"))
        if idx >= 0:
            self._default_combo.setCurrentIndex(idx)
        self._preset_list.blockSignals(False)
        self._default_combo.blockSignals(False)

    def _select_preset(self, preset_id: str) -> None:
        idx = self._preset_list.findData(preset_id)
        if idx >= 0:
            self._preset_list.setCurrentIndex(idx)

    def _current_preset(self) -> Optional[AlarmPreset]:
        return get_preset(str(self._preset_list.currentData() or ""), self._working_presets)

    def _on_preset_selected(self) -> None:
        if self._current_id and not self._loading:
            self._save_table_to_preset(self._current_id)
        preset_id = str(self._preset_list.currentData() or "")
        self._current_id = preset_id
        self._populate_table(preset_id)

    def _on_mode_changed(self) -> None:
        preset = self._current_preset()
        if preset is None or preset.is_builtin or self._loading:
            return
        preset.threshold_mode = str(self._mode_combo.currentData() or "noise_relative")

    def _populate_table(self, preset_id: str) -> None:
        preset = get_preset(preset_id, self._working_presets)
        if preset is None:
            return
        self._loading = True
        editable = not preset.is_builtin
        label = tr(preset.name_key) if preset.is_builtin else preset.name_key
        readonly = tr("monitor_preset_editor_builtin") if preset.is_builtin else tr("monitor_preset_editor_user")
        self._preset_title.setText(f"{label} — {readonly}")

        self._mode_combo.blockSignals(True)
        mode_idx = self._mode_combo.findData(preset.threshold_mode or "noise_relative")
        self._mode_combo.setCurrentIndex(mode_idx if mode_idx >= 0 else 0)
        self._mode_combo.setEnabled(editable)
        self._mode_combo.blockSignals(False)

        self._add_rule_btn.setEnabled(editable)
        self._remove_rule_btn.setEnabled(editable)

        rules = ensure_preset_rules(preset)
        self._row_widgets.clear()
        self._table.setRowCount(len(rules))
        mode = str(preset.threshold_mode or "noise_relative")

        for row_index, rule in enumerate(rules):
            self._build_row(row_index, rule, mode=mode, editable=editable)

        self._loading = False

    def _condition_options(self, mode: str) -> List[tuple[str, str]]:
        options: List[tuple[str, str]] = []
        pool = list(DROP_CONDITIONS) if mode == "nominal_delta" else list(BELOW_CONDITIONS)
        pool.append(COND_SYNC_LOST)
        for cond in pool:
            key = CONDITION_I18N.get(cond, cond)
            options.append((tr(key), cond))
        return options

    def _build_row(
        self,
        row_index: int,
        rule: AlarmPolicyRule,
        *,
        mode: str,
        editable: bool,
    ) -> None:
        cond_combo = QComboBox()
        for label, cond_id in self._condition_options(mode):
            cond_combo.addItem(label, cond_id)
        idx = cond_combo.findData(rule.condition_type)
        if idx >= 0:
            cond_combo.setCurrentIndex(idx)
        cond_combo.setEnabled(editable)

        threshold = QDoubleSpinBox()
        threshold.setRange(-120.0, 120.0)
        threshold.setDecimals(1)
        threshold.setSuffix(" dB")
        threshold.setEnabled(editable and rule.condition_type != COND_SYNC_LOST)
        if rule.threshold is not None:
            threshold.setValue(float(rule.threshold))

        radios: Dict[str, QRadioButton] = {}
        severity_group = QButtonGroup(self)
        for col_offset, sev in enumerate(EDITOR_SEVERITY_COLUMNS):
            radio = QRadioButton()
            radio.setEnabled(editable)
            severity_group.addButton(radio)
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.addWidget(radio)
            cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            self._table.setCellWidget(row_index, self._COL_FIRST_SEV + col_offset, cell)
            radios[sev] = radio
            if rule.severity == sev:
                radio.setChecked(True)
        if not any(radio.isChecked() for radio in radios.values()):
            radios["aviso"].setChecked(True)

        label_item = QTableWidgetItem(format_rule_label(rule, threshold_mode=mode, tr=tr))
        label_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self._table.setItem(row_index, self._COL_LABEL, label_item)
        self._table.setCellWidget(row_index, self._COL_THRESHOLD, threshold)

        def _refresh_label() -> None:
            if self._loading:
                return
            cond = str(cond_combo.currentData() or "")
            threshold.setEnabled(editable and cond != COND_SYNC_LOST)
            temp = self._rule_from_row(row_index)
            label_item.setText(format_rule_label(temp, threshold_mode=mode, tr=tr))

        cond_combo.currentIndexChanged.connect(lambda _i: _refresh_label())
        threshold.valueChanged.connect(lambda _v: _refresh_label())

        self._row_widgets.append(
            {
                "rule_id": rule.rule_id,
                "condition": cond_combo,
                "threshold": threshold,
                "radios": radios,
            }
        )

    def _rule_from_row(self, row_index: int) -> AlarmPolicyRule:
        editor = self._row_widgets[row_index]
        cond_combo: QComboBox = editor["condition"]
        threshold: QDoubleSpinBox = editor["threshold"]
        radios: Dict[str, QRadioButton] = editor["radios"]
        cond = str(cond_combo.currentData() or "")
        severity = "aviso"
        for sev, radio in radios.items():
            if radio.isChecked():
                severity = sev
                break
        value = None if cond == COND_SYNC_LOST else float(threshold.value())
        return AlarmPolicyRule(
            rule_id=str(editor.get("rule_id") or new_rule_id()),
            condition_type=cond,
            threshold=value,
            severity=severity,  # type: ignore[arg-type]
            enabled=True,
        )

    def _save_table_to_preset(self, preset_id: str) -> None:
        preset = get_preset(preset_id, self._working_presets)
        if preset is None or preset.is_builtin:
            return
        rules = [self._rule_from_row(i) for i in range(len(self._row_widgets))]
        mode = str(self._mode_combo.currentData() or "noise_relative")
        self._working_presets[preset_id] = AlarmPreset(
            preset_id=preset_id,
            name_key=preset.name_key,
            technology=preset.technology,
            rules=rules,
            checks=checks_from_rules(rules, threshold_mode=mode),
            is_builtin=False,
            threshold_mode=mode,
        )

    def _add_rule_row(self) -> None:
        preset = self._current_preset()
        if preset is None or preset.is_builtin:
            return
        mode = str(self._mode_combo.currentData() or "noise_relative")
        defaults = default_conditions_for_mode(mode, preset.technology)
        cond = defaults[0] if defaults else "snr_below"
        rule = AlarmPolicyRule(rule_id=new_rule_id(), condition_type=cond, threshold=6.0, severity="aviso")
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._build_row(row, rule, mode=mode, editable=True)

    def _remove_selected_rules(self) -> None:
        preset = self._current_preset()
        if preset is None or preset.is_builtin:
            return
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()}, reverse=True)
        for row in rows:
            if 0 <= row < len(self._row_widgets):
                self._row_widgets.pop(row)
            self._table.removeRow(row)

    def _duplicate_preset(self) -> None:
        source = self._current_preset()
        if source is None:
            return
        name, ok = self._prompt_text(tr("monitor_preset_editor_duplicate_name"), f"{tr(source.name_key)} copy")
        if not ok or not name.strip():
            return
        new_id = self._slugify(name)
        if get_preset(new_id, self._working_presets) is not None:
            QMessageBox.warning(self, tr("monitor_policy_editor_title"), tr("monitor_preset_editor_duplicate_exists"))
            return
        rules = clone_preset_rules(source)
        self._working_presets[new_id] = AlarmPreset(
            preset_id=new_id,
            name_key=name.strip(),
            technology=source.technology,
            rules=rules,
            checks=checks_from_rules(rules, threshold_mode=source.threshold_mode),
            is_builtin=False,
            threshold_mode=source.threshold_mode,
        )
        self._load_preset_list()
        self._current_id = ""
        self._select_preset(new_id)

    def _export_preset(self) -> None:
        preset = self._current_preset()
        if preset is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("monitor_preset_editor_export"),
            f"{preset.preset_id}.json",
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
            preset = AlarmPreset.from_dict(data if isinstance(data, dict) else {})
            preset = AlarmPreset(
                preset_id=preset.preset_id or self._slugify(path),
                name_key=preset.name_key,
                technology=preset.technology,
                rules=preset.rules,
                checks=preset.checks,
                is_builtin=False,
                threshold_mode=preset.threshold_mode,
            )
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            QMessageBox.warning(self, tr("monitor_policy_editor_title"), tr("monitor_preset_editor_import_error"))
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
            self._save_table_to_preset(self._current_id)
        self.accept()
