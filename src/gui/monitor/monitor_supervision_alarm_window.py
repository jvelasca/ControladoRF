"""Ventana flotante opcional del árbol de supervisión."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QWidget

from core.monitor.supervision.supervision_models import (
    AlarmDisplayRow,
    ResolvedSupervisionTarget,
    SupervisionChannelMetrics,
    SupervisionState,
)
from gui.monitor.monitor_alarmas_toolbar import MonitorAlarmasToolbarWidget
from gui.monitor.monitor_supervision_tree_widget import MonitorSupervisionTreeWidget
from i18n.json_translation import tr


class MonitorSupervisionAlarmWindow(QDialog):
    ack_all_requested = pyqtSignal()
    ack_channel_requested = pyqtSignal(str)
    highlight_channels_requested = pyqtSignal(list)
    locate_channels_requested = pyqtSignal(list)
    group_mode_changed = pyqtSignal(str)
    layout_changed = pyqtSignal(object)
    user_dismissed = pyqtSignal()
    supervision_enabled_changed = pyqtSignal(list, bool)
    history_requested = pyqtSignal()
    export_requested = pyqtSignal()
    thresholds_requested = pyqtSignal(object)
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
        self.setWindowTitle(tr("monitor_supervision_tree_title"))
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setMinimumSize(240, 280)
        self.resize(268, 420)
        self._pending_attention = 0
        self._persisted_expanded_groups: set[str] = set()
        self._persisted_scroll = 0
        self._force_close = False
        self._layout_save_timer = QTimer(self)
        self._layout_save_timer.setSingleShot(True)
        self._layout_save_timer.setInterval(350)
        self._layout_save_timer.timeout.connect(self._emit_layout_changed)
        self._build_ui()
        from gui.app_chrome_styles import apply_monitor_supervision_alarm_window_styles

        apply_monitor_supervision_alarm_window_styles(self)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        self._toolbar = MonitorAlarmasToolbarWidget()
        self._toolbar.popout_requested.connect(self._dismiss_floating_window)
        self._toolbar.thresholds_requested.connect(
            lambda: self.thresholds_requested.emit({"scope": "global"})
        )
        self._toolbar.rec_toggle_requested.connect(self.rec_toggle_requested.emit)
        self._toolbar.log_settings_requested.connect(self.log_settings_requested.emit)
        self._toolbar.last_log_requested.connect(self.last_log_requested.emit)
        layout.addWidget(self._toolbar)

        self._tree_panel = MonitorSupervisionTreeWidget(
            self,
            compact=True,
            embed_toolbar=False,
        )
        self._toolbar.bind_supervision_tree(self._tree_panel)
        self._tree_panel.ack_all_requested.connect(self.ack_all_requested.emit)
        self._tree_panel.ack_channel_requested.connect(self.ack_channel_requested.emit)
        self._tree_panel.highlight_channels_requested.connect(self.highlight_channels_requested.emit)
        self._tree_panel.locate_channels_requested.connect(self.locate_channels_requested.emit)
        self._tree_panel.group_mode_changed.connect(self._on_group_mode_changed)
        self._tree_panel.supervision_enabled_changed.connect(self.supervision_enabled_changed.emit)
        self._tree_panel.history_requested.connect(self.history_requested.emit)
        self._tree_panel.export_requested.connect(self.export_requested.emit)
        self._tree_panel.thresholds_requested.connect(self.thresholds_requested.emit)
        self._tree_panel.help_requested.connect(self.help_requested.emit)
        self._tree_panel.digital_mode_changed.connect(self.digital_mode_changed.emit)
        self._tree_panel.log_export_requested.connect(self.log_export_requested.emit)
        self._tree_panel.log_view_requested.connect(self.log_view_requested.emit)
        self._tree_panel.scope_thresholds_requested.connect(self.scope_thresholds_requested.emit)
        layout.addWidget(self._tree_panel, stretch=1)

    def restore_layout(self, layout: Dict[str, Any] | None) -> None:
        raw = layout or {}
        geometry_b64 = str(raw.get("geometry_b64") or raw.get("alarm_window_geometry_b64") or "")
        if geometry_b64:
            from gui.widget_geometry_utils import decode_widget_geometry

            decode_widget_geometry(self, geometry_b64)
        expanded = raw.get("expanded_groups") or raw.get("alarm_window_expanded_groups") or []
        self._persisted_expanded_groups = {str(key) for key in expanded if key}
        scroll = raw.get("scroll", raw.get("alarm_window_scroll", 0))
        try:
            self._persisted_scroll = max(0, int(scroll))
        except (TypeError, ValueError):
            self._persisted_scroll = 0

    def capture_layout(self) -> Dict[str, Any]:
        from gui.widget_geometry_utils import encode_widget_geometry

        tree = self._tree_panel._tree
        return {
            "geometry_b64": encode_widget_geometry(self),
            "expanded_groups": sorted(self._expanded_group_keys()),
            "scroll": int(tree.verticalScrollBar().value()),
        }

    def _expanded_group_keys(self) -> set[str]:
        keys: set[str] = set()
        tree = self._tree_panel._tree
        for index in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(index)
            if item is not None and item.isExpanded():
                keys.add(str(item.data(0, int(Qt.ItemDataRole.UserRole) + 1) or ""))
        return keys

    def set_group_mode(self, mode: str) -> None:
        self._tree_panel.set_group_mode(mode)

    def update_supervision(
        self,
        *,
        resolved: Sequence[ResolvedSupervisionTarget],
        equipos: list,
        alarm_states: dict[str, str],
        alarm_rows: Sequence[AlarmDisplayRow],
        channel_metrics: Optional[Dict[str, SupervisionChannelMetrics]] = None,
        supervision_state: SupervisionState | None = None,
        group_mode: str,
        pending_attention: int,
        log_path: str = "",
    ) -> None:
        self._pending_attention = pending_attention
        self._tree_panel.update_supervision(
            resolved=resolved,
            equipos=equipos,
            alarm_states=alarm_states,
            alarm_rows=alarm_rows,
            channel_metrics=channel_metrics,
            supervision_state=supervision_state,
            group_mode=group_mode,
            pending_attention=pending_attention,
            log_path=log_path,
        )
        self._update_title()

    def _update_title(self) -> None:
        base = tr("monitor_supervision_tree_title")
        if self._pending_attention > 0:
            title = tr("monitor_supervision_tree_title_pending").format(
                title=base,
                count=self._pending_attention,
            )
        else:
            title = base
        self.setWindowTitle(title)

    def trigger_locate_selected(self) -> bool:
        return self._tree_panel.trigger_locate_selected()

    def trigger_ack_selected(self) -> bool:
        return self._tree_panel.trigger_ack_selected()

    def set_rec_status(self, **kwargs) -> None:
        self._toolbar.set_rec_status(**kwargs)

    def _on_group_mode_changed(self, mode: str) -> None:
        self.group_mode_changed.emit(mode)
        self._schedule_layout_save()

    def _schedule_layout_save(self) -> None:
        self._layout_save_timer.start()

    def _emit_layout_changed(self) -> None:
        self.layout_changed.emit(self.capture_layout())

    def _dismiss_floating_window(self) -> None:
        self._emit_layout_changed()
        self.user_dismissed.emit()
        self.hide()

    def force_close(self) -> None:
        """Cierra de verdad la ventana (p. ej. al salir de la aplicación)."""
        self._force_close = True
        self.close()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if self.isVisible():
            self._schedule_layout_save()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.isVisible():
            self._schedule_layout_save()

    def closeEvent(self, event) -> None:
        from PyQt6.QtWidgets import QApplication

        self._emit_layout_changed()
        app = QApplication.instance()
        shutting_down = app is not None and app.closingDown()
        if self._force_close or shutting_down:
            event.accept()
            super().closeEvent(event)
            return
        self.user_dismissed.emit()
        event.ignore()
        self.hide()

    def reject(self) -> None:
        self._dismiss_floating_window()

    def recargar_textos(self) -> None:
        self._toolbar.recargar_textos()
        self._tree_panel.recargar_textos()
        self._update_title()
