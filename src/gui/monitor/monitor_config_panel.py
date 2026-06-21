"""Panel lateral Dispositivo del Monitor — acordeón principal + DEBUG anidado."""

from __future__ import annotations

from typing import Callable, List, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.developer_mode import read_developer_mode
from core.monitor.device_discovery import SourceDescriptor, get_default_source_id, idle_message_for_source
from core.monitor.sdr_setup import DeviceSetupReport
from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.device_probe_worker import MonitorDeviceProbeWorker, MonitorProbeResult
from gui.monitor.monitor_config_accordion import MonitorConfigAccordion
from gui.monitor.monitor_radio_panel import MonitorRadioPanel
from gui.monitor.monitor_recorder_panel import MonitorRecorderPanel
from gui.monitor.monitor_setup_dialog import MonitorSetupDialog
from gui.monitor.monitor_source_setup_widget import MonitorSourceSetupWidget
from i18n.json_translation import tr

_SCROLLABLE_SECTIONS = frozenset({"radio", "markers", "freq_manager", "alarmas", "display"})


class MonitorConfigPanel(QWidget):
    """Acordeón: DISPOSITIVO → RADIO → … → DEBUG (sub-acordeón instalación/diagnóstico)."""

    source_changed = pyqtSignal(str)
    demod_params_changed = pyqtSignal(object)
    audio_volume_changed = pyqtSignal(float)
    recorder_params_changed = pyqtSignal(object)
    markers_params_changed = pyqtSignal(object)
    display_params_changed = pyqtSignal(object)
    calibration_step_requested = pyqtSignal(object)
    active_marker_changed = pyqtSignal(int)
    supervision_changed = pyqtSignal(object)
    supervision_ack_all_requested = pyqtSignal()
    supervision_ack_channel_requested = pyqtSignal(str)
    supervision_show_events_requested = pyqtSignal()
    supervision_thresholds_requested = pyqtSignal(object)
    capture_reference_requested = pyqtSignal(str)
    capture_reference_bulk_requested = pyqtSignal(object)
    clear_reference_bulk_requested = pyqtSignal(object)
    record_toggled = pyqtSignal(bool)
    auto_tune_requested = pyqtSignal()
    fm_broadcast_requested = pyqtSignal()
    welle_cli_requested = pyqtSignal()
    mode_restriction = pyqtSignal(object)

    SECTION_KEYS = (
        "fuente",
        "radio",
        "freq_manager",
        "alarmas",
        "markers",
        "display",
        "debug",
    )
    DEBUG_SECTION_KEYS = ("setup", "diag")

    def __init__(self, module_id: str, panel_id: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.module_id = module_id
        self.panel_id = panel_id
        self._status_label: Optional[QLabel] = None
        self._source_combo: Optional[QComboBox] = None
        self._setup_widget: Optional[MonitorSourceSetupWidget] = None
        self._accordion: Optional[MonitorConfigAccordion] = None
        self._debug_accordion: Optional[MonitorConfigAccordion] = None
        self._debug_lock: Optional["DeveloperLockButton"] = None
        self._debug_locked_notice: Optional[QLabel] = None
        self._debug_content: Optional[QWidget] = None
        self._debug_header_layout: Optional[QHBoxLayout] = None
        self._get_config: Callable[[], dict] | None = None
        self._set_config: Callable[[dict], None] | None = None
        self._probe_worker: Optional[MonitorDeviceProbeWorker] = None
        self._radio_panel: Optional[MonitorRadioPanel] = None
        self._recorder_panel: Optional[MonitorRecorderPanel] = None
        self._markers_panel = None
        self._freq_manager_panel = None
        self._alarmas_panel = None
        self._display_panel = None
        self._get_equipos = None
        self._descriptors: List[SourceDescriptor] = []
        self._setup_reports: List[DeviceSetupReport] = []
        self._transport_busy: Optional[Callable[[], bool]] = None
        self._accordion_layout_cache: tuple = ()
        self._table_layout_persist: Optional[Callable[[], None]] = None
        self._build_ui()
        self.refresh_sources_async()

    def bind_developer_access(
        self,
        get_config: Callable[[], dict],
        set_config: Callable[[dict], None],
    ) -> None:
        from gui.developer_lock_button import DeveloperLockButton

        self._get_config = get_config
        self._set_config = set_config
        if self._debug_lock is not None:
            self._sync_debug_access()
            return
        self._debug_lock = DeveloperLockButton(
            get_config=get_config,
            set_config=set_config,
            parent=self,
        )
        self._debug_lock.unlocked_changed.connect(self._on_debug_lock_changed)
        if self._debug_header_layout is not None:
            self._debug_header_layout.addWidget(
                self._debug_lock, alignment=Qt.AlignmentFlag.AlignVCenter
            )
        self._sync_debug_access()

    def _on_debug_lock_changed(self, _unlocked: bool) -> None:
        self._sync_debug_access()

    def _sync_debug_access(self) -> None:
        get_config = getattr(self, "_get_config", None)
        unlocked = read_developer_mode(get_config()) if callable(get_config) else False
        if self._debug_content is not None:
            self._debug_content.setVisible(unlocked)
        if self._debug_locked_notice is not None:
            self._debug_locked_notice.setVisible(not unlocked)
        if self._debug_lock is not None:
            self._debug_lock.sync_from_config()

    def set_transport_busy_callback(self, callback: Callable[[], bool]) -> None:
        self._transport_busy = callback

    def set_equipos_provider(self, provider: Callable[[], list]) -> None:
        self._get_equipos = provider
        if self._freq_manager_panel is not None:
            self._freq_manager_panel.set_equipos_provider(provider)

    def _emit_source_change(self, source_id: str) -> None:
        if self._transport_busy is not None and self._transport_busy():
            return
        self.source_changed.emit(str(source_id))

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self._accordion = MonitorConfigAccordion(self)
        self._accordion.setObjectName("MonitorConfigAccordion")

        for key in self.SECTION_KEYS:
            if key == "fuente":
                page = self._build_fuente_section()
            elif key == "radio":
                page = self._build_radio_section()
            elif key == "recorder":
                page = self._build_recorder_section()
            elif key == "markers":
                page = self._build_markers_section()
            elif key == "freq_manager":
                page = self._build_freq_manager_section()
            elif key == "alarmas":
                page = self._build_alarmas_section()
            elif key == "display":
                page = self._build_display_section()
            elif key == "debug":
                page = self._build_debug_section()
            else:
                page = self._placeholder_section(key)
            scrollable = key in _SCROLLABLE_SECTIONS
            self._accordion.addSection(page, tr(f"monitor_cfg_{key}"), scrollable=scrollable)

        self._accordion.currentChanged.connect(self._on_main_section_changed)

        layout.addWidget(self._accordion, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        self._apply_accordion_styles()
        QTimer.singleShot(0, self._sync_accordion_layout)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._sync_accordion_layout)

    def refresh_layout_geometry(self) -> None:
        """Invalida medidas cacheadas tras colapsar/expandir el panel lateral."""
        self._accordion_layout_cache = ()
        self._sync_accordion_layout()

    def _apply_accordion_styles(self) -> None:
        from gui.app_chrome_styles import apply_monitor_config_toolbox_styles, apply_monitor_device_panel_hints

        if self._accordion is not None:
            apply_monitor_config_toolbox_styles(self._accordion)
        if self._debug_accordion is not None:
            apply_monitor_config_toolbox_styles(self._debug_accordion)
        apply_monitor_device_panel_hints(self)

    def _sync_accordion_layout(self) -> None:
        panel_h = max(self.height(), 240)
        idx = self._accordion.currentIndex() if self._accordion is not None else -1
        debug_open = (
            0 <= idx < len(self.SECTION_KEYS) and self.SECTION_KEYS[idx] == "debug"
        )
        if debug_open and self._debug_accordion is not None and self._accordion is not None:
            intro_reserve = 72
            nested_headers = self._debug_accordion.headers_height_hint()
            budget = max(
                140,
                panel_h - self._accordion.headers_height_hint() - intro_reserve - nested_headers,
            )
        else:
            budget = 280
        cache_key = (panel_h, idx, debug_open, budget)
        if cache_key == self._accordion_layout_cache:
            return
        self._accordion_layout_cache = cache_key
        if self._accordion is not None:
            self._accordion.update_viewport(panel_h)
        if self._debug_accordion is not None and debug_open:
            self._debug_accordion.update_viewport(budget)

    def _on_main_section_changed(self, _index: int) -> None:
        QTimer.singleShot(0, self._sync_accordion_layout)

    def _on_debug_section_changed(self, _index: int) -> None:
        QTimer.singleShot(0, self._sync_accordion_layout)

    def _build_fuente_section(self) -> QWidget:
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)
        outer.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinAndMaxSize)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._source_combo = QComboBox()
        self._source_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._source_combo.setMinimumContentsLength(14)
        self._source_combo.currentIndexChanged.connect(self._on_source_combo_changed)

        self._status_label = QLabel(tr("monitor_source_scanning"))
        self._status_label.setWordWrap(True)
        self._status_label.setObjectName("MonitorDeviceStatusLabel")

        form.addRow(tr("monitor_source_device"), self._source_combo)
        outer.addLayout(form)
        outer.addWidget(self._status_label)

        play_hint = QLabel(tr("monitor_cfg_fuente_play_hint"))
        play_hint.setWordWrap(True)
        play_hint.setObjectName("MonitorDevicePlayHint")
        outer.addWidget(play_hint)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        return content

    def _build_debug_section(self) -> QWidget:
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(6)
        outer.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinAndMaxSize)

        debug_header = QHBoxLayout()
        self._debug_header_layout = debug_header
        debug_title = QLabel(tr("monitor_cfg_debug"))
        debug_font = debug_title.font()
        debug_font.setBold(True)
        debug_title.setFont(debug_font)
        from gui.monitor.monitor_info_button import MonitorInfoButton

        debug_info = MonitorInfoButton(
            title_key="monitor_cfg_debug",
            body_key="monitor_cfg_debug_intro",
        )
        debug_header.addWidget(debug_title)
        debug_header.addWidget(debug_info, alignment=Qt.AlignmentFlag.AlignVCenter)
        debug_header.addStretch(1)
        outer.addLayout(debug_header)

        self._debug_locked_notice = QLabel(tr("monitor_cfg_debug_locked"))
        self._debug_locked_notice.setWordWrap(True)
        self._debug_locked_notice.setObjectName("MonitorDebugLockedNotice")
        outer.addWidget(self._debug_locked_notice)

        self._debug_content = QWidget(content)
        debug_outer = QVBoxLayout(self._debug_content)
        debug_outer.setContentsMargins(0, 0, 0, 0)
        debug_outer.setSpacing(6)

        self._debug_accordion = MonitorConfigAccordion(self._debug_content)
        self._debug_accordion.setObjectName("MonitorDebugAccordion")
        self._debug_accordion.currentChanged.connect(self._on_debug_section_changed)

        self._setup_widget = MonitorSourceSetupWidget(self._debug_content)
        self._setup_widget.recheck_requested.connect(
            lambda deep: self.refresh_sources_async(probe_backend=deep)
        )
        self._setup_widget.open_wizard_requested.connect(self._open_setup_wizard)

        self._debug_accordion.addSection(
            self._setup_widget,
            tr("monitor_cfg_debug_setup"),
            scrollable=True,
        )
        from gui.monitor.monitor_calibration_widget import MonitorCalibrationWidget

        self._calibration_widget = MonitorCalibrationWidget(self._debug_content)
        self._calibration_widget.calibration_step_requested.connect(
            self.calibration_step_requested.emit
        )
        self._debug_accordion.addSection(
            self._calibration_widget,
            tr("monitor_cfg_debug_diag"),
            scrollable=False,
        )
        debug_outer.addWidget(self._debug_accordion)
        outer.addWidget(self._debug_content)
        self._debug_locked_notice.setVisible(True)
        self._debug_content.setVisible(False)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        return content

    def _build_recorder_section(self) -> QWidget:
        self._recorder_panel = MonitorRecorderPanel()
        self._recorder_panel.params_changed.connect(self.recorder_params_changed.emit)
        self._recorder_panel.record_toggled.connect(self.record_toggled.emit)
        self._recorder_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        return self._recorder_panel

    def _build_markers_section(self) -> QWidget:
        from gui.monitor.monitor_markers_panel import MonitorMarkersPanel

        self._markers_panel = MonitorMarkersPanel()
        self._markers_panel.params_changed.connect(self.markers_params_changed.emit)
        self._markers_panel.active_marker_changed.connect(self.active_marker_changed.emit)
        self._markers_panel.set_table_layout_changed_callback(self._emit_table_layout_changed)
        self._markers_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        return self._markers_panel

    def _build_freq_manager_section(self) -> QWidget:
        from gui.monitor.monitor_freq_manager_panel import MonitorFreqManagerPanel

        self._freq_manager_panel = MonitorFreqManagerPanel()
        if self._get_equipos is not None:
            self._freq_manager_panel.set_equipos_provider(self._get_equipos)
        self._freq_manager_panel.state_changed.connect(self._on_supervision_panel_changed)
        self._freq_manager_panel.thresholds_requested.connect(self.supervision_thresholds_requested.emit)
        self._freq_manager_panel.capture_reference_requested.connect(self.capture_reference_requested.emit)
        self._freq_manager_panel.capture_reference_bulk_requested.connect(
            self.capture_reference_bulk_requested.emit
        )
        self._freq_manager_panel.clear_reference_bulk_requested.connect(
            self.clear_reference_bulk_requested.emit
        )
        self._freq_manager_panel.set_table_layout_changed_callback(self._emit_table_layout_changed)
        self._freq_manager_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        return self._freq_manager_panel

    def _build_display_section(self) -> QWidget:
        from gui.monitor.monitor_display_panel import MonitorDisplayPanel

        self._display_panel = MonitorDisplayPanel()
        self._display_panel.params_changed.connect(self.display_params_changed.emit)
        self._display_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        return self._display_panel

    def _build_alarmas_section(self) -> QWidget:
        from gui.monitor.monitor_alarmas_panel import MonitorAlarmasPanel

        self._alarmas_panel = MonitorAlarmasPanel()
        self._alarmas_panel.state_changed.connect(self._on_supervision_panel_changed)
        self._alarmas_panel.show_events_requested.connect(self.supervision_show_events_requested.emit)
        self._alarmas_panel.thresholds_requested.connect(self.supervision_thresholds_requested.emit)
        self._alarmas_panel.ack_all_requested.connect(self.supervision_ack_all_requested.emit)
        self._alarmas_panel.ack_channel_requested.connect(self.supervision_ack_channel_requested.emit)
        self._alarmas_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        return self._alarmas_panel

    def _on_supervision_panel_changed(self, _state) -> None:
        merged = self._merge_supervision_state()
        if self._freq_manager_panel is not None:
            self._freq_manager_panel.set_state(merged)
        if self._alarmas_panel is not None:
            self._alarmas_panel.set_state(merged)
        self.supervision_changed.emit(merged)

    def _merge_supervision_state(self):
        from core.monitor.supervision.supervision_models import SupervisionState

        if self._freq_manager_panel is None or self._alarmas_panel is None:
            return SupervisionState()
        freq = self._freq_manager_panel.get_state()
        alarm = self._alarmas_panel.get_state()
        merged = SupervisionState.from_dict(freq.to_dict())
        merged.settings = alarm.settings
        merged.rules = alarm.rules
        merged.user_presets = dict(alarm.user_presets or freq.user_presets or {})
        active = str(alarm.active_alarm_preset_id or freq.active_alarm_preset_id or "").strip()
        if not active:
            from core.monitor.supervision.alarm_presets import resolve_active_alarm_preset_id

            active = resolve_active_alarm_preset_id(alarm)
        merged.active_alarm_preset_id = active
        merged.default_preset_id = active or alarm.default_preset_id or freq.default_preset_id
        return merged

    def _build_radio_section(self) -> QWidget:
        self._radio_panel = MonitorRadioPanel()
        self._radio_panel.params_changed.connect(self.demod_params_changed.emit)
        self._radio_panel.audio_volume_changed.connect(self.audio_volume_changed.emit)
        self._radio_panel.auto_tune_requested.connect(self.auto_tune_requested.emit)
        self._radio_panel.fm_broadcast_requested.connect(self.fm_broadcast_requested.emit)
        self._radio_panel.welle_cli_requested.connect(self.welle_cli_requested.emit)
        self._radio_panel.mode_restriction.connect(self.mode_restriction.emit)
        self._radio_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        return self._radio_panel

    def _placeholder_section(
        self,
        section_key: str,
        *,
        placeholder_key: str | None = None,
    ) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinAndMaxSize)
        key = placeholder_key or f"monitor_cfg_{section_key}_placeholder"
        label = QLabel(tr(key))
        label.setWordWrap(True)
        layout.addWidget(label)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        return widget

    def _on_source_combo_changed(self, _index: int) -> None:
        if self._source_combo is None:
            return
        source_id = self._source_combo.currentData()
        if not source_id:
            return
        self._update_device_status(str(source_id))
        self._emit_source_change(str(source_id))

    def _update_device_status(self, source_id: str) -> None:
        if self._status_label is None:
            return
        text = tr("monitor_source_unknown")
        for item in self._descriptors:
            if item.source_id == source_id:
                idle = idle_message_for_source(source_id, descriptors=self._descriptors)
                detail = item.detail.strip()
                if detail and idle:
                    text = f"{detail} · {idle}"
                else:
                    text = detail or idle
                break
        if self._status_label.text() == text:
            return
        self._status_label.setText(text)
        if self._accordion is not None and self._accordion.currentIndex() == 0:
            QTimer.singleShot(0, self._sync_accordion_layout)

    def refresh_sources_async(self, probe_backend: bool = False) -> None:
        if self._probe_worker is not None and self._probe_worker.isRunning():
            return
        if self._status_label is not None:
            self._status_label.setText(tr("monitor_source_scanning"))
        self._probe_worker = MonitorDeviceProbeWorker(probe_backend=probe_backend, parent=self)
        self._probe_worker.finished_probe.connect(self._apply_probe_result)
        self._probe_worker.start()

    @pyqtSlot(object)
    def _apply_probe_result(self, result: object) -> None:
        if isinstance(result, MonitorProbeResult):
            self._descriptors = result.descriptors
            self._setup_reports = result.setup_reports
        elif isinstance(result, list):
            self._descriptors = result
            self._setup_reports = []
        else:
            return

        if self._setup_widget is not None:
            self._setup_widget.set_reports(self._setup_reports)

        combo = self._source_combo
        if combo is None:
            return

        previous_id = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for item in self._descriptors:
            label = item.display_name
            if item.is_default and item.available:
                label = f"{label} ★"
            if not item.available and item.device_family != "mock":
                label = f"{label} ({tr('monitor_source_unavailable')})"
            combo.addItem(label, item.source_id)
            if not item.available and item.device_family != "mock":
                idx = combo.count() - 1
                model = combo.model()
                if model is not None:
                    model_item = model.item(idx)
                    if model_item is not None:
                        model_item.setEnabled(False)

        selected_id = str(previous_id) if previous_id else get_default_source_id(descriptors=self._descriptors)
        idx = combo.findData(selected_id)
        if idx < 0 and combo.count() > 0:
            idx = 0
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.blockSignals(False)

        source_id = combo.currentData()
        if source_id:
            self._update_device_status(str(source_id))
            if str(source_id) != str(previous_id):
                self._emit_source_change(str(source_id))

    def _open_setup_wizard(self, device_id: str) -> None:
        dialog = MonitorSetupDialog(
            reports=self._setup_reports,
            focus_device_id=device_id,
            parent=self.window(),
        )
        dialog.exec()

    def set_status_message(self, message: str) -> None:
        if self._status_label is None:
            return
        if self._status_label.text() == message:
            return
        self._status_label.setText(message)

    def get_selected_source_id(self) -> str | None:
        if self._source_combo is None:
            return None
        source_id = self._source_combo.currentData()
        return str(source_id) if source_id else None

    def set_controls_busy(self, *, connecting: bool, running: bool) -> None:
        if self._source_combo is not None:
            self._source_combo.setEnabled(not connecting and not running)

    def set_monitor_params(
        self,
        params: SpectrumParams,
        *,
        prev: SpectrumParams | None = None,
    ) -> None:
        from core.monitor.monitor_flow_log import DISPLAY_PARAM_KEYS, RADIO_PANEL_KEYS, diff_param_keys

        if self._radio_panel is not None and (
            prev is None or diff_param_keys(prev, params, RADIO_PANEL_KEYS)
        ):
            self._radio_panel.set_params(params)
        if self._recorder_panel is not None:
            self._recorder_panel.set_params(params)
        if self._markers_panel is not None:
            self._markers_panel.set_params(params)
        if self._display_panel is not None and (
            prev is None or diff_param_keys(prev, params, DISPLAY_PARAM_KEYS)
        ):
            self._display_panel.set_params(params)

    def set_radio_audio_volume(self, volume: float) -> None:
        if self._radio_panel is not None:
            self._radio_panel.set_audio_volume_only(volume)

    def update_marker_trace(self, freqs, power) -> None:
        if self._markers_panel is not None:
            self._markers_panel.set_trace_snapshot(freqs, power)

    def set_supervision_state(self, state, *, alarm_counts=None, alarm_lines=None) -> None:
        if self._freq_manager_panel is not None:
            self._freq_manager_panel.set_state(state)
        if self._alarmas_panel is not None:
            self._alarmas_panel.set_state(state)

    def set_supervision_runtime(
        self,
        *,
        alarm_counts,
        alarm_lines,
        alarm_rows=None,
        pending_attention: int = 0,
        engine_active: bool = True,
    ) -> None:
        if self._alarmas_panel is not None:
            self._alarmas_panel.set_engine_active(engine_active)

    def update_supervision_tree(self, **kwargs) -> None:
        if self._alarmas_panel is not None:
            self._alarmas_panel.update_supervision_tree(**kwargs)

    def trigger_supervision_tree_locate(self) -> bool:
        if self._alarmas_panel is None:
            return False
        return self._alarmas_panel.trigger_tree_locate_selected()

    def trigger_supervision_tree_ack(self) -> bool:
        if self._alarmas_panel is None:
            return False
        return self._alarmas_panel.trigger_tree_ack_selected()

    def bind_calibration_controller(
        self,
        get_params: Callable[[], SpectrumParams],
        is_running: Callable[[], bool],
    ) -> None:
        if getattr(self, "_calibration_widget", None) is not None:
            self._calibration_widget.bind_controller(get_params, is_running)

    def bind_supervision_tree_controller(self, controller) -> None:
        if self._alarmas_panel is None:
            return
        panel = self._alarmas_panel
        panel.highlight_channels_requested.connect(controller._on_supervision_highlight_channels)
        panel.locate_channels_requested.connect(controller._on_supervision_locate_channels)
        panel.group_mode_changed.connect(controller._on_supervision_tree_group_changed)
        panel.supervision_enabled_changed.connect(controller._on_supervision_enabled_changed)
        panel.history_requested.connect(controller.show_supervision_events_dialog)
        panel.export_requested.connect(controller.export_supervision_events)
        panel.help_requested.connect(controller.show_supervision_help)
        panel.digital_mode_changed.connect(controller._on_supervision_digital_mode_changed)
        panel.log_export_requested.connect(controller.export_supervision_log_for_channels)
        panel.log_view_requested.connect(controller.show_supervision_log_view_dialog)
        panel.scope_thresholds_requested.connect(controller.show_supervision_scope_thresholds_dialog)
        panel.rec_toggle_requested.connect(controller.toggle_supervision_rec)
        panel.log_settings_requested.connect(controller.show_supervision_log_settings_dialog)
        panel.last_log_requested.connect(controller.open_last_supervision_log)

    def set_supervision_rec_status(self, **kwargs) -> None:
        if self._alarmas_panel is not None:
            self._alarmas_panel.set_rec_status(**kwargs)

    def focus_alarmas_panel(self) -> None:
        self.open_section("alarmas")

    def sync_tree_group_mode(self, mode: str) -> None:
        if self._alarmas_panel is not None:
            self._alarmas_panel.sync_tree_group_mode(mode)

    def open_section(self, section_key: str) -> None:
        if self._accordion is None:
            return
        try:
            index = self.SECTION_KEYS.index(section_key)
        except ValueError:
            return
        self._accordion.setCurrentIndex(index)

    def focus_markers_panel(self) -> None:
        self.open_section("markers")
        if self._markers_panel is not None:
            self._markers_panel.focus_active_marker()

    def update_recorder_state(self, params: SpectrumParams, *, recording: bool, running: bool) -> None:
        if self._recorder_panel is None:
            return
        self._recorder_panel.set_capture_ready(
            running=running,
            iq_mode=params.capture_mode == "iq",
            demod_active=params.demod_enabled(),
        )
        self._recorder_panel.set_recording_active(recording)

    def resolve_recorder_output_path(self, params: SpectrumParams):
        if self._recorder_panel is None:
            return None
        return self._recorder_panel.resolve_output_path(params)

    def update_demod_display(self, state) -> None:
        if self._radio_panel is not None:
            self._radio_panel.update_demod_state(state)

    def update_squelch_rf_level(self, rf_dbm: float) -> None:
        if self._radio_panel is not None:
            self._radio_panel.update_squelch_rf_level(rf_dbm)

    def update_demod_signal_level(self, level_dbfs: float | None) -> None:
        if self._radio_panel is not None:
            self._radio_panel.update_demod_signal_level(level_dbfs)

    def update_digital_analysis(self, state) -> None:
        if self._radio_panel is not None:
            self._radio_panel.update_digital_analysis(state)

    def update_rf_metrics(self, metrics) -> None:
        if self._radio_panel is not None:
            self._radio_panel.update_rf_metrics(metrics)

    def update_audio_output(self, *, active: bool, error: str = "") -> None:
        if self._radio_panel is not None:
            self._radio_panel.update_audio_output(active=active, error=error)

    def set_operating_mode(self, mode: str) -> None:
        if self._radio_panel is not None:
            self._radio_panel.set_operating_mode(mode)
            QTimer.singleShot(0, self._sync_accordion_layout)

    def recargar_textos(self) -> None:
        if self._accordion is not None:
            for index, key in enumerate(self.SECTION_KEYS):
                self._accordion.setItemText(index, tr(f"monitor_cfg_{key}"))
        if self._debug_accordion is not None:
            for index, key in enumerate(self.DEBUG_SECTION_KEYS):
                self._debug_accordion.setItemText(index, tr(f"monitor_cfg_debug_{key}"))
        if self._debug_lock is not None:
            self._debug_lock.recargar_textos()
        if self._debug_locked_notice is not None:
            self._debug_locked_notice.setText(tr("monitor_cfg_debug_locked"))
        if self._setup_widget is not None:
            self._setup_widget.recargar_textos()
        if getattr(self, "_calibration_widget", None) is not None:
            self._calibration_widget.recargar_textos()
        if self._radio_panel is not None:
            self._radio_panel.recargar_textos()
        if self._recorder_panel is not None:
            self._recorder_panel.recargar_textos()
        if self._markers_panel is not None:
            self._markers_panel.recargar_textos()
        if self._freq_manager_panel is not None:
            self._freq_manager_panel.recargar_textos()
        if self._alarmas_panel is not None:
            self._alarmas_panel.recargar_textos()
        if self._display_panel is not None:
            self._display_panel.recargar_textos()
        self.refresh_sources_async()
        QTimer.singleShot(0, self._sync_accordion_layout)

    def apply_visual_theme(self, _style_key: str) -> None:
        self._apply_accordion_styles()

    def bind_table_layout_persist(self, callback: Optional[Callable[[], None]]) -> None:
        self._table_layout_persist = callback
        if self._markers_panel is not None:
            self._markers_panel.set_table_layout_changed_callback(self._emit_table_layout_changed)
        if self._freq_manager_panel is not None:
            self._freq_manager_panel.set_table_layout_changed_callback(self._emit_table_layout_changed)
        if self._alarmas_panel is not None:
            self._alarmas_panel.set_table_layout_changed_callback(self._emit_table_layout_changed)

    def save_persisted_table_layout(self) -> dict:
        layout: dict = {}
        if self._freq_manager_panel is not None:
            header = self._freq_manager_panel.save_table_header_state()
            if header:
                layout["freq_manager_table_header"] = header
        if self._markers_panel is not None:
            header = self._markers_panel.save_table_header_state()
            if header:
                layout["markers_table_header"] = header
        if self._alarmas_panel is not None:
            header = self._alarmas_panel.save_table_header_state()
            if header:
                layout["alarmas_preset_matrix_header"] = header
        return layout

    def apply_persisted_table_layout(self, data: dict) -> None:
        if not isinstance(data, dict):
            return
        if self._freq_manager_panel is not None:
            header = data.get("freq_manager_table_header")
            if isinstance(header, str):
                self._freq_manager_panel.apply_table_header_state(header)
        if self._markers_panel is not None:
            header = data.get("markers_table_header")
            if isinstance(header, str):
                self._markers_panel.apply_table_header_state(header)
        if self._alarmas_panel is not None:
            header = data.get("alarmas_preset_matrix_header")
            if isinstance(header, str):
                self._alarmas_panel.apply_table_header_state(header)

    def _emit_table_layout_changed(self) -> None:
        if self._table_layout_persist is not None:
            self._table_layout_persist()
