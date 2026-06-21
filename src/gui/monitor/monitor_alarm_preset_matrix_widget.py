"""Resumen de preset de umbrales activo en panel ALARMAS."""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from core.monitor.supervision.alarm_presets import (
    PRESET_ALARM_NORMAL,
    PRESET_ALARM_STRICT,
    get_preset,
    preset_display_name,
    resolve_active_alarm_preset_id,
    _user_presets_from_state,
)
from core.monitor.supervision.alarm_policy_rules import ensure_preset_rules, format_rule_summary
from core.monitor.supervision.supervision_models import SupervisionState
from i18n.json_translation import tr


class MonitorAlarmPresetMatrixWidget(QWidget):
    """Muestra el preset activo; la configuración completa está en el diálogo Umbrales."""

    state_changed = pyqtSignal(object)
    thresholds_requested = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._state = SupervisionState()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel(tr("monitor_preset_matrix_title"))
        title.setObjectName("MonitorPanelSectionTitle")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        hint = QLabel(tr("monitor_preset_matrix_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        self._normal_btn = QPushButton(tr("monitor_preset_alarm_normal"))
        self._strict_btn = QPushButton(tr("monitor_preset_alarm_strict"))
        for btn in (self._normal_btn, self._strict_btn):
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._normal_btn.clicked.connect(lambda: self._set_active_preset(PRESET_ALARM_NORMAL))
        self._strict_btn.clicked.connect(lambda: self._set_active_preset(PRESET_ALARM_STRICT))
        preset_row.addWidget(self._normal_btn, stretch=1)
        preset_row.addWidget(self._strict_btn, stretch=1)
        layout.addLayout(preset_row)

        row = QHBoxLayout()
        self._active_label = QLabel()
        self._active_label.setWordWrap(True)
        row.addWidget(self._active_label, stretch=1)
        self._open_btn = QPushButton(tr("monitor_thresholds_open"))
        self._open_btn.clicked.connect(lambda: self.thresholds_requested.emit({"scope": "global"}))
        row.addWidget(self._open_btn)
        layout.addLayout(row)

        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._summary.setObjectName("MonitorPresetActiveSummary")
        layout.addWidget(self._summary)

    def set_state(self, state: SupervisionState) -> None:
        self._state = state
        self._refresh()

    def get_state(self) -> SupervisionState:
        return self._state

    def _refresh(self) -> None:
        user_presets = _user_presets_from_state(self._state)
        active_id = resolve_active_alarm_preset_id(self._state)
        preset = get_preset(active_id, user_presets)
        if preset is None:
            self._active_label.setText(tr("monitor_thresholds_no_active"))
            self._summary.setText("")
            return
        name = preset_display_name(preset, tr=tr)
        mode_key = (
            "monitor_threshold_mode_nominal"
            if preset.threshold_mode == "nominal_delta"
            else "monitor_threshold_mode_noise"
        )
        self._active_label.setText(
            tr("monitor_thresholds_active_summary").format(name=name, mode=tr(mode_key))
        )
        rules = ensure_preset_rules(preset)
        self._summary.setText(
            format_rule_summary(rules, threshold_mode=preset.threshold_mode, tr=tr)
        )
        self._update_preset_buttons(active_id)

    def _update_preset_buttons(self, active_id: str) -> None:
        self._normal_btn.blockSignals(True)
        self._strict_btn.blockSignals(True)
        self._normal_btn.setChecked(active_id == PRESET_ALARM_NORMAL)
        self._strict_btn.setChecked(active_id == PRESET_ALARM_STRICT)
        self._normal_btn.blockSignals(False)
        self._strict_btn.blockSignals(False)

    def _set_active_preset(self, preset_id: str) -> None:
        if not preset_id:
            return
        self._state.active_alarm_preset_id = preset_id
        self._state.default_preset_id = preset_id
        self._refresh()
        self.state_changed.emit(self._state)

    def apply_user_presets(self, user_presets: dict) -> None:
        self._state.user_presets = dict(user_presets or {})
        self._refresh()
        self.state_changed.emit(self._state)

    def duplicate_builtin(self, preset_id: str, name: str) -> None:
        del preset_id, name

    def set_table_layout_changed_callback(self, callback: Callable[[], None] | None) -> None:
        del callback

    def save_table_header_state(self) -> str:
        return ""

    def apply_table_header_state(self, state: str) -> None:
        del state

    def recargar_textos(self) -> None:
        self._normal_btn.setText(tr("monitor_preset_alarm_normal"))
        self._strict_btn.setText(tr("monitor_preset_alarm_strict"))
        self._open_btn.setText(tr("monitor_thresholds_open"))
        self._refresh()
