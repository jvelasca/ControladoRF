"""Diálogo Umbrales — presets fundamentales + matriz fila×severidad."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QSize
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
    QInputDialog,
    QLabel,
    QMessageBox,
    QRadioButton,
    QSpinBox,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
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
    PRESET_ALARM_NORMAL_FM,
    AlarmPreset,
    get_preset,
    is_fundamental_preset,
    list_alarm_threshold_preset_options,
    preset_display_name,
    resolve_active_alarm_preset_id,
)
from core.monitor.supervision.alarm_severity import EDITOR_SEVERITY_COLUMNS, SEVERITY_I18N_KEY
from core.monitor.supervision.rules_resolver import clone_supervision_state
from core.monitor.supervision.supervision_models import SupervisionState
from gui.dialog_styles import apply_professional_dialog_style
from gui.monitor.monitor_info_button import MonitorInfoButton
from i18n.json_translation import tr

_TOOL_BTN_SIZE = QSize(22, 20)
_TOOL_ICON_SIZE = QSize(14, 14)


class MonitorAlarmThresholdsDialog(QDialog):
    """Umbrales: combo de preset + matriz condición × severidad (+ tiempos)."""

    _COL_ALARM = 0
    _COL_THRESHOLD = 1
    _COL_FIRST_SEV = 2
    _COL_DEBOUNCE = 6
    _COL_AUTO_CLEAR = 7
    _COL_COUNT = 8

    def __init__(
        self,
        state: SupervisionState,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._working = clone_supervision_state(state)
        self._user_presets: Dict[str, AlarmPreset] = {
            key: AlarmPreset.from_dict(value)
            for key, value in (self._working.user_presets or {}).items()
            if isinstance(value, dict)
        }
        self._selected_id = resolve_active_alarm_preset_id(self._working)
        self._loading = False
        self._row_widgets: List[dict] = []
        self.setWindowTitle(tr("monitor_thresholds_title"))
        apply_professional_dialog_style(self)
        self.resize(980, 620)
        self._build_ui()
        self._reload_preset_combo()
        self._select_preset(self._selected_id)
        if self._preset_combo.currentIndex() < 0 and self._preset_combo.count() > 0:
            self._preset_combo.setCurrentIndex(0)
        self._selected_id = str(self._preset_combo.currentData() or self._selected_id)
        self._populate_matrix()
        from gui.app_chrome_styles import apply_monitor_freq_manager_styles

        apply_monitor_freq_manager_styles(self)

    def get_state(self) -> SupervisionState:
        return self._working

    def _make_tool_button(self, icon: QStyle.StandardPixmap, tip: str) -> QToolButton:
        btn = QToolButton(self)
        btn.setObjectName("MonitorSupervisionToolBtn")
        style = self.style()
        if style is not None:
            btn.setIcon(style.standardIcon(icon))
        btn.setIconSize(_TOOL_ICON_SIZE)
        btn.setFixedSize(_TOOL_BTN_SIZE)
        btn.setToolTip(tip)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setAutoRaise(True)
        return btn

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel(tr("monitor_thresholds_title"))
        title.setObjectName("MonitorPanelSectionTitle")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        self._info = MonitorInfoButton(
            title_key="monitor_thresholds_title",
            body_key="monitor_thresholds_dialog_intro",
        )
        title_row.addWidget(title)
        title_row.addWidget(self._info, alignment=Qt.AlignmentFlag.AlignVCenter)
        title_row.addStretch(1)
        layout.addLayout(title_row)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel(tr("monitor_thresholds_preset_label")))
        self._preset_combo = QComboBox()
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self._preset_combo, stretch=1)
        layout.addLayout(preset_row)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(2)
        self._save_as_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_DialogSaveButton,
            tr("monitor_thresholds_save_as"),
        )
        self._duplicate_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_FileDialogNewFolder,
            tr("monitor_thresholds_duplicate"),
        )
        self._rename_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_FileDialogContentsView,
            tr("monitor_thresholds_rename"),
        )
        self._delete_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_TrashIcon,
            tr("monitor_thresholds_delete"),
        )
        self._export_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_DialogSaveButton,
            tr("monitor_preset_editor_export"),
        )
        self._import_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_DialogOpenButton,
            tr("monitor_preset_editor_import"),
        )
        self._add_rule_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            tr("monitor_policy_editor_add_rule"),
        )
        self._remove_rule_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_DialogCancelButton,
            tr("monitor_policy_editor_remove_rule"),
        )
        self._save_as_btn.clicked.connect(self._save_as)
        self._duplicate_btn.clicked.connect(self._duplicate_preset)
        self._rename_btn.clicked.connect(self._rename_preset)
        self._delete_btn.clicked.connect(self._delete_preset)
        self._export_btn.clicked.connect(self._export_preset)
        self._import_btn.clicked.connect(self._import_preset)
        self._add_rule_btn.clicked.connect(self._add_rule_row)
        self._remove_rule_btn.clicked.connect(self._remove_selected_rules)
        for btn in (
            self._save_as_btn,
            self._duplicate_btn,
            self._rename_btn,
            self._delete_btn,
            self._export_btn,
            self._import_btn,
            self._add_rule_btn,
            self._remove_rule_btn,
        ):
            toolbar.addWidget(btn)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self._fundamental_hint = QLabel(tr("monitor_thresholds_fundamental_hint"))
        self._fundamental_hint.setWordWrap(True)
        layout.addWidget(self._fundamental_hint)

        self._table = QTableWidget(0, self._COL_COUNT)
        self._apply_headers()
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(self._COL_ALARM, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self._COL_THRESHOLD, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self._COL_DEBOUNCE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self._COL_AUTO_CLEAR, QHeaderView.ResizeMode.ResizeToContents)
        for col in range(self._COL_FIRST_SEV, self._COL_DEBOUNCE):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self._table, stretch=1)

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
        headers.extend(
            [
                tr("monitor_thresholds_col_debounce"),
                tr("monitor_thresholds_col_auto_clear"),
            ]
        )
        self._table.setHorizontalHeaderLabels(headers)

    def _reload_preset_combo(self) -> None:
        self._preset_combo.blockSignals(True)
        self._preset_combo.clear()
        for preset_id in list_alarm_threshold_preset_options(self._user_presets):
            preset = get_preset(preset_id, self._user_presets)
            if preset is None:
                continue
            self._preset_combo.addItem(preset_display_name(preset, tr=tr), preset_id)
        self._preset_combo.blockSignals(False)

    def _select_preset(self, preset_id: str) -> None:
        idx = self._preset_combo.findData(preset_id)
        if idx >= 0:
            self._preset_combo.setCurrentIndex(idx)

    def _current_preset(self) -> Optional[AlarmPreset]:
        return get_preset(str(self._preset_combo.currentData() or ""), self._user_presets)

    def _on_preset_changed(self) -> None:
        if self._loading:
            return
        if self._selected_id and not is_fundamental_preset(self._selected_id):
            self._save_table_to_preset(self._selected_id)
        self._selected_id = str(self._preset_combo.currentData() or "")
        self._populate_matrix()

    def _populate_matrix(self) -> None:
        preset = self._current_preset()
        if preset is None:
            return
        self._loading = True
        is_fundamental = preset.is_fundamental
        self._fundamental_hint.setVisible(is_fundamental)
        self._rename_btn.setEnabled(not is_fundamental)
        self._delete_btn.setEnabled(not is_fundamental)
        self._add_rule_btn.setEnabled(not is_fundamental)
        self._remove_rule_btn.setEnabled(not is_fundamental)

        rules = ensure_preset_rules(preset)
        self._row_widgets.clear()
        self._table.setRowCount(len(rules))
        mode = str(preset.threshold_mode or "noise_relative")
        for row_index, rule in enumerate(rules):
            self._build_row(row_index, rule, mode=mode, editable=True)
        self._loading = False

    def _condition_options(self, mode: str) -> List[tuple[str, str]]:
        options: List[tuple[str, str]] = []
        pool = list(DROP_CONDITIONS) if mode == "nominal_delta" else list(BELOW_CONDITIONS)
        pool.append(COND_SYNC_LOST)
        for cond in pool:
            options.append((tr(CONDITION_I18N.get(cond, cond)), cond))
        return options

    def _build_row(self, row_index: int, rule: AlarmPolicyRule, *, mode: str, editable: bool) -> None:
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

        debounce = QSpinBox()
        debounce.setRange(0, 60_000)
        debounce.setSuffix(" ms")
        debounce.setSingleStep(100)
        debounce.setValue(int(rule.debounce_ms or 500))
        debounce.setEnabled(editable)

        auto_clear = QDoubleSpinBox()
        auto_clear.setRange(0.0, 3600.0)
        auto_clear.setDecimals(0)
        auto_clear.setSuffix(" s")
        auto_clear.setSpecialValueText("—")
        auto_clear.setValue(float(rule.auto_clear_s or 0.0))
        auto_clear.setEnabled(editable)

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
        if not any(r.isChecked() for r in radios.values()):
            radios["aviso"].setChecked(True)

        label_item = QTableWidgetItem(format_rule_label(rule, threshold_mode=mode, tr=tr))
        label_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self._table.setItem(row_index, self._COL_ALARM, label_item)
        self._table.setCellWidget(row_index, self._COL_THRESHOLD, threshold)
        self._table.setCellWidget(row_index, self._COL_DEBOUNCE, debounce)
        self._table.setCellWidget(row_index, self._COL_AUTO_CLEAR, auto_clear)

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
                "debounce": debounce,
                "auto_clear": auto_clear,
            }
        )

    def _rule_from_row(self, row_index: int) -> AlarmPolicyRule:
        editor = self._row_widgets[row_index]
        cond = str(editor["condition"].currentData() or "")
        severity = "aviso"
        for sev, radio in editor["radios"].items():
            if radio.isChecked():
                severity = sev
                break
        value = None if cond == COND_SYNC_LOST else float(editor["threshold"].value())
        debounce_val = int(editor["debounce"].value())
        auto_clear_val = float(editor["auto_clear"].value())
        return AlarmPolicyRule(
            rule_id=str(editor.get("rule_id") or new_rule_id()),
            condition_type=cond,
            threshold=value,
            severity=severity,  # type: ignore[arg-type]
            enabled=True,
            debounce_ms=debounce_val if debounce_val > 0 else None,
            auto_clear_s=auto_clear_val if auto_clear_val > 0 else None,
        )

    def _rules_from_table(self) -> List[AlarmPolicyRule]:
        return [self._rule_from_row(i) for i in range(len(self._row_widgets))]

    def _save_table_to_preset(self, preset_id: str) -> None:
        preset = get_preset(preset_id, self._user_presets)
        if preset is None or preset.is_fundamental:
            return
        rules = self._rules_from_table()
        mode = str(preset.threshold_mode or "noise_relative")
        self._user_presets[preset_id] = AlarmPreset(
            preset_id=preset_id,
            name_key=preset.name_key,
            technology=preset.technology,
            rules=rules,
            checks=checks_from_rules(rules, threshold_mode=mode),
            is_builtin=False,
            is_fundamental=False,
            threshold_mode=mode,
        )

    def _slugify(self, text: str) -> str:
        base = "".join(ch if ch.isalnum() else "_" for ch in text.lower()).strip("_")
        return base[:48] or "preset_custom"

    def _unique_preset_id(self, name: str) -> str:
        base = self._slugify(name)
        candidate = base
        suffix = 2
        while get_preset(candidate, self._user_presets) is not None:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    def _rules_for_save(self, source: AlarmPreset) -> List[AlarmPolicyRule]:
        del source
        return self._rules_from_table()

    def _save_as(self) -> bool:
        source = self._current_preset()
        if source is None:
            return False
        default_name = tr("monitor_thresholds_save_as_default").format(
            name=preset_display_name(source, tr=tr)
        )
        name, ok = QInputDialog.getText(
            self,
            tr("monitor_thresholds_save_as"),
            tr("monitor_preset_editor_name_label"),
            text=default_name,
        )
        if not ok or not name.strip():
            return False
        new_id = self._unique_preset_id(name.strip())
        rules = self._rules_for_save(source)
        mode = str(source.threshold_mode or "noise_relative")
        self._user_presets[new_id] = AlarmPreset(
            preset_id=new_id,
            name_key=name.strip(),
            technology=source.technology,
            rules=rules,
            checks=checks_from_rules(rules, threshold_mode=mode),
            is_builtin=False,
            threshold_mode=mode,
        )
        self._reload_preset_combo()
        self._selected_id = new_id
        self._select_preset(new_id)
        self._working.active_alarm_preset_id = new_id
        self._working.default_preset_id = new_id
        return True

    def _duplicate_preset(self) -> None:
        source = self._current_preset()
        if source is None:
            return
        if not source.is_fundamental:
            self._save_table_to_preset(source.preset_id)
            source = self._current_preset()
            if source is None:
                return
        default_name = tr("monitor_thresholds_duplicate_default").format(
            name=preset_display_name(source, tr=tr)
        )
        name, ok = QInputDialog.getText(
            self,
            tr("monitor_thresholds_duplicate"),
            tr("monitor_preset_editor_name_label"),
            text=default_name,
        )
        if not ok or not name.strip():
            return
        new_id = self._unique_preset_id(name.strip())
        rules = self._rules_for_save(source)
        mode = str(source.threshold_mode or "noise_relative")
        self._user_presets[new_id] = AlarmPreset(
            preset_id=new_id,
            name_key=name.strip(),
            technology=source.technology,
            rules=rules,
            checks=checks_from_rules(rules, threshold_mode=mode),
            is_builtin=False,
            threshold_mode=mode,
        )
        self._reload_preset_combo()
        self._selected_id = new_id
        self._select_preset(new_id)

    def _rename_preset(self) -> None:
        preset = self._current_preset()
        if preset is None or preset.is_fundamental:
            return
        name, ok = QInputDialog.getText(
            self,
            tr("monitor_thresholds_rename"),
            tr("monitor_preset_editor_name_label"),
            text=preset.name_key,
        )
        if not ok or not name.strip():
            return
        pid = preset.preset_id
        self._save_table_to_preset(pid)
        updated = self._user_presets[pid]
        self._user_presets[pid] = AlarmPreset(
            preset_id=pid,
            name_key=name.strip(),
            technology=updated.technology,
            rules=updated.rules,
            checks=updated.checks,
            is_builtin=False,
            threshold_mode=updated.threshold_mode,
        )
        self._reload_preset_combo()
        self._select_preset(pid)

    def _delete_preset(self) -> None:
        preset = self._current_preset()
        if preset is None or preset.is_fundamental:
            return
        pid = preset.preset_id
        if pid == resolve_active_alarm_preset_id(self._working):
            QMessageBox.warning(self, tr("monitor_thresholds_title"), tr("monitor_thresholds_delete_active"))
            return
        confirm = QMessageBox.question(
            self,
            tr("monitor_thresholds_delete"),
            tr("monitor_thresholds_delete_confirm").format(name=preset.name_key),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._user_presets.pop(pid, None)
        self._reload_preset_combo()
        self._select_preset(PRESET_ALARM_NORMAL_FM)

    def _export_preset(self) -> None:
        preset = self._current_preset()
        if preset is None:
            return
        if not preset.is_fundamental:
            self._save_table_to_preset(preset.preset_id)
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
            imported = AlarmPreset.from_dict(data if isinstance(data, dict) else {})
            new_id = self._unique_preset_id(imported.name_key or imported.preset_id or self._slugify(path))
            preset = AlarmPreset(
                preset_id=new_id,
                name_key=imported.name_key or new_id,
                technology=imported.technology,
                rules=imported.rules,
                checks=imported.checks,
                is_builtin=False,
                threshold_mode=imported.threshold_mode,
            )
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            QMessageBox.warning(self, tr("monitor_thresholds_title"), tr("monitor_preset_editor_import_error"))
            return
        self._user_presets[new_id] = preset
        self._reload_preset_combo()
        self._selected_id = new_id
        self._select_preset(new_id)

    def _add_rule_row(self) -> None:
        preset = self._current_preset()
        if preset is None or preset.is_fundamental:
            return
        mode = str(preset.threshold_mode or "noise_relative")
        defaults = default_conditions_for_mode(mode, preset.technology)
        rule = AlarmPolicyRule(
            rule_id=new_rule_id(),
            condition_type=defaults[0] if defaults else "snr_below",
            threshold=6.0,
            severity="aviso",
            debounce_ms=500,
        )
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._build_row(row, rule, mode=mode, editable=True)

    def _remove_selected_rules(self) -> None:
        preset = self._current_preset()
        if preset is None or preset.is_fundamental:
            return
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()}, reverse=True)
        for row in rows:
            if 0 <= row < len(self._row_widgets):
                self._row_widgets.pop(row)
            self._table.removeRow(row)

    def _commit_working_state(self, preset_id: str) -> None:
        if preset_id and not is_fundamental_preset(preset_id):
            self._save_table_to_preset(preset_id)
        self._working.user_presets = {
            key: item.to_dict() for key, item in self._user_presets.items()
        }
        if preset_id:
            self._working.active_alarm_preset_id = preset_id
            self._working.default_preset_id = preset_id

    def _accept(self) -> None:
        pid = str(self._preset_combo.currentData() or "")
        preset = self._current_preset()
        if preset is None:
            self.reject()
            return

        if preset.is_fundamental and self._table_is_dirty():
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle(tr("monitor_thresholds_title"))
            box.setText(tr("monitor_thresholds_fundamental_ok_prompt"))
            save_btn = box.addButton(
                tr("monitor_thresholds_save_as"),
                QMessageBox.ButtonRole.AcceptRole,
            )
            discard_btn = box.addButton(
                tr("monitor_thresholds_discard"),
                QMessageBox.ButtonRole.DestructiveRole,
            )
            cancel_btn = box.addButton(tr("cancel"), QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(save_btn)
            box.exec()
            clicked = box.clickedButton()
            if clicked is cancel_btn or clicked is None:
                return
            if clicked is save_btn:
                if not self._save_as():
                    return
                pid = str(self._preset_combo.currentData() or "")

        self._commit_working_state(pid)
        self.accept()

    def _table_is_dirty(self) -> bool:
        preset = self._current_preset()
        if preset is None or not preset.is_fundamental:
            return False
        current = self._rules_from_table()
        original = ensure_preset_rules(preset)
        if len(current) != len(original):
            return True
        for left, right in zip(current, original):
            if left.to_dict() != right.to_dict():
                return True
        return False


def edit_supervision_thresholds_dialog(
    state: SupervisionState,
    equipos: List[Dict[str, Any]] | None = None,
    *,
    initial_scope: str = "",
    initial_key: str = "",
    parent: Optional[QWidget] = None,
) -> SupervisionState | None:
    del equipos, initial_scope, initial_key
    dialog = MonitorAlarmThresholdsDialog(state, parent=parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.get_state()
