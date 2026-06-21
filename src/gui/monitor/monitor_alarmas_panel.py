"""Panel ALARMAS — árbol de supervisión con barra de herramientas compacta."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.monitor.supervision.supervision_models import SupervisionState
from gui.monitor.monitor_alarmas_toolbar import MonitorAlarmasToolbarWidget
from gui.monitor.monitor_supervision_tree_widget import MonitorSupervisionTreeWidget
from i18n.json_translation import tr


class MonitorAlarmasPanel(QWidget):
    state_changed = pyqtSignal(object)
    show_events_requested = pyqtSignal()
    thresholds_requested = pyqtSignal(object)
    ack_all_requested = pyqtSignal()
    ack_channel_requested = pyqtSignal(str)
    highlight_channels_requested = pyqtSignal(list)
    locate_channels_requested = pyqtSignal(list)
    group_mode_changed = pyqtSignal(str)
    supervision_enabled_changed = pyqtSignal(list, bool)
    history_requested = pyqtSignal()
    export_requested = pyqtSignal()
    help_requested = pyqtSignal()
    digital_mode_changed = pyqtSignal(str, bool)
    log_export_requested = pyqtSignal(list)
    log_view_requested = pyqtSignal(object)
    scope_thresholds_requested = pyqtSignal(object)
    rec_toggle_requested = pyqtSignal()
    log_settings_requested = pyqtSignal()
    last_log_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._state = SupervisionState()
        self._engine_active = False
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        self._toolbar = MonitorAlarmasToolbarWidget()
        self._toolbar.popout_requested.connect(self.show_events_requested.emit)
        self._toolbar.thresholds_requested.connect(
            lambda: self.thresholds_requested.emit({"scope": "global"})
        )
        self._toolbar.rec_toggle_requested.connect(self.rec_toggle_requested.emit)
        self._toolbar.log_settings_requested.connect(self.log_settings_requested.emit)
        self._toolbar.last_log_requested.connect(self.last_log_requested.emit)
        outer.addWidget(self._toolbar)

        self._supervision_tree = MonitorSupervisionTreeWidget(
            compact=True,
            embed_toolbar=False,
        )
        self._toolbar.bind_supervision_tree(self._supervision_tree)
        self._supervision_tree.setMinimumHeight(240)
        self._supervision_tree.highlight_channels_requested.connect(
            self.highlight_channels_requested.emit
        )
        self._supervision_tree.locate_channels_requested.connect(
            self.locate_channels_requested.emit
        )
        self._supervision_tree.group_mode_changed.connect(self.group_mode_changed.emit)
        self._supervision_tree.supervision_enabled_changed.connect(
            self.supervision_enabled_changed.emit
        )
        self._supervision_tree.ack_all_requested.connect(self.ack_all_requested.emit)
        self._supervision_tree.ack_channel_requested.connect(self.ack_channel_requested.emit)
        self._supervision_tree.thresholds_requested.connect(self.thresholds_requested.emit)
        self._supervision_tree.history_requested.connect(self.history_requested.emit)
        self._supervision_tree.export_requested.connect(self.export_requested.emit)
        self._supervision_tree.help_requested.connect(self.help_requested.emit)
        self._supervision_tree.digital_mode_changed.connect(self.digital_mode_changed.emit)
        self._supervision_tree.log_export_requested.connect(self.log_export_requested.emit)
        self._supervision_tree.log_view_requested.connect(self.log_view_requested.emit)
        self._supervision_tree.scope_thresholds_requested.connect(self.scope_thresholds_requested.emit)
        outer.addWidget(self._supervision_tree, stretch=1)

        self._pending_note = QLabel(tr("monitor_alarmas_engine_pending"))
        self._pending_note.setWordWrap(True)
        outer.addWidget(self._pending_note)

    def set_table_layout_changed_callback(self, callback) -> None:
        del callback

    def save_table_header_state(self) -> str:
        return ""

    def apply_table_header_state(self, state: str) -> None:
        del state

    def set_state(self, state: SupervisionState) -> None:
        self._state = state
        self._supervision_tree.set_group_mode(state.settings.tree_group_mode)

    def set_engine_active(self, active: bool) -> None:
        self._engine_active = active
        self._pending_note.setVisible(not active)

    def update_supervision_tree(self, **kwargs) -> None:
        self._supervision_tree.update_supervision(**kwargs)

    def trigger_tree_locate_selected(self) -> bool:
        return self._supervision_tree.trigger_locate_selected()

    def trigger_tree_ack_selected(self) -> bool:
        return self._supervision_tree.trigger_ack_selected()

    def sync_tree_group_mode(self, mode: str) -> None:
        self._state.settings.tree_group_mode = mode
        self._supervision_tree.set_group_mode(mode)

    def set_rec_status(self, **kwargs) -> None:
        self._toolbar.set_rec_status(**kwargs)

    def get_state(self) -> SupervisionState:
        return self._state

    def recargar_textos(self) -> None:
        self._toolbar.recargar_textos()
        self._supervision_tree.recargar_textos()
        self._pending_note.setText(tr("monitor_alarmas_engine_pending"))
