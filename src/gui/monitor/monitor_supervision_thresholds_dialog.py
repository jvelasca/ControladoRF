"""Diálogo de umbrales de supervisión RF — global, fabricante, modelo y canal."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.monitor.supervision.rules_resolver import (
    SCOPE_CHANNEL,
    SCOPE_DEVICE_TYPE,
    SCOPE_GLOBAL,
    SCOPE_MANUFACTURER,
    SCOPE_MODEL,
    SCOPE_ZONE,
    THRESHOLD_SCOPES,
    clear_rule_override,
    clone_supervision_state,
    collect_scope_options,
    has_rule_override,
    resolve_rules_for_scope,
    set_rule_override,
    validate_mer_rules,
    validate_rules,
)
from core.monitor.supervision.supervision_models import SupervisionRules, SupervisionState
from core.monitor.supervision.digital_supervision import (
    digital_metrics_enabled_for_mode,
    digital_supervision_mode_from_rules,
    is_digital_modulation_class,
)
from gui.dialog_styles import apply_professional_dialog_style, build_dialog_header
from i18n.json_translation import tr

_SCOPE_I18N = {
    SCOPE_GLOBAL: "monitor_thresholds_scope_global",
    SCOPE_ZONE: "monitor_thresholds_scope_zone",
    SCOPE_DEVICE_TYPE: "monitor_thresholds_scope_device_type",
    SCOPE_MANUFACTURER: "monitor_thresholds_scope_manufacturer",
    SCOPE_MODEL: "monitor_thresholds_scope_model",
    SCOPE_CHANNEL: "monitor_thresholds_scope_channel",
}


class MonitorSupervisionThresholdsDialog(QDialog):
    def __init__(
        self,
        state: SupervisionState,
        equipos: List[Dict[str, Any]],
        *,
        initial_scope: str = SCOPE_GLOBAL,
        initial_key: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._working = clone_supervision_state(state)
        self._equipos = list(equipos or [])
        self._scope_options = collect_scope_options(self._equipos, tr=tr)
        self._initial_scope = initial_scope if initial_scope in THRESHOLD_SCOPES else SCOPE_GLOBAL
        self._initial_key = str(initial_key or "")
        self._loading = False
        self.setWindowTitle(tr("monitor_thresholds_title"))
        apply_professional_dialog_style(self)
        self.resize(520, 480)
        self._build_ui()
        self._select_initial_scope()

    def get_state(self) -> SupervisionState:
        return self._working

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(
            build_dialog_header(
                tr("monitor_thresholds_title"),
                tr("monitor_thresholds_intro"),
            )
        )

        selector_row = QHBoxLayout()
        self._scope = QComboBox()
        for scope in THRESHOLD_SCOPES:
            self._scope.addItem(tr(_SCOPE_I18N[scope]), scope)
        self._scope.currentIndexChanged.connect(self._on_scope_changed)

        self._entity = QComboBox()
        self._entity.currentIndexChanged.connect(self._load_editor_values)

        selector_row.addWidget(QLabel(tr("monitor_thresholds_scope_label")))
        selector_row.addWidget(self._scope, stretch=1)
        selector_row.addWidget(self._entity, stretch=2)
        layout.addLayout(selector_row)

        self._inherit_label = QLabel()
        self._inherit_label.setWordWrap(True)
        self._inherit_label.setObjectName("MonitorThresholdsInheritLabel")
        layout.addWidget(self._inherit_label)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._warning = QDoubleSpinBox()
        self._warning.setRange(0.0, 60.0)
        self._warning.setDecimals(1)
        self._warning.setSingleStep(0.5)
        self._warning.setSuffix(" dB")
        self._warning.valueChanged.connect(self._update_effective_preview)

        self._critical = QDoubleSpinBox()
        self._critical.setRange(0.0, 60.0)
        self._critical.setDecimals(1)
        self._critical.setSingleStep(0.5)
        self._critical.setSuffix(" dB")
        self._critical.valueChanged.connect(self._update_effective_preview)

        self._debounce = QSpinBox()
        self._debounce.setRange(0, 10_000)
        self._debounce.setSingleStep(50)
        self._debounce.setSuffix(" ms")

        form.addRow(tr("monitor_thresholds_warning"), self._warning)
        form.addRow(tr("monitor_thresholds_critical"), self._critical)
        form.addRow(tr("monitor_thresholds_debounce"), self._debounce)

        self._digital_mode = QComboBox()
        self._digital_mode.addItem(tr("monitor_thresholds_digital_mode_snr_only"), "snr_only")
        self._digital_mode.addItem(tr("monitor_thresholds_digital_mode_snr_mer"), "snr_and_mer")
        self._digital_mode.currentIndexChanged.connect(self._on_digital_mode_changed)

        self._mer_warning = QDoubleSpinBox()
        self._mer_warning.setRange(0.0, 60.0)
        self._mer_warning.setDecimals(1)
        self._mer_warning.setSingleStep(0.5)
        self._mer_warning.setSuffix(" dB")
        self._mer_warning.valueChanged.connect(self._update_effective_preview)

        self._mer_critical = QDoubleSpinBox()
        self._mer_critical.setRange(0.0, 60.0)
        self._mer_critical.setDecimals(1)
        self._mer_critical.setSingleStep(0.5)
        self._mer_critical.setSuffix(" dB")
        self._mer_critical.valueChanged.connect(self._update_effective_preview)

        self._digital_debounce = QSpinBox()
        self._digital_debounce.setRange(0, 10_000)
        self._digital_debounce.setSingleStep(50)
        self._digital_debounce.setSuffix(" ms")
        self._digital_debounce.valueChanged.connect(self._update_effective_preview)

        form.addRow(tr("monitor_thresholds_digital_mode"), self._digital_mode)
        form.addRow(tr("monitor_thresholds_mer_warning"), self._mer_warning)
        form.addRow(tr("monitor_thresholds_mer_critical"), self._mer_critical)
        form.addRow(tr("monitor_thresholds_digital_debounce"), self._digital_debounce)
        layout.addLayout(form)

        self._effective_label = QLabel()
        self._effective_label.setWordWrap(True)
        layout.addWidget(self._effective_label)

        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        self._reset_btn = QPushButton(tr("monitor_thresholds_reset"))
        self._reset_btn.clicked.connect(self._on_reset)
        reset_row.addWidget(self._reset_btn)
        layout.addLayout(reset_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _select_initial_scope(self) -> None:
        scope_idx = self._scope.findData(self._initial_scope)
        if scope_idx < 0:
            scope_idx = 0
        self._scope.setCurrentIndex(scope_idx)
        if self._initial_key:
            entity_idx = self._entity.findData(self._initial_key)
            if entity_idx >= 0:
                self._entity.setCurrentIndex(entity_idx)
        self._load_editor_values()

    def _current_scope(self) -> str:
        scope = self._scope.currentData()
        return scope if scope in THRESHOLD_SCOPES else SCOPE_GLOBAL

    def _current_key(self) -> str:
        if self._current_scope() == SCOPE_GLOBAL:
            return ""
        return str(self._entity.currentData() or "")

    def _on_scope_changed(self, _index: int) -> None:
        self._populate_entity_combo()
        self._load_editor_values()

    def _populate_entity_combo(self) -> None:
        self._loading = True
        try:
            scope = self._current_scope()
            self._entity.blockSignals(True)
            self._entity.clear()
            if scope == SCOPE_GLOBAL:
                self._entity.setEnabled(False)
                self._entity.addItem(tr("monitor_thresholds_scope_global"), "")
            else:
                self._entity.setEnabled(True)
                options = self._scope_options.get(scope, [])
                if not options:
                    self._entity.addItem(tr("monitor_thresholds_no_items"), "")
                    self._entity.setEnabled(False)
                else:
                    for key, label in options:
                        self._entity.addItem(label, key)
            self._entity.blockSignals(False)
        finally:
            self._loading = False

    def _load_editor_values(self) -> None:
        if self._loading:
            return
        scope = self._current_scope()
        key = self._current_key()
        rules = resolve_rules_for_scope(self._working, scope, key, equipos=self._equipos)
        self._loading = True
        try:
            self._warning.setValue(float(rules.warning_above_noise_db))
            self._critical.setValue(float(rules.critical_above_noise_db))
            self._debounce.setValue(int(rules.debounce_ms))
            self._set_digital_mode_ui(rules)
            self._mer_warning.setValue(float(rules.mer_warning_db))
            self._mer_critical.setValue(float(rules.mer_critical_db))
            self._digital_debounce.setValue(int(rules.digital_debounce_ms))
        finally:
            self._loading = False
        self._update_digital_section_visibility(scope, key)
        self._update_inherit_label(scope, key)
        self._update_effective_preview()
        self._reset_btn.setEnabled(scope != SCOPE_GLOBAL and bool(key) and has_rule_override(self._working, scope, key))

    def _set_digital_mode_ui(self, rules: SupervisionRules) -> None:
        mode = digital_supervision_mode_from_rules(bool(rules.digital_metrics_enabled))
        idx = self._digital_mode.findData(mode)
        if idx >= 0:
            self._digital_mode.setCurrentIndex(idx)
        mer_enabled = bool(rules.digital_metrics_enabled)
        self._mer_warning.setEnabled(mer_enabled)
        self._mer_critical.setEnabled(mer_enabled)
        self._digital_debounce.setEnabled(mer_enabled)

    def _digital_metrics_enabled_from_ui(self) -> bool:
        mode = self._digital_mode.currentData()
        return digital_metrics_enabled_for_mode(mode if mode in ("snr_only", "snr_and_mer") else "snr_and_mer")

    def _update_digital_section_visibility(self, scope: str, key: str) -> None:
        show_digital = True
        if scope == SCOPE_CHANNEL and key:
            equipo = next(
                (item for item in self._equipos if str(item.get("channel_key") or "") == key),
                {},
            )
            modulation = str(equipo.get("modulation_class") or "analog_fm")
            show_digital = is_digital_modulation_class(modulation)
        self._digital_mode.setVisible(show_digital or scope != SCOPE_CHANNEL or not key)
        mer_visible = (show_digital or scope != SCOPE_CHANNEL or not key) and self._digital_metrics_enabled_from_ui()
        self._mer_warning.setEnabled(mer_visible)
        self._mer_critical.setEnabled(mer_visible)
        self._digital_debounce.setEnabled(mer_visible)

    def _on_digital_mode_changed(self, _index: int) -> None:
        if self._loading:
            return
        mer_enabled = self._digital_metrics_enabled_from_ui()
        self._mer_warning.setEnabled(mer_enabled)
        self._mer_critical.setEnabled(mer_enabled)
        self._digital_debounce.setEnabled(mer_enabled)
        self._update_effective_preview()

    def _update_inherit_label(self, scope: str, key: str) -> None:
        if scope == SCOPE_GLOBAL:
            self._inherit_label.setText(tr("monitor_thresholds_global_hint"))
            return
        if not key:
            self._inherit_label.setText(tr("monitor_thresholds_no_items"))
            return
        if has_rule_override(self._working, scope, key):
            self._inherit_label.setText(tr("monitor_thresholds_custom_hint"))
        else:
            self._inherit_label.setText(tr("monitor_thresholds_inherited_hint"))

    def _update_effective_preview(self) -> None:
        scope = self._current_scope()
        key = self._current_key()
        preview_rules = SupervisionRules(
            warning_above_noise_db=float(self._warning.value()),
            critical_above_noise_db=float(self._critical.value()),
            debounce_ms=int(self._debounce.value()),
            digital_metrics_enabled=self._digital_metrics_enabled_from_ui(),
            mer_warning_db=float(self._mer_warning.value()),
            mer_critical_db=float(self._mer_critical.value()),
            digital_debounce_ms=int(self._digital_debounce.value()),
        )
        if scope == SCOPE_CHANNEL and key:
            effective = preview_rules
        else:
            temp = clone_supervision_state(self._working)
            if scope == SCOPE_GLOBAL:
                temp.rules = preview_rules
                effective = temp.rules
            elif key:
                set_rule_override(temp, scope, key, preview_rules)
                effective = resolve_rules_for_scope(temp, scope, key, equipos=self._equipos)
            else:
                effective = preview_rules
        self._effective_label.setText(
            tr("monitor_thresholds_effective").format(
                warning=f"{effective.warning_above_noise_db:.1f}",
                critical=f"{effective.critical_above_noise_db:.1f}",
                debounce=int(effective.debounce_ms),
                mer_warning=f"{effective.mer_warning_db:.1f}",
                mer_critical=f"{effective.mer_critical_db:.1f}",
                digital_debounce=int(effective.digital_debounce_ms),
                digital_on=tr(
                    "monitor_thresholds_digital_mode_snr_mer"
                    if effective.digital_metrics_enabled
                    else "monitor_thresholds_digital_mode_snr_only"
                ),
            )
        )

    def _on_reset(self) -> None:
        scope = self._current_scope()
        key = self._current_key()
        if scope == SCOPE_GLOBAL or not key:
            return
        clear_rule_override(self._working, scope, key)
        self._load_editor_values()

    def _on_accept(self) -> None:
        warning = float(self._warning.value())
        critical = float(self._critical.value())
        if not validate_rules(warning, critical):
            QMessageBox.warning(
                self,
                tr("monitor_thresholds_title"),
                tr("monitor_thresholds_invalid_order"),
            )
            return
        mer_warning = float(self._mer_warning.value())
        mer_critical = float(self._mer_critical.value())
        if not validate_mer_rules(mer_warning, mer_critical):
            QMessageBox.warning(
                self,
                tr("monitor_thresholds_title"),
                tr("monitor_thresholds_invalid_mer_order"),
            )
            return
        rules = SupervisionRules(
            warning_above_noise_db=warning,
            critical_above_noise_db=critical,
            carrier_loss_margin_db=self._working.rules.carrier_loss_margin_db,
            debounce_ms=int(self._debounce.value()),
            digital_metrics_enabled=self._digital_metrics_enabled_from_ui(),
            mer_warning_db=mer_warning,
            mer_critical_db=mer_critical,
            digital_debounce_ms=int(self._digital_debounce.value()),
        )
        scope = self._current_scope()
        key = self._current_key()
        if scope == SCOPE_GLOBAL:
            self._working.rules = rules
        elif key:
            set_rule_override(self._working, scope, key, rules)
        else:
            QMessageBox.warning(
                self,
                tr("monitor_thresholds_title"),
                tr("monitor_thresholds_no_items"),
            )
            return
        self.accept()


def edit_supervision_thresholds_dialog(
    state: SupervisionState,
    equipos: List[Dict[str, Any]],
    *,
    initial_scope: str = SCOPE_GLOBAL,
    initial_key: str = "",
    parent: Optional[QWidget] = None,
) -> SupervisionState | None:
    dialog = MonitorSupervisionThresholdsDialog(
        state,
        equipos,
        initial_scope=initial_scope,
        initial_key=initial_key,
        parent=parent,
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.get_state()
