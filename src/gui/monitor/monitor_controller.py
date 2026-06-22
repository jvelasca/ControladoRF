"""Controlador del módulo Monitor — enlaza motor FFT y widgets."""
from __future__ import annotations

import threading
import time
from typing import Optional

import math

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.monitor.device_discovery import idle_message_for_source
from core.monitor.monitor_operating_mode import MonitorOperatingMode, normalize_operating_mode
from core.monitor.spectrum_engine import SpectrumEngine
from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams
from core.monitor.monitor_mode_profile import clamp_center_to_source, refresh_capture_and_span_limits
from core.monitor.monitor_mode_profile import max_span_hz_for_source
from core.rf.runner import RfSpectrumRunner
from gui.monitor.monitor_rf_view_model import MonitorRfViewModel
from core.monitor.monitor_export import TraceExportFormat
from core.monitor.monitor_freq_span_logic import ensure_marker_visible, patch_center_freq, patch_selected_freq, zoom_manual_span
from core.monitor.monitor_recorder import (
    EXPORT_RECORD_AUDIO,
    EXPORT_RECORD_BASEBAND,
    MonitorRecorder,
)
from core.monitor.spectrum_params_io import params_from_dict, params_to_dict
from gui.monitor.demod_audio_output import DemodAudioOutput
from gui.monitor.monitor_config_panel import MonitorConfigPanel
from gui.monitor.monitor_spectrum_widget import MonitorSpectrumWidget
from gui.monitor.monitor_waterfall_widget import MonitorWaterfallWidget


def _sweep_manual_trigger_active(params: SpectrumParams) -> bool:
    """Disparo manual solo aplica al barrido; en IQ debe mostrarse en continuo."""
    return params.capture_mode == "sweep" and params.sweep_trigger_mode == "manual"


class MonitorController(QObject):
    """Gestiona SpectrumEngine y actualización thread-safe de la GUI."""

    status_changed = pyqtSignal(str)
    frame_ready = pyqtSignal(object)
    demod_state_ready = pyqtSignal(object)
    digital_analysis_ready = pyqtSignal(object)
    rf_metrics_ready = pyqtSignal(object)
    params_updated = pyqtSignal(object)
    toolbar_sync_requested = pyqtSignal(object)
    transport_changed = pyqtSignal(bool, bool)  # running, connecting
    operating_mode_changed = pyqtSignal(str)
    engine_running_changed = pyqtSignal(bool)

    def __init__(
        self,
        *,
        spectrum: MonitorSpectrumWidget,
        waterfall: MonitorWaterfallWidget,
        config: MonitorConfigPanel,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._spectrum = spectrum
        self._waterfall = waterfall
        self._config = config
        self._engine = SpectrumEngine(
            on_frame=self._enqueue_frame,
            on_status=self._enqueue_status,
            on_running_changed=self.engine_running_changed.emit,
            on_demod_pcm=self._push_demod_pcm_direct,
            on_demod_ui=self._enqueue_demod_state,
            on_digital_ui=self._enqueue_digital_analysis,
        )
        self._rf_runner = RfSpectrumRunner(
            on_frame=self._enqueue_frame,
            on_status=self._enqueue_status,
            on_running_changed=self.engine_running_changed.emit,
        )
        self._rf_view_model = MonitorRfViewModel()
        self._rf_view_model.bind_runner(self._rf_runner)
        self._last_auto_ref_emit = 0.0
        self._auto_ref_smooth: tuple[float, float] | None = None
        self._last_rf_metrics_emit = 0.0
        self._last_status_peak_emit = 0.0
        self._trace_update_armed = True
        self._trigger_timer = QTimer(self)
        self._trigger_timer.timeout.connect(self._on_periodic_trigger)
        self._on_layout_persist = None
        self._start_guard_until = 0.0
        self._user_stop_requested = False
        self._last_frame_at = 0.0
        self._last_status_message = ""
        self._last_display_frame: Optional[SpectrumFrame] = None
        self._pending_vfo_peak_snap = False
        self._vfo_snap_warmup_frames = 0
        self._audio_out = DemodAudioOutput(self)
        self._audio_error_shown = False
        self._recorder = MonitorRecorder()
        self._engine.set_recording_iq_handler(self._on_recording_iq)
        self._frame_watchdog = QTimer(self)
        self._frame_watchdog.setInterval(2000)
        self._frame_watchdog.timeout.connect(self._check_capture_health)
        self._layout_persist_timer = QTimer(self)
        self._layout_persist_timer.setSingleShot(True)
        self._layout_persist_timer.setInterval(400)
        self._layout_persist_timer.timeout.connect(self._run_layout_persist)
        self._marker_trace_timer = QTimer(self)
        self._marker_trace_timer.setSingleShot(True)
        self._marker_trace_timer.setInterval(200)
        self._marker_trace_timer.timeout.connect(self._flush_marker_trace)
        self._pending_marker_trace: tuple | None = None
        self._marker_drag_active = False
        self._apply_params_busy = False
        self._pending_apply_params: SpectrumParams | None = None
        self._auto_tune_busy = False
        self._project_params_lock = threading.Lock()
        self._project_params = self._engine.params.copy()
        self._get_project_manager = None
        self._get_database_service = None
        self._get_channelization_service = None
        self._toolbar_ref = None
        self._supervision_event_store = None
        self._supervision_state = None
        self._supervision_engine = None
        self._supervision_alarm_window = None
        self._supervision_resolved = []
        self._supervision_catalog = []
        self._supervision_alarm_popup_suppressed = False
        self._app_status_bar = None
        self._focus_monitor_alarms_cb = None
        self._dwell_phase = 0
        self._dwell_saved_params: SpectrumParams | None = None
        self._dwell_request = None
        self._dwell_timer = QTimer(self)
        self._dwell_timer.setSingleShot(True)
        self._dwell_timer.setInterval(900)
        self._dwell_timer.timeout.connect(self._on_supervision_dwell_timer)
        self._rec_clock_timer = QTimer(self)
        self._rec_clock_timer.setInterval(1000)
        self._rec_clock_timer.timeout.connect(self._on_supervision_rec_clock_tick)
        self.engine_running_changed.connect(self._on_running_changed)

        from core.monitor.hackrf_paths import ensure_hackrf_on_path

        ensure_hackrf_on_path()

        self.frame_ready.connect(self._deliver_frame)
        self.demod_state_ready.connect(self._on_demod_state)
        self.digital_analysis_ready.connect(self._on_digital_analysis)
        self.rf_metrics_ready.connect(self._config.update_rf_metrics)
        self.status_changed.connect(self._config.set_status_message)
        self.status_changed.connect(self._on_status_message)
        config.source_changed.connect(self._on_config_source_changed)
        config.set_transport_busy_callback(self.is_transport_busy)
        config.demod_params_changed.connect(self._apply_demod_params_from_panel)
        config.radio_soft_param_patch.connect(self._apply_soft_param_patch)
        config.audio_volume_changed.connect(self.apply_audio_volume)
        config.recorder_params_changed.connect(self.apply_params)
        config.markers_params_changed.connect(self.apply_params)
        config.display_params_changed.connect(self.apply_params)
        config.calibration_step_requested.connect(self.apply_params)
        config.bind_calibration_controller(
            get_params=self.get_params,
            is_running=self._capture_or_demod_running,
        )
        config.supervision_changed.connect(self._on_supervision_changed)
        config.supervision_ack_all_requested.connect(self._on_supervision_ack_all)
        config.supervision_ack_channel_requested.connect(self._on_supervision_ack_channel)
        config.supervision_show_events_requested.connect(
            lambda: self._show_supervision_alarm_window(user_initiated=True)
        )
        config.supervision_thresholds_requested.connect(self.show_supervision_thresholds_dialog)
        config.bind_supervision_tree_controller(self)
        config.capture_reference_requested.connect(self._on_capture_reference)
        config.capture_reference_bulk_requested.connect(self._on_capture_reference_bulk)
        config.clear_reference_bulk_requested.connect(self._on_clear_reference_bulk)
        config.record_toggled.connect(self._on_record_toggled)
        config.auto_tune_requested.connect(self.auto_tune_sdr)
        config.welle_cli_requested.connect(self.launch_welle_cli_sdr)
        config.mode_restriction.connect(self._notify_mode_restriction)
        self.operating_mode_changed.connect(config.set_operating_mode)
        self._spectrum.frequency_clicked.connect(self._on_spectrum_frequency)
        self._spectrum.marker_drag_active.connect(self._on_marker_drag_active)
        self._spectrum.span_zoom_requested.connect(self._on_span_zoom)
        self._spectrum.sliders.params_changed.connect(self._apply_params_from_overlay_sliders)
        for slider_name in ("rf_preamp", "rf_lna", "rf_vga", "ampt", "vrange"):
            getattr(self._spectrum, slider_name).params_changed.connect(
                self._apply_params_from_dock_sliders
            )
        self._spectrum.dock_settings_changed.connect(self._apply_dock_settings)
        self._spectrum.status.params_changed.connect(self._apply_params_from_status_strip)
        self._spectrum.marker_settings_requested.connect(self._on_marker_settings_requested)
        self._spectrum.marker_activate_requested.connect(self._on_marker_activate_requested)
        self._spectrum.freq_plot_gutter_changed.connect(self._waterfall.set_freq_plot_right_gutter)
        self._waterfall.levels.params_changed.connect(self.apply_params)
        self.params_updated.connect(self._spectrum.set_analyzer_params)
        self.params_updated.connect(self._waterfall.set_analyzer_params)
        self._waterfall.set_freq_plot_right_gutter(self._spectrum.freq_plot_right_gutter())
        self.params_updated.emit(self.get_params())
        self._config.set_monitor_params(self.get_params())
        self._config.set_controls_busy(connecting=False, running=False)
        from core.monitor.supervision.supervision_engine import SupervisionEngine

        self._supervision_engine = SupervisionEngine()
        self._sync_supervision_event_store()

    def bind_project(self, get_project_manager) -> None:
        self._get_project_manager = get_project_manager
        self._config.set_equipos_provider(self._project_equipos)
        self._sync_supervision_event_store()
        self.reload_supervision_from_project()

    def bind_database(self, get_database_service) -> None:
        self._get_database_service = get_database_service
        self._sync_supervision_event_store()

    def bind_channelization(self, get_channelization_service) -> None:
        self._get_channelization_service = get_channelization_service
        self.refresh_channelization_ui()

    def refresh_channelization_ui(self) -> None:
        svc = self._get_channelization_service() if self._get_channelization_service else None
        if self._toolbar_ref is not None and hasattr(self._toolbar_ref, "set_channelization_service"):
            self._toolbar_ref.set_channelization_service(svc)
        if hasattr(self._spectrum, "set_channelization_service"):
            self._spectrum.set_channelization_service(svc)
        self.toolbar_sync_requested.emit(self.get_params())

    def _project_equipos(self) -> list:
        pm = self._get_project_manager() if self._get_project_manager else None
        if pm is None or pm.project is None:
            return []
        from core.inventory_channel import equipos_from_project

        return equipos_from_project(pm.project)

    def reload_supervision_from_project(self) -> None:
        from core.monitor.supervision import (
            default_supervision_state,
            load_supervision,
            resolve_supervision_targets,
            save_supervision,
            sync_supervision_targets,
        )
        from core.monitor.supervision.supervision_models import AlarmSummaryCounts
        from core.monitor.supervision.supervision_resolve import resolve_supervision_catalog

        pm = self._get_project_manager() if self._get_project_manager else None
        if pm is None or pm.project is None:
            state = default_supervision_state()
            resolved = []
            catalog = []
            equipos = []
        else:
            state = load_supervision(pm.project)
            before = state.to_dict()
            sync_supervision_targets(pm.project, state)
            if state.to_dict() != before:
                save_supervision(pm.project, state)
            equipos = self._project_equipos()
            resolved = resolve_supervision_targets(state, equipos)
            catalog = resolve_supervision_catalog(state, equipos)
        self._supervision_state = state
        self._supervision_resolved = resolved
        self._supervision_catalog = catalog
        self._configure_supervision_engine(state, equipos)
        counts = (
            self._supervision_engine.last_snapshot.counts
            if self._supervision_engine is not None
            else AlarmSummaryCounts(ok=len(resolved))
        )
        self._apply_supervision_display(
            resolved,
            state.settings.show_inventory_on_spectrum,
            {},
        )
        self._config.set_supervision_state(state, alarm_counts=counts, alarm_lines=[])
        if resolved:
            self._config.set_supervision_runtime(
                alarm_counts=counts,
                alarm_lines=[],
                engine_active=True,
            )
        self._refresh_supervision_tree_views()
        self._restore_supervision_alarm_window_if_needed()
        self._sync_supervision_rec_status_ui()
        self._sync_app_supervision_status(counts)

    def bind_app_status_bar(self, widget) -> None:
        """Enlaza la barra de estado global (badges, REC, reloj, log, config)."""
        self._app_status_bar = widget
        widget.alarms_requested.connect(self.open_supervision_alarms_ui)
        widget.rec_toggle_requested.connect(self.toggle_supervision_rec)
        widget.log_settings_requested.connect(self.show_supervision_log_settings_dialog)
        widget.last_log_requested.connect(self.open_last_supervision_log)
        pm = self._get_project_manager() if self._get_project_manager else None
        widget.set_supervision_active(pm is not None and pm.project is not None)
        if self._supervision_engine is not None:
            widget.set_alarm_counts(self._supervision_engine.last_snapshot.counts)
        self._sync_supervision_rec_status_ui()

    def bind_main_window_actions(self, *, focus_monitor_alarms) -> None:
        """Registra callback de la ventana principal para abrir Monitor + alarmas."""
        self._focus_monitor_alarms_cb = focus_monitor_alarms

    def open_supervision_alarms_ui(self) -> None:
        """Abre la UI de alarmas (vía main window o ventana flotante del panel)."""
        if self._focus_monitor_alarms_cb is not None:
            self._focus_monitor_alarms_cb()
            return
        self.show_supervision_alarms_window()

    def show_supervision_alarms_window(self, *, user_initiated: bool = True) -> None:
        self._config.focus_alarmas_panel()
        self._show_supervision_alarm_window(user_initiated=user_initiated)

    def open_last_supervision_log(self, *, parent=None) -> None:
        """Muestra el CSV de la sesión REC activa o la última cerrada y abre su carpeta."""
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        from PyQt6.QtWidgets import QMessageBox

        from core.monitor.supervision.alarm_log_repository import read_alarm_log_csv
        from gui.monitor.monitor_supervision_log_view_dialog import MonitorSupervisionLogViewDialog
        from i18n.json_translation import tr

        if self._supervision_engine is None:
            return
        session = (
            self._supervision_engine.session_manager.active
            if self._supervision_engine.is_recording
            else self._supervision_engine.session_manager.last
        )
        host = parent or self._spectrum.window()
        if session is None or not session.directory.exists():
            QMessageBox.information(
                host,
                tr("monitor_alarmas_open_last_log"),
                tr("monitor_alarmas_open_last_log_none"),
            )
            return
        entries = read_alarm_log_csv(session.csv_path) if session.csv_path.exists() else []
        dialog = MonitorSupervisionLogViewDialog(
            entries,
            log_path=str(session.csv_path),
            parent=host,
        )
        dialog.exec()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(session.directory)))

    def _sync_app_supervision_status(self, counts=None) -> None:
        """Actualiza badges de supervisión en la barra de estado de la aplicación."""
        if self._app_status_bar is None:
            return
        pm = self._get_project_manager() if self._get_project_manager else None
        self._app_status_bar.set_supervision_active(pm is not None and pm.project is not None)
        if counts is not None:
            self._app_status_bar.set_alarm_counts(counts)
        elif self._supervision_engine is not None:
            self._app_status_bar.set_alarm_counts(self._supervision_engine.last_snapshot.counts)

    def _supervision_project_context(self) -> tuple[str, str]:
        pm = self._get_project_manager() if self._get_project_manager else None
        project_name = pm.get_project_name() if pm is not None else "session"
        project_file = pm.file_path if pm is not None else ""
        return project_name, project_file

    def _resolve_supervision_log_roots(self) -> tuple:
        from core.monitor.supervision.supervision_log_paths import (
            resolve_supervision_log_directory,
            resolve_supervision_log_export_directory,
        )

        if self._supervision_state is None:
            raise RuntimeError("Supervision state not loaded")
        project_name, project_file = self._supervision_project_context()
        log_root = resolve_supervision_log_directory(
            self._supervision_state,
            project_file_path=project_file or None,
            project_name=project_name,
        )
        export_root = resolve_supervision_log_export_directory(
            self._supervision_state,
            project_file_path=project_file or None,
            project_name=project_name,
        )
        return log_root, export_root, project_name, project_file

    def _configure_supervision_engine(self, state, equipos: list) -> None:
        if self._supervision_engine is None:
            return
        project_name = ""
        project_key = ""
        project_file = ""
        pm = self._get_project_manager() if self._get_project_manager else None
        if pm is not None:
            project_name = pm.get_project_name()
            project_file = pm.file_path or ""
            if pm.project is not None:
                from core.inventory_channel import project_storage_key

                project_key = project_storage_key(pm.file_path, project_name)
        from core.monitor.supervision.supervision_log_paths import resolve_supervision_log_directory

        log_root = resolve_supervision_log_directory(
            state,
            project_file_path=project_file or None,
            project_name=project_name,
        )
        self._supervision_engine.configure(
            state,
            equipos,
            project_name=project_name,
            project_key=project_key,
            log_directory=log_root,
        )

    def _sync_supervision_event_store(self) -> None:
        if self._supervision_engine is None:
            return
        from core.monitor.supervision.supervision_event_store import SupervisionEventStore

        db_svc = self._get_database_service() if self._get_database_service else None
        if db_svc is not None:
            self._supervision_event_store = SupervisionEventStore(db_svc.supervision_events)
        else:
            self._supervision_event_store = SupervisionEventStore(None)
        self._supervision_engine.set_event_store(self._supervision_event_store)

    def _project_storage_key(self) -> str:
        pm = self._get_project_manager() if self._get_project_manager else None
        if pm is None or pm.project is None:
            return ""
        from core.inventory_channel import project_storage_key

        return project_storage_key(pm.file_path, pm.get_project_name())

    def _supervision_log_path(self) -> str:
        if self._supervision_engine is None or self._supervision_engine.log_path is None:
            return ""
        return str(self._supervision_engine.log_path)

    def _load_session_log_entries(self, channel_keys: list[str] | None = None) -> list:
        from core.monitor.supervision.alarm_log_repository import (
            filter_alarm_log_entries,
            read_alarm_log_csv,
        )

        log_path = self._supervision_log_path()
        if not log_path:
            return []
        entries = read_alarm_log_csv(log_path)
        if channel_keys:
            entries = filter_alarm_log_entries(entries, channel_keys=channel_keys)
        return entries

    def show_supervision_log_view_dialog(
        self,
        context=None,
        *,
        parent=None,
    ) -> None:
        from gui.monitor.monitor_supervision_log_view_dialog import MonitorSupervisionLogViewDialog
        from i18n.json_translation import tr

        payload = context if isinstance(context, dict) else {}
        channel_keys = [str(key) for key in (payload.get("channel_keys") or []) if key]
        scope_title = str(payload.get("title") or "")
        host = parent or self._spectrum.window()
        log_path = self._supervision_log_path()
        if not log_path:
            from PyQt6.QtWidgets import QMessageBox

            from i18n.json_translation import tr

            QMessageBox.information(
                host,
                tr("monitor_supervision_log_view_title"),
                tr("monitor_supervision_log_view_no_session"),
            )
            return
        entries = self._load_session_log_entries(channel_keys)
        dialog = MonitorSupervisionLogViewDialog(
            entries,
            log_path=log_path,
            scope_title=scope_title,
            parent=host,
        )
        dialog.exec()

    def export_supervision_log_for_channels(
        self,
        channel_keys: list[str],
        *,
        parent=None,
    ) -> None:
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        from core.monitor.monitor_export_paths import EXPORT_ALARM_CSV, remember_save_path
        from core.monitor.supervision.alarm_log_repository import export_alarm_log_csv
        from i18n.json_translation import tr

        host = parent or self._spectrum.window()
        log_path = self._supervision_log_path()
        if not log_path:
            QMessageBox.information(
                host,
                tr("monitor_supervision_log_view_title"),
                tr("monitor_supervision_log_view_no_session"),
            )
            return
        entries = self._load_session_log_entries(channel_keys)
        if not entries:
            QMessageBox.information(
                host,
                tr("monitor_supervision_ctx_export_log"),
                tr("monitor_supervision_log_view_empty"),
            )
            return
        default_path = str(
            self._resolve_supervision_log_roots()[1] / "supervision_log_export.csv"
        )
        path, _filter = QFileDialog.getSaveFileName(
            host,
            tr("monitor_supervision_ctx_export_log"),
            default_path,
            tr("monitor_export_filter_csv"),
        )
        if not path:
            return
        try:
            export_alarm_log_csv(entries, path)
            remember_save_path(EXPORT_ALARM_CSV, path)
            QMessageBox.information(
                host,
                tr("monitor_supervision_ctx_export_log"),
                tr("monitor_export_csv_done").format(path=path),
            )
        except OSError as exc:
            QMessageBox.warning(
                host,
                tr("monitor_supervision_ctx_export_log"),
                tr("monitor_export_error").format(error=str(exc)),
            )

    def show_supervision_scope_thresholds_dialog(
        self,
        context=None,
        *,
        parent=None,
    ) -> None:
        if self._supervision_state is None:
            return
        payload = context if isinstance(context, dict) else {}
        channel_keys = [str(key) for key in (payload.get("channel_keys") or []) if key]
        if not channel_keys:
            return
        from PyQt6.QtWidgets import QDialog

        from gui.monitor.monitor_supervision_scope_freq_dialog import (
            MonitorSupervisionScopeFreqDialog,
        )

        host = parent or self._spectrum.window()
        dialog = MonitorSupervisionScopeFreqDialog(
            self._supervision_state,
            self._project_equipos(),
            channel_keys,
            scope_title=str(payload.get("title") or ""),
            parent=host,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._on_supervision_changed(dialog.get_state())

    def toggle_supervision_rec(self) -> None:
        """Inicia o detiene una sesión REC manual (carpeta con CSV, TXT y metadatos)."""
        if self._supervision_engine is None or self._supervision_state is None:
            return
        if self._supervision_engine.is_recording:
            self._stop_supervision_rec()
        else:
            self._start_supervision_rec()

    def _start_supervision_rec(self) -> None:
        """Crea carpeta de sesión, arranca REC y sincroniza panel, ventana y barra global."""
        from i18n.json_translation import tr

        if self._supervision_engine is None or self._supervision_state is None:
            return
        log_root, _, project_name, _ = self._resolve_supervision_log_roots()
        try:
            path = self._supervision_engine.start_recording(
                log_root=log_root,
                project_name=project_name,
            )
        except OSError as exc:
            host = self._spectrum.window()
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(
                host,
                tr("monitor_alarmas_rec_toggle"),
                tr("monitor_alarmas_rec_start_error").format(error=str(exc)),
            )
            self._sync_supervision_rec_status_ui()
            return
        self._rec_clock_timer.start()
        self._sync_supervision_rec_status_ui()
        self.status_changed.emit(
            tr("monitor_alarmas_rec_started").format(path=str(path.parent))
        )

    def _stop_supervision_rec(self) -> None:
        """Cierra la sesión REC, genera informe y actualiza indicadores REC/reloj."""
        from i18n.json_translation import tr

        if self._supervision_engine is None or self._supervision_state is None:
            return
        project_name, _ = self._supervision_project_context()
        session = self._supervision_engine.stop_recording(project_name=project_name, tr=tr)
        self._rec_clock_timer.stop()
        self._sync_supervision_rec_status_ui()
        if session is not None:
            self.status_changed.emit(
                tr("monitor_alarmas_rec_stopped").format(
                    folder=str(session.directory),
                    events=session.event_count,
                )
            )

    def _on_supervision_rec_clock_tick(self) -> None:
        """Refresca el reloj REC cada segundo mientras hay sesión activa."""
        self._sync_supervision_rec_status_ui()

    def _sync_supervision_rec_status_ui(self) -> None:
        """Propaga estado REC (activo, transcurrido, sesiones) a panel, ventana y barra."""
        engine = self._supervision_engine
        active = bool(engine is not None and engine.is_recording)
        elapsed = engine.rec_elapsed_seconds() if active and engine is not None else 0
        last = engine.session_manager.last if engine is not None else None
        active_session = engine.session_manager.active if active and engine is not None else None
        payload = {
            "active": active,
            "elapsed_s": elapsed,
            "last": last,
            "active_session": active_session,
        }
        self._config.set_supervision_rec_status(**payload)
        if self._supervision_alarm_window is not None:
            self._supervision_alarm_window.set_rec_status(**payload)
        if self._app_status_bar is not None:
            self._app_status_bar.set_rec_status(**payload)

    def show_supervision_log_settings_dialog(self, *, parent=None) -> None:
        """Diálogo de carpetas de log, disparo CSV e inicio REC (manual o al pulsar Play)."""
        if self._supervision_state is None:
            return
        from PyQt6.QtWidgets import QDialog

        from gui.monitor.monitor_supervision_log_settings_dialog import (
            MonitorSupervisionLogSettingsDialog,
        )

        project_name, project_file = self._supervision_project_context()
        host = parent or self._spectrum.window()
        dialog = MonitorSupervisionLogSettingsDialog(
            self._supervision_state,
            project_file_path=project_file,
            project_name=project_name,
            parent=host,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.get_settings()
        self._supervision_state.settings.log_directory = settings.log_directory
        self._supervision_state.settings.log_export_directory = settings.log_export_directory
        self._supervision_state.settings.log_trigger = settings.log_trigger
        self._supervision_state.settings.rec_start_mode = settings.rec_start_mode
        self._on_supervision_changed(self._supervision_state)

    def _load_supervision_event_entries(self, severity: str = "", phase: str = "") -> list:
        store = self._supervision_event_store
        project_key = self._project_storage_key()
        log_path = self._supervision_log_path()
        if store is None or not project_key:
            from core.monitor.supervision.alarm_log_repository import (
                filter_alarm_log_entries,
                read_alarm_log_csv,
            )

            if log_path:
                entries = read_alarm_log_csv(log_path)
                return filter_alarm_log_entries(entries, severity=severity, phase=phase)
            return []
        return store.query_merged(
            project_key,
            csv_path=log_path or None,
            limit=2000,
            channel_key="",
            severity=severity,
            phase=phase,
        )

    def show_supervision_help(self, *, parent=None) -> None:
        """Abre la ayuda F1 de supervisión (markdown docs/monitor_supervision_*.md)."""
        from gui.monitor.monitor_supervision_help_dialog import show_supervision_help_dialog

        host = parent or self._spectrum.window()
        show_supervision_help_dialog(host)

    def toggle_transport(self) -> None:
        if self._engine.is_running:
            self.stop()
        else:
            self.start()

    def show_supervision_tree_panel(self) -> None:
        """Abre la sección ALARMAS con el árbol de inventario."""
        self._config.focus_alarmas_panel()
        self._refresh_supervision_tree_views()

    def locate_selected_supervision_channel(self) -> None:
        if self._config.trigger_supervision_tree_locate():
            return
        if self._supervision_alarm_window is None:
            self._show_supervision_alarm_window(user_initiated=True)
        if self._supervision_alarm_window is not None:
            if not self._supervision_alarm_window.trigger_locate_selected():
                self.status_changed.emit(self._tr("monitor_shortcut_locate_none"))

    def ack_selected_supervision_channel(self) -> None:
        if self._config.trigger_supervision_tree_ack():
            return
        if self._supervision_alarm_window is None:
            self._show_supervision_alarm_window(user_initiated=True)
        if self._supervision_alarm_window is not None:
            if not self._supervision_alarm_window.trigger_ack_selected():
                self.status_changed.emit(self._tr("monitor_shortcut_ack_none"))

    @staticmethod
    def _tr(key: str) -> str:
        from i18n.json_translation import tr

        return tr(key)

    def show_supervision_thresholds_dialog(self, context=None, *, parent=None) -> None:
        if self._supervision_state is None:
            return
        from core.monitor.supervision.rules_resolver import SCOPE_GLOBAL
        from gui.monitor.monitor_alarm_thresholds_dialog import edit_supervision_thresholds_dialog

        payload = context if isinstance(context, dict) else {}
        scope = str(payload.get("scope") or SCOPE_GLOBAL)
        key = str(payload.get("key") or "")
        host = parent or self._spectrum.window()
        updated = edit_supervision_thresholds_dialog(
            self._supervision_state,
            self._project_equipos(),
            initial_scope=scope,
            initial_key=key,
            parent=host,
        )
        if updated is not None:
            self._on_supervision_changed(updated)

    def show_supervision_events_dialog(self) -> None:
        from gui.monitor.monitor_supervision_events_dialog import MonitorSupervisionEventsDialog

        host = self._spectrum.window()
        dialog = MonitorSupervisionEventsDialog(
            query_entries=self._load_supervision_event_entries,
            export_csv=self._export_supervision_events_csv,
            export_txt=self._export_supervision_events_txt,
            log_path=self._supervision_log_path(),
            parent=host,
        )
        dialog.exec()

    def _project_name(self) -> str:
        pm = self._get_project_manager() if self._get_project_manager else None
        if pm is None:
            return ""
        return pm.get_project_name()

    def export_supervision_events(self, *, parent=None) -> None:
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        from core.monitor.monitor_export_paths import EXPORT_ALARM_TXT, remember_save_path, resolve_save_path
        from i18n.json_translation import tr

        host = parent or self._spectrum.window()
        default_path = resolve_save_path(EXPORT_ALARM_TXT, "supervision_alarm_report.txt")
        path, _filter = QFileDialog.getSaveFileName(
            host,
            tr("monitor_supervision_events_export_txt"),
            default_path,
            tr("monitor_export_filter_txt"),
        )
        if not path:
            return
        entries = self._load_supervision_event_entries("", "")
        ok, message = self._export_supervision_events_txt(path, entries)
        if ok:
            remember_save_path(EXPORT_ALARM_TXT, path)
        if ok:
            QMessageBox.information(host, tr("monitor_supervision_events_export_title"), message)
        else:
            QMessageBox.warning(host, tr("monitor_supervision_events_export_title"), message)

    def _export_supervision_events_csv(self, path: str, entries: list) -> tuple[bool, str]:
        from i18n.json_translation import tr

        from core.monitor.supervision.supervision_event_store import SupervisionEventStore

        try:
            if not entries:
                return False, tr("monitor_supervision_events_empty")
            SupervisionEventStore.export_csv(entries, path)
            return True, tr("monitor_export_csv_done").format(path=path)
        except OSError as exc:
            return False, tr("monitor_export_error").format(error=str(exc))

    def _export_supervision_events_txt(self, path: str, entries: list) -> tuple[bool, str]:
        from i18n.json_translation import tr

        from core.monitor.supervision.supervision_event_store import SupervisionEventStore

        try:
            if not entries:
                return False, tr("monitor_supervision_events_empty")
            SupervisionEventStore.export_txt(
                entries,
                path,
                project_name=self._project_name(),
                tr=tr,
            )
            return True, tr("monitor_export_txt_done").format(path=path)
        except OSError as exc:
            return False, tr("monitor_export_error").format(error=str(exc))

    def _apply_supervision_display(self, resolved, show: bool, alarm_states: dict) -> None:
        self._spectrum.set_supervision_targets(resolved, visible=show)
        self._waterfall.set_supervision_targets(resolved, visible=show)
        self._spectrum.set_supervision_alarm_states(alarm_states)
        self._waterfall.set_supervision_alarm_states(alarm_states)

    def _apply_supervision_snapshot(self, snapshot) -> None:
        state = self._supervision_state
        show = True if state is None else state.settings.show_inventory_on_spectrum
        self._apply_supervision_display(self._supervision_resolved, show, snapshot.alarm_states)
        self._config.set_supervision_runtime(
            alarm_counts=snapshot.counts,
            alarm_lines=snapshot.alarm_lines,
            alarm_rows=snapshot.alarm_rows,
            pending_attention=snapshot.pending_attention,
            engine_active=True,
        )
        self._sync_app_supervision_status(snapshot.counts)
        self._refresh_supervision_tree_views(snapshot)
        if snapshot.pending_attention == 0:
            self._supervision_alarm_popup_suppressed = False
        has_new_critical = any(
            item.severity == "critical" and item.phase == "raised"
            for item in snapshot.transitions
        )
        if (
            has_new_critical
            and snapshot.pending_attention > 0
            and self._engine.is_running
            and not self._supervision_alarm_popup_suppressed
        ):
            self._show_supervision_alarm_window(user_initiated=False)

    def _on_supervision_ack_channel(self, channel_key: str) -> None:
        if self._supervision_engine is None:
            return
        snapshot = self._supervision_engine.acknowledge(channel_key)
        self._apply_supervision_snapshot(snapshot)

    def _on_supervision_changed(self, state) -> None:
        self._supervision_state = state
        pm = self._get_project_manager() if self._get_project_manager else None
        if pm is not None and pm.project is not None:
            from core.monitor.supervision import save_supervision

            save_supervision(pm.project, state)
            pm.mark_dirty()
        from core.monitor.supervision import resolve_supervision_targets
        from core.monitor.supervision.supervision_resolve import resolve_supervision_catalog

        equipos = self._project_equipos()
        resolved = resolve_supervision_targets(state, equipos)
        self._supervision_resolved = resolved
        self._supervision_catalog = resolve_supervision_catalog(state, equipos)
        if self._supervision_engine is not None:
            self._configure_supervision_engine(state, equipos)
            self._supervision_engine.update_settings(state)
        snapshot = (
            self._supervision_engine.last_snapshot
            if self._supervision_engine is not None
            else None
        )
        alarm_states = snapshot.alarm_states if snapshot is not None else {}
        self._apply_supervision_display(resolved, state.settings.show_inventory_on_spectrum, alarm_states)
        counts = snapshot.counts if snapshot is not None else None
        if counts is None:
            from core.monitor.supervision.supervision_models import AlarmSummaryCounts

            counts = AlarmSummaryCounts(ok=len(resolved))
        lines = snapshot.alarm_lines if snapshot is not None else []
        self._config.set_supervision_state(state, alarm_counts=counts, alarm_lines=lines)
        self._refresh_supervision_tree_views()

    def _on_supervision_ack_all(self) -> None:
        if self._supervision_engine is None:
            return
        snapshot = self._supervision_engine.acknowledge_all()
        self._apply_supervision_snapshot(snapshot)

    def _show_supervision_alarm_window(
        self,
        *,
        user_initiated: bool = True,
        restore_session: bool = False,
    ) -> None:
        from gui.monitor.monitor_supervision_alarm_window import MonitorSupervisionAlarmWindow

        self._sync_supervision_catalog_from_project()
        if (
            not user_initiated
            and not restore_session
            and self._supervision_alarm_popup_suppressed
        ):
            return
        snapshot = self._supervision_engine_snapshot()
        if self._supervision_alarm_window is None:
            host = self._spectrum.window()
            self._supervision_alarm_window = MonitorSupervisionAlarmWindow(host)
            self._supervision_alarm_window.ack_all_requested.connect(self._on_supervision_ack_all)
            self._supervision_alarm_window.ack_channel_requested.connect(
                self._on_supervision_ack_channel
            )
            self._supervision_alarm_window.user_dismissed.connect(
                self._on_supervision_alarm_window_dismissed
            )
            self._supervision_alarm_window.highlight_channels_requested.connect(
                self._on_supervision_highlight_channels
            )
            self._supervision_alarm_window.locate_channels_requested.connect(
                self._on_supervision_locate_channels
            )
            self._supervision_alarm_window.group_mode_changed.connect(
                self._on_supervision_tree_group_changed
            )
            self._supervision_alarm_window.layout_changed.connect(
                self._on_supervision_alarm_window_layout_changed
            )
            self._supervision_alarm_window.supervision_enabled_changed.connect(
                self._on_supervision_enabled_changed
            )
            self._supervision_alarm_window.history_requested.connect(
                self.show_supervision_events_dialog
            )
            self._supervision_alarm_window.export_requested.connect(
                self.export_supervision_events
            )
            self._supervision_alarm_window.thresholds_requested.connect(
                self.show_supervision_thresholds_dialog
            )
            self._supervision_alarm_window.help_requested.connect(self.show_supervision_help)
            self._supervision_alarm_window.digital_mode_changed.connect(
                self._on_supervision_digital_mode_changed
            )
            self._supervision_alarm_window.log_export_requested.connect(
                self.export_supervision_log_for_channels
            )
            self._supervision_alarm_window.log_view_requested.connect(
                self.show_supervision_log_view_dialog
            )
            self._supervision_alarm_window.scope_thresholds_requested.connect(
                self.show_supervision_scope_thresholds_dialog
            )
            self._supervision_alarm_window.rec_toggle_requested.connect(
                self.toggle_supervision_rec
            )
            self._supervision_alarm_window.log_settings_requested.connect(
                self.show_supervision_log_settings_dialog
            )
            self._supervision_alarm_window.last_log_requested.connect(
                self.open_last_supervision_log
            )
        if user_initiated:
            self._supervision_alarm_popup_suppressed = False
        elif self._supervision_alarm_window.isVisible():
            self._refresh_supervision_tree_views(snapshot)
            return
        if not self._supervision_alarm_window.isVisible():
            self._supervision_alarm_window.restore_layout(self._supervision_alarm_window_layout())
        self._refresh_supervision_tree_views(snapshot)
        self._supervision_alarm_window.show()
        self._set_supervision_alarm_window_visible(True)
        if user_initiated:
            self._supervision_alarm_window.raise_()
            self._supervision_alarm_window.activateWindow()

    def _restore_supervision_alarm_window_if_needed(self) -> None:
        if self._supervision_state is None:
            return
        if not self._supervision_state.settings.alarm_window_visible:
            return
        QTimer.singleShot(
            0,
            lambda: self._show_supervision_alarm_window(
                user_initiated=False,
                restore_session=True,
            ),
        )

    def _set_supervision_alarm_window_visible(self, visible: bool) -> None:
        if self._supervision_state is None:
            return
        if self._supervision_state.settings.alarm_window_visible == visible:
            return
        self._supervision_state.settings.alarm_window_visible = visible
        pm = self._get_project_manager() if self._get_project_manager else None
        if pm is not None and pm.project is not None:
            from core.monitor.supervision import save_supervision

            save_supervision(pm.project, self._supervision_state)
            pm.mark_dirty()

    def _on_supervision_alarm_window_dismissed(self) -> None:
        self._supervision_alarm_popup_suppressed = True
        self._set_supervision_alarm_window_visible(False)

    def _supervision_engine_snapshot(self):
        if self._supervision_engine is None:
            return None
        return self._supervision_engine.last_snapshot

    def _sync_supervision_catalog_from_project(self) -> None:
        pm = self._get_project_manager() if self._get_project_manager else None
        if pm is None or pm.project is None:
            self._supervision_catalog = []
            return
        from core.monitor.supervision import load_supervision, sync_supervision_targets
        from core.monitor.supervision.supervision_resolve import resolve_supervision_catalog

        state = self._supervision_state or load_supervision(pm.project)
        sync_supervision_targets(pm.project, state)
        equipos = self._project_equipos()
        self._supervision_catalog = resolve_supervision_catalog(state, equipos)
        if self._supervision_state is not None:
            self._supervision_state.targets = list(state.targets)

    def _supervision_tree_payload(self, snapshot=None) -> dict:
        snap = snapshot if snapshot is not None else self._supervision_engine_snapshot()
        log_path = ""
        if self._supervision_engine is not None and self._supervision_engine.log_path is not None:
            log_path = str(self._supervision_engine.log_path)
        group_mode = "zone"
        if self._supervision_state is not None:
            group_mode = self._supervision_state.settings.tree_group_mode
        return {
            "resolved": self._supervision_catalog,
            "equipos": self._project_equipos(),
            "alarm_states": snap.alarm_states if snap is not None else {},
            "alarm_rows": snap.alarm_rows if snap is not None else [],
            "channel_metrics": getattr(snap, "channel_metrics", {}) if snap is not None else {},
            "supervision_state": self._supervision_state,
            "group_mode": group_mode,
            "pending_attention": snap.pending_attention if snap is not None else 0,
            "log_path": log_path,
        }

    def _refresh_supervision_tree_views(self, snapshot=None) -> None:
        self._sync_supervision_catalog_from_project()
        payload = self._supervision_tree_payload(snapshot)
        self._config.update_supervision_tree(**payload)
        if self._supervision_alarm_window is not None:
            self._supervision_alarm_window.update_supervision(**payload)

    def _refresh_supervision_alarm_window(self, snapshot=None) -> None:
        self._refresh_supervision_tree_views(snapshot)

    def _update_supervision_alarm_window(self, snapshot) -> None:
        self._refresh_supervision_tree_views(snapshot)

    def _on_supervision_digital_mode_changed(self, channel_key: str, mer_enabled: bool) -> None:
        if self._supervision_state is None or not channel_key:
            return
        from core.monitor.supervision.rules_resolver import set_channel_digital_metrics

        set_channel_digital_metrics(
            self._supervision_state,
            channel_key,
            enabled=bool(mer_enabled),
            equipos=self._project_equipos(),
        )
        if self._supervision_engine is not None:
            self._supervision_engine.update_settings(self._supervision_state)
            self._supervision_engine.clear_digital_state(channel_key)
        self._on_supervision_changed(self._supervision_state)
        snapshot = (
            self._supervision_engine.last_snapshot
            if self._supervision_engine is not None
            else None
        )
        if snapshot is not None:
            self._apply_supervision_snapshot(snapshot)

    def _capture_reference_for_channel(self, channel_key: str) -> bool:
        if self._supervision_state is None or not channel_key:
            return False
        record = None
        if self._supervision_engine is not None:
            record = self._supervision_engine._alarm_manager.records.get(channel_key)
        if record is None:
            return False
        has_snr = record.snr_above_noise_db is not None
        has_mer = record.mer_db is not None
        if not has_snr and not has_mer:
            return False
        from core.monitor.supervision.threshold_resolver import capture_channel_reference

        capture_channel_reference(
            self._supervision_state,
            channel_key,
            snr_above_noise_db=record.snr_above_noise_db,
            carrier_dbm=record.carrier_dbm,
            mer_db=record.mer_db,
            sync_ok=record.digital_sync_ok,
        )
        return True

    def _on_capture_reference(self, channel_key: str) -> None:
        from i18n.json_translation import tr

        if not self._capture_reference_for_channel(channel_key):
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self._spectrum.window(),
                tr("monitor_freq_manager_fix_reference"),
                tr("monitor_freq_manager_ref_need_play"),
            )
            return
        self._on_supervision_changed(self._supervision_state)
        if self._config is not None:
            self._config.set_supervision_state(self._supervision_state)

    def _on_capture_reference_bulk(self, channel_keys: object) -> None:
        keys = [str(key) for key in (channel_keys or []) if key]
        if not keys:
            return
        captured = sum(1 for key in keys if self._capture_reference_for_channel(key))
        if captured == 0:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self._spectrum.window(),
                tr("monitor_freq_manager_fix_reference"),
                tr("monitor_freq_manager_ref_need_play"),
            )
            return
        self._on_supervision_changed(self._supervision_state)
        if self._config is not None:
            self._config.set_supervision_state(self._supervision_state)

    def _on_clear_reference_bulk(self, channel_keys: object) -> None:
        if self._supervision_state is None:
            return
        keys = [str(key) for key in (channel_keys or []) if key]
        if not keys:
            return
        from core.monitor.supervision.threshold_resolver import clear_references_for_channels

        clear_references_for_channels(self._supervision_state, keys)
        self._on_supervision_changed(self._supervision_state)
        if self._config is not None:
            self._config.set_supervision_state(self._supervision_state)

    def _on_supervision_enabled_changed(self, channel_keys: list[str], enabled: bool) -> None:
        if self._supervision_state is None or not channel_keys:
            return
        key_set = set(str(key) for key in channel_keys if key)
        changed = False
        for target in self._supervision_state.targets:
            if target.channel_key in key_set and target.enabled != bool(enabled):
                target.enabled = bool(enabled)
                changed = True
        if not changed:
            return
        self._on_supervision_changed(self._supervision_state)
        snapshot = (
            self._supervision_engine.last_snapshot
            if self._supervision_engine is not None
            else None
        )
        if snapshot is not None:
            self._apply_supervision_snapshot(snapshot)

    def _supervision_catalog_targets(self, channel_keys: list[str]):
        key_set = {str(key) for key in channel_keys if key}
        if not key_set:
            return []
        return [
            target
            for target in self._supervision_catalog
            if target.channel_key in key_set and target.frequency_hz > 0.0
        ]

    def _center_supervision_channels(self, channel_keys: list[str]) -> None:
        targets = self._supervision_catalog_targets(channel_keys)
        if not targets:
            return
        targets.sort(key=lambda row: row.frequency_hz)
        freq_hz = float(targets[0].frequency_hz)
        params = self.get_params()
        if params.freq_readout == "f":
            updated = patch_selected_freq(params, freq_hz)
        else:
            updated = patch_center_freq(params, freq_hz)
        self.apply_params(updated)

    def _on_supervision_highlight_channels(self, channel_keys: list[str]) -> None:
        if not channel_keys:
            return
        pulse_targets = self._supervision_catalog_targets(channel_keys)
        self._spectrum.pulse_supervision_highlight(channel_keys, pulse_targets=pulse_targets)
        self._waterfall.pulse_supervision_highlight(channel_keys, pulse_targets=pulse_targets)

    def _on_supervision_locate_channels(self, channel_keys: list[str]) -> None:
        if not channel_keys:
            return
        pulse_targets = self._supervision_catalog_targets(channel_keys)
        self._center_supervision_channels(channel_keys)
        self._spectrum.pulse_supervision_highlight(channel_keys, pulse_targets=pulse_targets)
        self._waterfall.pulse_supervision_highlight(channel_keys, pulse_targets=pulse_targets)

    def _on_supervision_tree_group_changed(self, mode: str) -> None:
        if self._supervision_state is None:
            return
        from core.monitor.supervision.supervision_tree import SUPERVISION_TREE_GROUP_MODES

        if mode not in SUPERVISION_TREE_GROUP_MODES:
            return
        self._supervision_state.settings.tree_group_mode = mode
        pm = self._get_project_manager() if self._get_project_manager else None
        if pm is not None and pm.project is not None:
            from core.monitor.supervision import save_supervision

            save_supervision(pm.project, self._supervision_state)
            pm.mark_dirty()
        self._config.sync_tree_group_mode(mode)

    def _supervision_alarm_window_layout(self) -> dict:
        if self._supervision_state is None:
            return {}
        settings = self._supervision_state.settings
        return {
            "geometry_b64": settings.alarm_window_geometry_b64,
            "expanded_groups": list(settings.alarm_window_expanded_groups),
            "scroll": int(settings.alarm_window_scroll),
        }

    def _on_supervision_alarm_window_layout_changed(self, layout) -> None:
        if self._supervision_state is None or not isinstance(layout, dict):
            return
        settings = self._supervision_state.settings
        settings.alarm_window_geometry_b64 = str(layout.get("geometry_b64") or "")
        settings.alarm_window_expanded_groups = [
            str(key) for key in (layout.get("expanded_groups") or []) if key
        ]
        try:
            settings.alarm_window_scroll = max(0, int(layout.get("scroll", 0)))
        except (TypeError, ValueError):
            settings.alarm_window_scroll = 0
        pm = self._get_project_manager() if self._get_project_manager else None
        if pm is not None and pm.project is not None:
            from core.monitor.supervision import save_supervision

            save_supervision(pm.project, self._supervision_state)
            pm.mark_dirty()

    def _start_supervision_logging(self) -> None:
        if self._supervision_engine is None or self._supervision_state is None:
            return
        if self._supervision_engine.is_recording:
            return
        trigger = self._supervision_state.settings.log_trigger
        if trigger not in ("play", "auto"):
            return
        log_root, _, project_name, _ = self._resolve_supervision_log_roots()
        self._supervision_engine.start_logging(
            project_name=project_name,
            log_directory=log_root,
        )

    def _maybe_start_supervision_rec_on_play(self) -> None:
        """Arranca REC automáticamente al pulsar Play si rec_start_mode es 'play'."""
        if self._supervision_state is None or self._supervision_engine is None:
            return
        if self._supervision_state.settings.rec_start_mode != "play":
            return
        if self._supervision_engine.is_recording:
            return
        self._start_supervision_rec()

    def _stop_supervision_logging(self) -> None:
        if self._supervision_engine is not None:
            self._supervision_engine.stop_logging()

    def _process_supervision_frame(self, frame: SpectrumFrame) -> None:
        if self._supervision_engine is None or not self._supervision_resolved:
            return
        params = self.get_params()
        snapshot = self._supervision_engine.process_frame(
            frame,
            engine_running=self._engine.is_running,
            capture_mode=params.capture_mode,
            supervision_enabled=params.supervision_enabled,
            dwell_busy=self._dwell_phase != 0,
        )
        self._apply_supervision_snapshot(snapshot)
        if self._dwell_phase == 0 and self._engine.is_running:
            pending = self._supervision_engine.take_pending_dwell()
            if pending is not None:
                self._start_supervision_dwell(pending)

    _DWELL_IDLE = 0
    _DWELL_TUNING = 1
    _DWELL_RESTORE = 2

    def _start_supervision_dwell(self, request) -> None:
        if self._dwell_phase != self._DWELL_IDLE or not self._engine.is_running:
            return
        from core.monitor.monitor_mode_profile import instant_span_hz_for_source
        from core.monitor.supervision.digital_supervision import build_dwell_spectrum_params

        params = self.get_params()
        instant = instant_span_hz_for_source(params.source_id)
        active_span = max(
            float(params.manual_span_hz),
            float(params.span_hz),
            params.display_span_hz(),
        )
        if active_span > instant + 1.0:
            if self._supervision_engine is not None:
                self._supervision_engine.mark_dwell_started(request.channel_key)
            return

        equipo = {}
        if self._supervision_engine is not None:
            equipo = self._supervision_engine.get_equipo(request.channel_key) or {}
        target = next(
            (item for item in self._supervision_resolved if item.channel_key == request.channel_key),
            None,
        )
        if target is None:
            return
        self._dwell_request = request
        self._dwell_saved_params = self.get_params().copy()
        self._dwell_phase = self._DWELL_TUNING
        if self._supervision_engine is not None:
            self._supervision_engine.mark_dwell_started(request.channel_key)
        dwell_params = build_dwell_spectrum_params(self._dwell_saved_params, target, equipo)
        self.apply_params(dwell_params)
        reason_key = (
            "monitor_supervision_dwell_reason_snr"
            if request.reason == "snr_degraded"
            else "monitor_supervision_dwell_reason_periodic"
        )
        self.status_changed.emit(
            self._tr("monitor_supervision_dwell_status").format(
                label=request.label,
                freq=f"{request.frequency_hz / 1e6:.3f}",
                reason=self._tr(reason_key),
            )
        )
        tuning_ms = 900
        if self._supervision_state is not None:
            tuning_ms = int(self._supervision_state.settings.dwell_tuning_ms)
        self._dwell_timer.start(tuning_ms)

    def _on_supervision_dwell_timer(self) -> None:
        if self._dwell_phase == self._DWELL_TUNING:
            self._run_supervision_dwell_capture()
            self._dwell_phase = self._DWELL_RESTORE
            restore_ms = 80
            if self._supervision_state is not None:
                restore_ms = int(self._supervision_state.settings.dwell_restore_ms)
            self._dwell_timer.start(restore_ms)
            return
        if self._dwell_phase == self._DWELL_RESTORE:
            self._finish_supervision_dwell()

    def _run_supervision_dwell_capture(self) -> None:
        if self._supervision_engine is None or self._dwell_request is None:
            return
        from core.monitor.digital_mod_analysis import analyze_digital_modulation
        from core.monitor.digital_signal_profiles import get_digital_profile

        params = self.get_params()
        samples = self._engine.read_iq_snapshot(params, 16_384)
        if samples is None or int(getattr(samples, "size", 0)) < 256:
            return
        profile = get_digital_profile(params.digital_profile)
        result = analyze_digital_modulation(
            samples,
            params,
            sample_rate_hz=params.sample_rate_hz,
            profile=profile,
        )
        snapshot = self._supervision_engine.process_digital_analysis(
            channel_key=self._dwell_request.channel_key,
            vfo_hz=float(params.vfo_freq_hz),
            mer_db=result.mer_db,
            mer_db_smoothed=result.mer_db,
            sync_ok=bool(result.sync_ok),
            engine_running=True,
        )
        if snapshot.transitions:
            self._apply_supervision_snapshot(snapshot)

    def _finish_supervision_dwell(self) -> None:
        saved = self._dwell_saved_params
        self._dwell_saved_params = None
        self._dwell_request = None
        self._dwell_phase = self._DWELL_IDLE
        if saved is not None:
            saved.supervision_dwell_active = False
            self.apply_params(saved)
        if self._supervision_engine is not None and self._engine.is_running:
            pending = self._supervision_engine.take_pending_dwell()
            if pending is not None:
                self._start_supervision_dwell(pending)

    def set_layout_persist_callback(self, callback) -> None:
        self._on_layout_persist = callback

    def _schedule_layout_persist(self) -> None:
        if self._on_layout_persist is not None:
            self._layout_persist_timer.start()

    def _run_layout_persist(self) -> None:
        if self._on_layout_persist is not None:
            self._on_layout_persist()

    def flush_layout_persist(self) -> None:
        """Ejecuta de inmediato la persistencia de layout (cancela el debounce)."""
        if self._layout_persist_timer.isActive():
            self._layout_persist_timer.stop()
        self._run_layout_persist()

    def flush_persisted_state(self) -> None:
        """Consolida parámetros pendientes antes de serializar (sin re-disparar layout)."""
        pending = self._pending_apply_params
        if pending is not None:
            self._sync_persisted_radio_params_immediate(pending)
        self._layout_persist_timer.stop()

    def _flush_marker_trace(self) -> None:
        pending = self._pending_marker_trace
        if pending is None:
            return
        freqs, power = pending
        self._config.update_marker_trace(freqs, power)

    def load_persisted_params(self, data: dict) -> None:
        from core.monitor.spectrum_params_io import params_from_dict

        persist = self._on_layout_persist
        self._on_layout_persist = None
        try:
            merged = params_from_dict(data, base=self.get_params())
            self.apply_params(merged)
            self._config.apply_persisted_table_layout(data)
            if merged.config_panel_collapsed:
                workspace = self.parent()
                if workspace is not None and hasattr(workspace, "set_properties_panel_collapsed"):
                    workspace.set_properties_panel_collapsed(True, notify_controller=False)
            if merged.waterfall_panel_collapsed:
                workspace = self.parent()
                if workspace is not None and hasattr(workspace, "set_waterfall_panel_collapsed"):
                    workspace.set_waterfall_panel_collapsed(True, notify_controller=False)
            sid = merged.source_id or self._config.get_selected_source_id()
            if sid:
                base = sid.split("_")[0] if sid.startswith("hackrf") else sid
                if self._engine.source_impl_id != base:
                    self._engine.set_source(sid)
                    self.apply_params(self.get_params())
        finally:
            self._on_layout_persist = persist

    def get_persisted_params(self) -> dict:
        from core.monitor.spectrum_params_io import params_to_dict

        data = params_to_dict(self.get_params())
        data.update(self._config.save_persisted_table_layout())
        return data

    def get_params(self) -> SpectrumParams:
        with self._project_params_lock:
            return self._project_params.copy()

    def _capture_is_running(self) -> bool:
        return self._rf_runner.is_running

    def _capture_or_demod_running(self) -> bool:
        return self._capture_is_running() or self._engine.is_running

    def _capture_exit_message(self) -> str:
        return self._rf_runner.last_exit_message or self._engine.last_exit_message

    def is_transport_busy(self) -> bool:
        busy = (
            self._engine.is_connecting
            or self._engine.is_running
            or self._rf_runner.is_connecting
            or self._rf_runner.is_running
        )
        return busy or time.monotonic() < self._start_guard_until

    def _on_config_source_changed(self, source_id: str) -> None:
        if self.is_transport_busy():
            return
        self.set_source(source_id)

    def bind_toolbar(self, toolbar) -> None:
        self._toolbar_ref = toolbar
        self._spectrum.sliders.bind_toolbar(toolbar)
        span = getattr(toolbar, "_span", None)
        if span is not None and hasattr(span, "bind_mode_warning"):
            span.bind_mode_warning(self._notify_mode_restriction)
        if hasattr(self._spectrum.sliders, "bind_mode_warning"):
            self._spectrum.sliders.bind_mode_warning(self._notify_mode_restriction)

    def _notify_mode_restriction(self, restriction) -> None:
        from gui.monitor.monitor_mode_notify import format_mode_restriction

        msg = format_mode_restriction(restriction)
        self.status_changed.emit(msg)
        self._spectrum.set_alert_message(msg, tone="warn")

    def _notify_mode_restriction_from_key(self, i18n_key: str) -> None:
        from core.monitor.monitor_mode_guard import ModeRestriction

        self._notify_mode_restriction(ModeRestriction(i18n_key))

    def _prepare_source_for_start(self, source_id: str) -> None:
        if self._engine.is_running or self._engine.is_connecting:
            return
        if (
            self.get_params().source_id != source_id
            or self._engine.source_impl_id != source_id
        ):
            _ok, msg = self._engine.set_source(source_id)
            updated = self.get_params().copy()
            updated.source_id = source_id
            from core.rf.source_profile import apply_analyzer_source_restrictions

            apply_analyzer_source_restrictions(updated)
            updated.max_span_hz = max_span_hz_for_source(
                source_id,
                operating_mode=updated.operating_mode,
                center_freq_hz=updated.center_freq_hz,
            )
            refresh_capture_and_span_limits(updated)
            self.apply_params(updated)
            self._config.set_status_message(msg)

    def _apply_params_from_dock_sliders(self, params: SpectrumParams) -> None:
        from core.monitor.monitor_flow_log import RF_GAIN_PARAM_KEYS, changed_param_key_names

        merged = self.get_params().copy()
        gain_keys = (
            "lna_gain_db",
            "vga_gain_db",
            "rf_amp_enable",
            "rf_attenuation_db",
        )
        display_keys = (
            "ref_level_dbm",
            "ref_range_db",
            "ref_scale_auto",
            "ampt_mode",
            "vertical_divisions",
            "ref_offset_db",
            "amplitude_unit",
        )
        for key in gain_keys + display_keys:
            setattr(merged, key, getattr(params, key))
        changed = changed_param_key_names(self.get_params(), merged, gain_keys + display_keys)
        if changed and all(key in RF_GAIN_PARAM_KEYS for key in changed):
            self.apply_rf_gain_params(merged)
            return
        self.apply_params(merged)
        self.toolbar_sync_requested.emit(self.get_params())

    def _apply_dock_settings(self, mode: str, auto_sec: float) -> None:
        updated = self.get_params().copy()
        updated.dock_collapse_mode = str(mode)
        updated.dock_auto_collapse_sec = float(auto_sec)
        self.apply_params(updated)

    def _apply_params_from_overlay_sliders(self, params: SpectrumParams) -> None:
        merged = self.get_params().copy()
        for key in (
            "center_freq_hz",
            "selected_freq_hz",
            "span_hz",
            "manual_span_hz",
            "last_span_hz",
            "span_mode",
            "sample_rate_hz",
            "baseband_filter_bw_hz",
            "baseband_filter_auto",
            "freq_readout",
            "freq_pan_mode",
            "freq_step_hz",
            "freq_offset_hz",
            "freq_input_mode",
            "marker_start_hz",
            "marker_stop_hz",
        ):
            setattr(merged, key, getattr(params, key))
        self.apply_params(merged)
        self.toolbar_sync_requested.emit(self.get_params())

    def _apply_params_from_status_strip(self, params: SpectrumParams) -> None:
        merged = self.get_params().copy()
        for key in (
            "center_freq_hz",
            "span_hz",
            "manual_span_hz",
            "last_span_hz",
            "span_mode",
            "sample_rate_hz",
            "baseband_filter_bw_hz",
            "baseband_filter_auto",
            "ref_level_dbm",
            "ref_range_db",
            "ref_scale_auto",
            "ref_offset_db",
            "amplitude_unit",
            "ampt_mode",
            "rf_attenuation_db",
            "lna_gain_db",
            "vga_gain_db",
            "rf_amp_enable",
            "rbw_hz",
            "rbw_auto",
            "fft_size",
            "fft_auto",
            "capture_mode",
            "trace_smooth_auto",
            "trace_smooth_bins",
            "sweep_time_ms",
            "sweep_auto",
            "sweep_trigger_mode",
            "trace_mode",
            "detector",
            "freq_readout",
            "freq_step_hz",
            "selected_freq_hz",
            "marker_start_hz",
            "marker_stop_hz",
            "status_show_start",
            "status_show_center",
            "status_show_stop",
            "status_show_step",
            "status_show_readout",
            "status_show_span",
            "status_show_rbw",
            "status_show_vbw",
            "status_show_sweep",
            "status_show_trace",
            "status_show_detector",
            "status_show_ref",
            "status_show_ref_range",
            "status_show_lna",
            "status_show_preamp",
            "status_show_vga",
            "status_show_att",
            "status_show_capture",
            "status_show_fps",
        ):
            if hasattr(params, key):
                setattr(merged, key, getattr(params, key))
        self.apply_params(merged)
        self.toolbar_sync_requested.emit(self.get_params())

    def _on_marker_settings_requested(self) -> None:
        self._config.focus_markers_panel()

    def _on_marker_activate_requested(self, marker_id: int) -> None:
        params = self.get_params()
        if int(params.active_marker_id) == int(marker_id):
            return
        updated = params.copy()
        updated.active_marker_id = int(marker_id)
        from core.monitor.marker_bank import sync_selected_freq_from_active_marker

        sync_selected_freq_from_active_marker(updated)
        self.apply_params(updated)

    def apply_toolbar_params(self, toolbar_params: SpectrumParams) -> None:
        """Fusiona solo los campos que cambió la toolbar (evita pisar FC/VFO vivos)."""
        from core.monitor.monitor_flow_log import (
            RF_GAIN_PARAM_KEYS,
            TOOLBAR_PARAM_KEYS,
            changed_param_key_names,
            is_sdr_rf_gain_only_patch,
        )

        current = self.get_params()
        keys = changed_param_key_names(current, toolbar_params, TOOLBAR_PARAM_KEYS)
        if not keys:
            return
        merged = current.copy()
        for key in keys:
            setattr(merged, key, getattr(toolbar_params, key))
        if is_sdr_rf_gain_only_patch(current, merged) and all(
            key in RF_GAIN_PARAM_KEYS for key in keys
        ):
            self.apply_rf_gain_params(merged)
            return
        self.apply_params(merged)

    def apply_rf_gain_params(self, source: SpectrumParams) -> None:
        """LNA/VGA/P sin refrescar panel RADIO ni reiniciar demodulación."""
        from core.monitor.hackrf_rx_gains import snap_gains_for_source
        from core.monitor.monitor_flow_log import RF_GAIN_PARAM_KEYS, changed_param_key_names
        from i18n.json_translation import tr

        prev = self.get_params()
        keys = changed_param_key_names(prev, source, RF_GAIN_PARAM_KEYS)
        if not keys:
            return
        updated = prev.copy()
        for key in keys:
            setattr(updated, key, getattr(source, key))
        lna, vga, amp, warn_key = snap_gains_for_source(
            updated.source_id,
            updated.lna_gain_db,
            updated.vga_gain_db,
            updated.rf_amp_enable,
        )
        updated.lna_gain_db = lna
        updated.vga_gain_db = vga
        updated.rf_amp_enable = amp
        if updated.capture_mode == "sweep" or updated.operating_mode_enum() is MonitorOperatingMode.SDR:
            updated.rf_attenuation_db = max(0.0, 40.0 - updated.lna_gain_db)
        if warn_key:
            msg = tr(warn_key).format(
                lna=int(updated.lna_gain_db),
                vga=int(updated.vga_gain_db),
                sum_db=int(updated.lna_gain_db) + int(updated.vga_gain_db),
            )
            self.status_changed.emit(msg)
            self._spectrum.set_alert_message(msg, tone="warn")
        with self._project_params_lock:
            self._project_params = updated.copy()
        self._rf_view_model.apply_params(updated)
        self.toolbar_sync_requested.emit(updated)
        self._schedule_layout_persist()

    def _ensure_sdr_audio_receive(self, params: SpectrumParams) -> None:
        """Mantiene audio/demod activos en SDR IQ analógico (no pisa modo DIG)."""
        from core.monitor.analog_demod_profiles import normalize_analog_demod_mode

        if not params.operating_mode_enum().demod_enabled():
            return
        if params.capture_mode != "iq":
            return
        if normalize_analog_demod_mode(params.demod_mode) == "dig":
            return
        params.audio_enabled = True

    def apply_params(self, params: SpectrumParams) -> None:
        self._sync_persisted_radio_params_immediate(params)
        if self._apply_params_busy:
            self._pending_apply_params = params.copy()
            return
        self._apply_params_busy = True
        try:
            self._apply_params_impl(params)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).exception("apply_params failed")
            from i18n.json_translation import tr

            msg = tr("monitor_apply_params_error").format(error=str(exc))
            self.status_changed.emit(msg)
            self._spectrum.set_alert_message(msg, tone="error")
        finally:
            self._apply_params_busy = False
            pending = self._pending_apply_params
            self._pending_apply_params = None
            if pending is not None:
                self.apply_params(pending)

    def _sync_persisted_radio_params_immediate(self, params: SpectrumParams) -> None:
        """Refleja mute/volumen/demod en _project_params al instante."""
        from core.monitor.monitor_flow_log import PERSIST_RADIO_UI_KEYS

        with self._project_params_lock:
            current = self._project_params.copy()
            for key in PERSIST_RADIO_UI_KEYS:
                if hasattr(params, key) and hasattr(current, key):
                    setattr(current, key, getattr(params, key))
            self._project_params = current
        self._engine.set_params(
            squelch_db=float(params.squelch_db),
            squelch_enabled=bool(params.squelch_enabled),
        )

    def _apply_demod_params_from_panel(self, panel_params: SpectrumParams) -> None:
        """Fusiona campos RADIO del panel sin pisar modo/captura/audio vivo."""
        from core.monitor.monitor_flow_log import (
            RADIO_PANEL_PATCH_KEYS,
            RADIO_SOFT_PARAM_KEYS,
            changed_param_key_names,
        )

        prev = self.get_params()
        changed = changed_param_key_names(prev, panel_params, RADIO_PANEL_PATCH_KEYS)
        if not changed:
            return
        merged = prev.copy()
        for key in changed:
            setattr(merged, key, getattr(panel_params, key))
        if all(key in RADIO_SOFT_PARAM_KEYS for key in changed):
            self._apply_radio_soft_params(merged, prev, changed)
            return
        self.apply_params(merged)

    def _apply_soft_param_patch(self, patch: object) -> None:
        """Toggles WFM/RADIO — solo las claves del dict, nunca el estado obsoleto del panel."""
        if not isinstance(patch, dict) or not patch:
            return
        from core.monitor.monitor_flow_log import (
            RF_GAIN_PARAM_KEYS,
            RADIO_SOFT_PARAM_KEYS,
        )

        prev = self.get_params()
        merged = prev.copy()
        for key, value in patch.items():
            if hasattr(merged, key):
                setattr(merged, key, value)
        changed = [str(key) for key in patch if hasattr(merged, key)]
        if not changed:
            return
        if any(key not in RADIO_SOFT_PARAM_KEYS and key not in RF_GAIN_PARAM_KEYS for key in changed):
            self.apply_params(merged)
            return
        if any(key in RF_GAIN_PARAM_KEYS for key in changed):
            self.apply_rf_gain_params(merged)
            prev = self.get_params()
            merged = prev.copy()
            for key, value in patch.items():
                if hasattr(merged, key):
                    setattr(merged, key, value)
        soft_keys = [key for key in changed if key in RADIO_SOFT_PARAM_KEYS]
        if soft_keys:
            self._apply_radio_soft_params(merged, prev, soft_keys)
        self._config.sync_radio_params_snapshot(self.get_params())

    def _apply_radio_soft_params(
        self,
        merged: SpectrumParams,
        prev: SpectrumParams,
        changed: list[str],
    ) -> None:
        """Mute/squelch/toggles WFM sin reconfigurar captura ni reconstruir waterfall."""
        from PyQt6.QtCore import QTimer

        with self._project_params_lock:
            self._project_params = merged.copy()
        self._engine.set_params(
            squelch_db=float(merged.squelch_db),
            squelch_enabled=bool(merged.squelch_enabled),
        )
        self._audio_out.set_volume(merged.audio_volume)
        demod_chain_keys = {
            "demod_wfm_stereo",
            "demod_wfm_lowpass",
            "demod_noise_blanker_db",
            "demod_deemphasis",
            "demod_iq_correction",
            "demod_iq_invert",
            "demod_agc_attack",
            "demod_agc_decay",
            "demod_bandwidth_hz",
        }
        if self._rf_runner.is_running and self._engine.is_demod_auxiliary and any(
            key in demod_chain_keys for key in changed
        ):
            self._engine.reset_demod_signal_chain()
        if (
            "demod_wfm_stereo" in changed
            and prev.demod_wfm_stereo != merged.demod_wfm_stereo
            and self._audio_out.is_active
        ):
            wfm = (merged.demod_mode or "").lower() in ("wfm", "fm")
            stereo = bool(merged.demod_wfm_stereo and wfm)
            QTimer.singleShot(0, lambda s=stereo: self._restart_demod_audio_channels(s))
        if "demod_bandwidth_hz" in changed:
            self._spectrum.set_analyzer_params(merged)
        if "show_demod_bandwidth" in changed:
            self._spectrum.set_analyzer_params(merged)
        if "freq_readout" in changed or "demod_snap_interval" in changed:
            self._spectrum.set_analyzer_params(merged)
        self._config.sync_radio_bandwidth_ui(merged)
        if changed != ["demod_wfm_rds"]:
            self._schedule_layout_persist()

    def apply_audio_volume(self, volume: float) -> None:
        """Solo volumen de audio — sin repintar espectro ni reconfigurar captura."""
        clamped = max(0.0, min(1.0, float(volume)))
        current = self.get_params()
        if abs(current.audio_volume - clamped) < 0.001:
            return
        with self._project_params_lock:
            updated = self._project_params.copy()
            updated.audio_volume = clamped
            self._project_params = updated
        self._engine.set_params(audio_volume=clamped)
        self._audio_out.set_volume(clamped)
        self._config.set_radio_audio_volume(clamped)
        self._schedule_layout_persist()

    def _apply_params_impl(self, params: SpectrumParams) -> None:
        from core.monitor.monitor_flow_log import (
            DISPLAY_PARAM_KEYS,
            HARDWARE_PARAM_KEYS,
            diff_param_keys,
            infer_apply_source,
            is_sdr_rf_gain_only_patch,
            log_apply_params,
        )

        prev = self.get_params()
        updated = params.copy()
        ch_svc = self._get_channelization_service() if self._get_channelization_service else None
        if ch_svc is not None and updated.freq_input_mode != prev.freq_input_mode:
            state = ch_svc.get_state()
            state.input_mode = updated.freq_input_mode
            state.show_spectrum_allocations = updated.freq_input_mode == "channel"
            ch_svc.save_state(state)
            self.refresh_channelization_ui()
        gain_only_sdr = is_sdr_rf_gain_only_patch(prev, params)
        from core.monitor.hackrf_rx_gains import snap_gains_for_source
        from i18n.json_translation import tr

        lna, vga, amp, warn_key = snap_gains_for_source(
            updated.source_id,
            updated.lna_gain_db,
            updated.vga_gain_db,
            updated.rf_amp_enable,
        )
        updated.lna_gain_db = lna
        updated.vga_gain_db = vga
        updated.rf_amp_enable = amp
        if updated.capture_mode == "sweep" or updated.operating_mode_enum() is MonitorOperatingMode.SDR:
            updated.rf_attenuation_db = max(0.0, 40.0 - updated.lna_gain_db)
        if warn_key:
            msg = tr(warn_key).format(
                lna=int(updated.lna_gain_db),
                vga=int(updated.vga_gain_db),
                sum_db=int(updated.lna_gain_db) + int(updated.vga_gain_db),
            )
            self.status_changed.emit(msg)
            self._spectrum.set_alert_message(msg, tone="warn")
        if updated.operating_mode != prev.operating_mode:
            updated.apply_operating_mode()
        clamp_center_to_source(updated)
        if not gain_only_sdr:
            if updated.span_mode == "manual":
                updated.manual_span_hz = max(0.0, updated.manual_span_hz or updated.span_hz)
            from core.monitor.monitor_freq_span_logic import sync_span_geometry

            refresh_capture_and_span_limits(updated)
            if updated.span_mode == "manual" and updated.manual_span_hz > 0.0:
                sync_span_geometry(updated)
                refresh_capture_and_span_limits(updated)
        else:
            from core.monitor.monitor_mode_profile import max_span_hz_for_source

            updated.max_span_hz = max_span_hz_for_source(
                updated.source_id,
                operating_mode=updated.operating_mode,
                center_freq_hz=updated.center_freq_hz,
            )
        if updated.operating_mode_enum() is MonitorOperatingMode.SDR and not gain_only_sdr:
            if updated.freq_readout == "f":
                from core.monitor.analog_demod_profiles import snap_vfo_freq_hz

                tune_hz = float(updated.selected_freq_hz)
                if tune_hz <= 0.0:
                    tune_hz = float(updated.center_freq_hz)
                updated.vfo_freq_hz = snap_vfo_freq_hz(tune_hz, updated.demod_snap_interval)
                updated.selected_freq_hz = updated.vfo_freq_hz
            else:
                updated.vfo_freq_hz = updated.center_freq_hz
            updated.sync_iq_display()
        if updated.capture_mode == "iq" and updated.sweep_trigger_mode == "manual":
            updated.sweep_trigger_mode = "continuous"
            updated.single_sweep_pending = False
            self._trace_update_armed = True
        if updated.capture_mode == "iq" and not gain_only_sdr:
            from core.monitor.iq_sdr_profile import sync_iq_hardware

            rate_or_span_changed = (
                abs(updated.sample_rate_hz - prev.sample_rate_hz) > 1.0
                or abs(updated.span_hz - prev.span_hz) > 1.0
            )
            if rate_or_span_changed:
                sync_iq_hardware(updated)
                from core.monitor.monitor_iq_rf_logic import ensure_baseband_filter_valid

                ensure_baseband_filter_valid(updated)
                if updated.span_mode == "manual":
                    updated.manual_span_hz = updated.span_hz
                    updated.apply_span_as_sample_rate()
            updated.marker_auto_pan = False
        if updated.operating_mode_enum() is MonitorOperatingMode.SDR and not gain_only_sdr:
            updated.sync_receive_mode_effects()
        if updated.freq_readout == "f" and not gain_only_sdr:
            from core.monitor.marker_bank import sync_selected_freq_from_active_marker

            sync_selected_freq_from_active_marker(updated)
        if updated.capture_mode == "iq" and updated.span_mode == "manual" and not gain_only_sdr:
            updated.sync_iq_display()
        if not gain_only_sdr:
            if not self._marker_drag_active:
                updated = ensure_marker_visible(updated)
        from core.rf.bridge import prepare_params_for_capture

        updated = prepare_params_for_capture(updated, preserve_iq_span=gain_only_sdr)
        updated = self._rf_view_model.apply_params(updated)
        if (
            updated.span_mode == "full"
            and prev.span_mode != "full"
            and updated.capture_mode == "sweep"
        ):
            self.status_changed.emit(tr("monitor_full_span_sweep_hint"))
        prev_trace = self.get_params().trace_mode
        prev_fft_size = self.get_params().fft_size
        prev_fft_auto = self.get_params().fft_auto
        prev_smooth_auto = self.get_params().trace_smooth_auto
        prev_smooth_bins = self.get_params().trace_smooth_bins
        prev_trigger_mode = self.get_params().sweep_trigger_mode
        display_changes = diff_param_keys(prev, updated, DISPLAY_PARAM_KEYS)
        hardware_changes = diff_param_keys(prev, updated, HARDWARE_PARAM_KEYS)
        log_apply_params(
            source=infer_apply_source(),
            display_changes=display_changes,
            hardware_changes=hardware_changes,
            triggers_reconfigure=bool(hardware_changes) and self._rf_runner.is_running,
            running=self._engine.is_running or self._rf_runner.is_running,
        )
        self._ensure_sdr_audio_receive(updated)
        with self._project_params_lock:
            self._project_params = updated.copy()
        self._engine.set_params(
            request_hw_reconfigure=not self._rf_runner.is_running,
            center_freq_hz=updated.center_freq_hz,
            span_hz=updated.span_hz,
            manual_span_hz=updated.manual_span_hz,
            last_span_hz=updated.last_span_hz,
            analyzer_span_hz=updated.analyzer_span_hz,
            analyzer_span_mode=updated.analyzer_span_mode,
            max_span_hz=updated.max_span_hz,
            span_mode=updated.span_mode,
            ref_level_dbm=updated.ref_level_dbm,
            ref_offset_db=updated.ref_offset_db,
            ref_range_db=updated.ref_range_db,
            amplitude_unit=updated.amplitude_unit,
            rf_attenuation_db=updated.rf_attenuation_db,
            lna_gain_db=updated.lna_gain_db,
            vga_gain_db=updated.vga_gain_db,
            rf_amp_enable=updated.rf_amp_enable,
            rf_bias_tee_enable=updated.rf_bias_tee_enable,
            ref_scale_auto=updated.ref_scale_auto,
            ampt_mode=updated.ampt_mode,
            rbw_hz=updated.rbw_hz,
            rbw_auto=updated.rbw_auto,
            fft_auto=updated.fft_auto,
            trace_smooth_auto=updated.trace_smooth_auto,
            trace_smooth_bins=updated.trace_smooth_bins,
            sweep_time_ms=updated.sweep_time_ms,
            sweep_auto=updated.sweep_auto,
            sweep_mode=updated.sweep_mode,
            sweep_trigger_mode=updated.sweep_trigger_mode,
            sweep_trigger_period_sec=updated.sweep_trigger_period_sec,
            single_sweep_pending=updated.single_sweep_pending,
            trace_mode=updated.trace_mode,
            detector=updated.detector,
            fft_size=updated.fft_size,
            sample_rate_hz=updated.sample_rate_hz,
            baseband_filter_bw_hz=updated.baseband_filter_bw_hz,
            baseband_filter_auto=updated.baseband_filter_auto,
            vertical_divisions=updated.vertical_divisions,
            horizontal_divisions=updated.horizontal_divisions,
            capture_mode=updated.capture_mode,
            operating_mode=updated.operating_mode,
            vfo_freq_hz=updated.vfo_freq_hz,
            demod_mode=updated.demod_mode,
            demod_bandwidth_hz=updated.demod_bandwidth_hz,
            demod_snap_interval=updated.demod_snap_interval,
            demod_deemphasis=updated.demod_deemphasis,
            demod_noise_blanker_db=updated.demod_noise_blanker_db,
            demod_wfm_stereo=updated.demod_wfm_stereo,
            demod_wfm_rds=updated.demod_wfm_rds,
            demod_wfm_lowpass=updated.demod_wfm_lowpass,
            demod_iq_correction=updated.demod_iq_correction,
            demod_iq_invert=updated.demod_iq_invert,
            demod_agc_attack=updated.demod_agc_attack,
            demod_agc_decay=updated.demod_agc_decay,
            squelch_db=updated.squelch_db,
            squelch_enabled=updated.squelch_enabled,
            show_demod_bandwidth=updated.show_demod_bandwidth,
            recorder_mode=updated.recorder_mode,
            recorder_directory=updated.recorder_directory,
            recorder_filename=updated.recorder_filename,
            config_panel_collapsed=updated.config_panel_collapsed,
            waterfall_panel_collapsed=updated.waterfall_panel_collapsed,
            audio_volume=updated.audio_volume,
            audio_muted=updated.audio_muted,
            audio_enabled=updated.audio_enabled,
            digital_analysis_enabled=updated.digital_analysis_enabled,
            digital_profile=updated.digital_profile,
            digital_symbol_rate_hz=updated.digital_symbol_rate_hz,
            digital_mod_order=updated.digital_mod_order,
            supervision_enabled=updated.supervision_enabled,
            freq_readout=updated.freq_readout,
            freq_pan_mode=updated.freq_pan_mode,
            freq_step_hz=updated.freq_step_hz,
            freq_offset_hz=updated.freq_offset_hz,
            freq_input_mode=updated.freq_input_mode,
            selected_freq_hz=updated.selected_freq_hz,
            marker_start_hz=updated.marker_start_hz,
            marker_stop_hz=updated.marker_stop_hz,
            status_show_start=updated.status_show_start,
            status_show_center=updated.status_show_center,
            status_show_stop=updated.status_show_stop,
            status_show_step=updated.status_show_step,
            status_show_readout=updated.status_show_readout,
            status_show_span=updated.status_show_span,
            status_show_rbw=updated.status_show_rbw,
            status_show_vbw=updated.status_show_vbw,
            status_show_sweep=updated.status_show_sweep,
            status_show_trace=updated.status_show_trace,
            status_show_detector=updated.status_show_detector,
            status_show_ref=updated.status_show_ref,
            status_show_ref_range=updated.status_show_ref_range,
            status_show_lna=updated.status_show_lna,
            status_show_preamp=updated.status_show_preamp,
            status_show_vga=updated.status_show_vga,
            status_show_att=updated.status_show_att,
            status_show_capture=updated.status_show_capture,
            status_show_fps=updated.status_show_fps,
            waterfall_min_db=updated.waterfall_min_db,
            waterfall_max_db=updated.waterfall_max_db,
            waterfall_auto_levels=updated.waterfall_auto_levels,
            waterfall_contrast_auto=updated.waterfall_contrast_auto,
            waterfall_colormap=updated.waterfall_colormap,
            dock_collapse_mode=updated.dock_collapse_mode,
            dock_auto_collapse_sec=updated.dock_auto_collapse_sec,
            marker_show_line=updated.marker_show_line,
            marker_show_freq=updated.marker_show_freq,
            marker_show_level=updated.marker_show_level,
            marker_show_snr=updated.marker_show_snr,
            marker_auto_pan=updated.marker_auto_pan,
            active_marker_id=updated.active_marker_id,
            markers=[marker.copy() for marker in updated.markers],
        )
        if self._rf_runner.is_running and self._engine.is_demod_auxiliary and hardware_changes:
            from core.monitor.monitor_flow_log import RF_GAIN_PARAM_KEYS, changed_param_key_names

            hw_keys = changed_param_key_names(prev, updated, HARDWARE_PARAM_KEYS)
            if any(key not in RF_GAIN_PARAM_KEYS for key in hw_keys):
                self._engine.reset_demod_signal_chain()
        current = updated.copy()
        demod_chain_keys = (
            "demod_wfm_stereo",
            "demod_wfm_lowpass",
            "demod_noise_blanker_db",
            "demod_mode",
            "demod_deemphasis",
            "demod_bandwidth_hz",
        )
        if self._engine.is_running and any(
            getattr(prev, key, None) != getattr(current, key, None) for key in demod_chain_keys
        ):
            self._engine.reset_demod_signal_chain()
        if prev.demod_wfm_stereo != current.demod_wfm_stereo and self._audio_out.is_active:
            wfm = (current.demod_mode or "").lower() in ("wfm", "fm")
            stereo = bool(current.demod_wfm_stereo and wfm)
            QTimer.singleShot(0, lambda s=stereo: self._restart_demod_audio_channels(s))
        if prev.ref_scale_auto != current.ref_scale_auto:
            self._auto_ref_smooth = None
        if prev.capture_mode != current.capture_mode:
            self._auto_ref_smooth = None
            self._waterfall.clear_history()
            self._rf_view_model.reset_trace_state()
            if current.capture_mode == "iq" and prev.capture_mode == "sweep":
                if current.ref_scale_auto:
                    self._spectrum.set_display_params(
                        current.ref_level_dbm,
                        current.ref_range_db,
                    )
        if current.trace_mode != prev_trace:
            self._rf_view_model.reset_trace_state()
        if current.fft_size != prev_fft_size:
            self._rf_view_model.reset_trace_state()
            if current.capture_mode == "iq":
                self._waterfall.clear_history()
        elif current.fft_auto != prev_fft_auto and current.capture_mode == "iq":
            self._rf_view_model.reset_trace_state()
        if (
            current.trace_smooth_auto != prev_smooth_auto
            or current.trace_smooth_bins != prev_smooth_bins
        ):
            self._rf_view_model.reset_trace_state()
        self._sync_trigger_state(current, prev_trigger_mode)
        if not self._engine.is_running:
            self._spectrum.set_display_params(current.ref_level_dbm, current.ref_range_db)
            self._waterfall.set_display_params(current.ref_level_dbm, current.ref_range_db)
        elif any(
            k in display_changes
            for k in ("ref_level_dbm", "ref_range_db", "ref_scale_auto", "amplitude_unit", "ref_offset_db")
        ):
            if current.ref_scale_auto and self._last_display_frame is not None:
                ref = self._last_display_frame.ref_level_dbm
                rng = self._last_display_frame.ref_range_db
            else:
                ref = current.ref_level_dbm
                rng = current.ref_range_db
            self._spectrum.set_display_params(ref, rng)
            self._waterfall.set_display_params(ref, rng)
        self._audio_out.set_volume(current.audio_volume)
        if (
            hardware_changes
            and self._engine.is_running
            and current.demod_enabled()
            and not self._audio_out.is_active
        ):
            self._audio_out.start(
                stereo=bool(
                    current.demod_wfm_stereo
                    and (current.demod_mode or "").lower() in ("wfm", "fm")
                )
            )
            self._config.update_audio_output(active=True)
        self.params_updated.emit(current)
        if (
            prev.freq_input_mode != current.freq_input_mode
            or abs(float(prev.center_freq_hz) - float(current.center_freq_hz)) > 0.5
            or abs(float(prev.selected_freq_hz) - float(current.selected_freq_hz)) > 0.5
        ):
            self.toolbar_sync_requested.emit(current)
        if not self._marker_drag_active:
            self._config.set_monitor_params(current, prev=prev)
        self._schedule_layout_persist()

    def arm_trigger(self) -> None:
        params = self.get_params()
        if params.sweep_trigger_mode not in ("manual", "periodic"):
            return
        self._trace_update_armed = True
        self._engine.set_params(single_sweep_pending=True)
        if self._spectrum.alert_tone() == "info":
            self._spectrum.clear_alert_message()

    def _sync_trigger_state(self, params: SpectrumParams, prev_mode: str) -> None:
        mode = params.sweep_trigger_mode
        if mode == "manual" and params.capture_mode == "sweep":
            if prev_mode != "manual":
                self._trace_update_armed = False
            self._trigger_timer.stop()
            self._update_manual_trigger_alert()
        elif mode == "manual":
            self._trace_update_armed = True
            self._trigger_timer.stop()
        elif mode == "periodic":
            self._trigger_timer.setInterval(max(200, int(params.sweep_trigger_period_sec * 1000)))
            if self._engine.is_running:
                self._trigger_timer.start()
            else:
                self._trigger_timer.stop()
        else:
            self._trace_update_armed = True
            self._trigger_timer.stop()

    def _on_periodic_trigger(self) -> None:
        if self.get_params().sweep_trigger_mode != "periodic":
            self._trigger_timer.stop()
            return
        self.arm_trigger()

    def set_operating_mode(self, mode: str) -> None:
        updated = self.get_params().copy()
        previous = normalize_operating_mode(updated.operating_mode)
        normalized = normalize_operating_mode(mode)
        if previous == normalized:
            return
        from core.monitor.monitor_mode_guard import sdr_mode_blocked_for_source

        blocked = sdr_mode_blocked_for_source(updated)
        if blocked is not None and normalized is MonitorOperatingMode.SDR:
            self._notify_mode_restriction(blocked)
            return
        updated.operating_mode = normalized.value
        if normalized is MonitorOperatingMode.SDR:
            updated.vfo_freq_hz = updated.center_freq_hz
            updated.selected_freq_hz = updated.center_freq_hz
            updated.freq_readout = "f"
        from core.monitor.monitor_mode_profile import (
            instant_span_hz_for_source,
            transition_operating_mode,
        )

        span_clamped = transition_operating_mode(
            updated,
            previous_mode=previous,
            new_mode=normalized,
        )
        restored_analyzer = (
            previous is MonitorOperatingMode.SDR
            and normalized is MonitorOperatingMode.SPECTRUM
            and updated.manual_span_hz > instant_span_hz_for_source(updated.source_id) + 1.0
        )
        updated.apply_operating_mode()
        self.apply_params(updated)
        self.operating_mode_changed.emit(normalized.value)
        self.toolbar_sync_requested.emit(self.get_params())
        from i18n.json_translation import tr

        if span_clamped:
            instant_mhz = instant_span_hz_for_source(updated.source_id) / 1_000_000.0
            self.status_changed.emit(
                tr("monitor_sdr_span_clamped").format(span=f"{instant_mhz:.0f}")
            )
        elif restored_analyzer:
            self.status_changed.emit(tr("monitor_analyzer_span_restored"))

    def _on_marker_drag_active(self, active: bool) -> None:
        self._marker_drag_active = active
        if active:
            return
        params = self.get_params()
        if params.freq_readout != "f" or not params.marker_auto_pan or params.capture_mode == "iq":
            self._config.set_monitor_params(params)
            return
        from core.monitor.monitor_freq_span_logic import ensure_marker_visible

        updated = ensure_marker_visible(params)
        if updated is params:
            self._config.set_monitor_params(params)
            return
        self.apply_params(updated)

    def _on_spectrum_frequency(self, freq_hz: float) -> None:
        params = self.get_params()
        if params.freq_input_mode == "channel":
            ch_svc = (
                self._get_channelization_service()
                if self._get_channelization_service
                else None
            )
            if ch_svc is not None:
                from core.rf.channel_input import snap_channel_frequency

                freq_hz = snap_channel_frequency(ch_svc, freq_hz)
        if params.freq_readout == "f":
            updated = patch_selected_freq(params, freq_hz, clamp_visible=True)
        else:
            updated = patch_center_freq(params, freq_hz)
        self.apply_params(updated)

    def _on_span_zoom(self, factor: float, anchor_hz: float) -> None:
        if factor <= 0 or not math.isfinite(factor):
            return
        from core.monitor.monitor_mode_guard import zoom_out_requires_analyzer_mode
        from core.monitor.monitor_freq_span_logic import zoom_manual_span

        notice = zoom_out_requires_analyzer_mode(self.get_params(), factor)
        if notice is not None:
            self._notify_mode_restriction(notice)
        updated = zoom_manual_span(self.get_params(), factor, anchor_hz=anchor_hz)
        self.apply_params(updated)

    def start(self) -> None:
        self._user_stop_requested = False
        self._start_guard_until = time.monotonic() + 4.0
        from core.monitor.device_discovery import detect_sources, prefer_playable_source_id

        source_id = self._config.get_selected_source_id()
        descriptors = detect_sources()
        if not source_id or source_id == "mock":
            picked = prefer_playable_source_id(descriptors=descriptors)
            if picked != "mock":
                source_id = picked
        if source_id:
            self._prepare_source_for_start(source_id)
        self._rf_view_model.reset_trace_state()
        self._waterfall.clear_history()
        preflight = self.get_params().copy()
        if source_id:
            preflight.source_id = source_id
            from core.rf.source_profile import apply_analyzer_source_restrictions

            apply_analyzer_source_restrictions(preflight)
        refresh_capture_and_span_limits(preflight)
        if preflight.operating_mode_enum().demod_enabled():
            from core.monitor.analog_demod_profiles import normalize_analog_demod_mode, snap_vfo_freq_hz

            preflight.capture_mode = "iq"
            preflight.freq_readout = "f"
            preflight.audio_enabled = True
            preflight.show_demod_bandwidth = True
            preflight.sync_receive_mode_effects()
            if normalize_analog_demod_mode(preflight.demod_mode) in ("wfm", "fm", "nfm"):
                if float(preflight.demod_bandwidth_hz or 0) < 100_000.0:
                    preflight.demod_bandwidth_hz = 200_000.0
            tune_hz = float(preflight.selected_freq_hz or 0.0)
            if tune_hz <= 0.0:
                tune_hz = float(preflight.vfo_freq_hz or preflight.center_freq_hz)
            preflight.vfo_freq_hz = snap_vfo_freq_hz(tune_hz, preflight.demod_snap_interval)
            preflight.selected_freq_hz = preflight.vfo_freq_hz
            preflight.squelch_db = min(float(preflight.squelch_db), -100.0)
            from core.monitor.iq_sdr_profile import prepare_iq_for_play

            prepare_iq_for_play(preflight)
        self.apply_params(preflight)
        self._config.set_controls_busy(connecting=True, running=False)
        self.transport_changed.emit(False, True)
        self._config.set_status_message("Conectando…")
        release = getattr(self._engine, "release_hardware", None)
        if callable(release):
            release()
        if self._engine.is_demod_auxiliary or self._engine.is_running:
            self._engine.stop()
        self._rf_runner.sync_from_params(self.get_params())
        ok, msg = self._rf_runner.start()
        if ok:
            params = self.get_params()
            if params.demod_enabled() or params.digital_analysis_active():
                tap = self._rf_runner.create_demod_iq_source()
                if tap is None and params.demod_enabled():
                    from i18n.json_translation import tr

                    self.status_changed.emit(tr("monitor_demod_iq_tap_unavailable"))
                elif tap is not None:
                    self._engine.start_demod_auxiliary(tap, get_params=self.get_params)
            if params.demod_enabled():
                stereo = bool(
                    params.demod_wfm_stereo
                    and (params.demod_mode or "").lower() in ("wfm", "fm")
                )
                if not self._audio_out.is_active:
                    if self._audio_out.start(stereo=stereo):
                        self._audio_out.set_volume(params.audio_volume)
                        self._config.update_audio_output(active=True)
                else:
                    self._audio_out.set_volume(params.audio_volume)
            self._config.sync_radio_bandwidth_ui(params)
            self._spectrum.set_analyzer_params(params)
        if ok:
            self._last_frame_at = time.monotonic()
            self._frame_watchdog.start()
            self._spectrum.clear_alert_message()
            self._start_supervision_logging()
            self._maybe_start_supervision_rec_on_play()
            self.status_changed.emit(msg)
        else:
            self._config.set_controls_busy(connecting=False, running=False)
            self.transport_changed.emit(False, False)
            self._config.set_status_message(msg)
            self.status_changed.emit(msg)

    def stop(self) -> None:
        self._user_stop_requested = True
        self._pending_vfo_peak_snap = False
        self._vfo_snap_warmup_frames = 0
        self._start_guard_until = 0.0
        self._frame_watchdog.stop()
        had_fatal = bool(self._capture_exit_message())
        if self._rf_runner.is_running:
            self._rf_runner.stop()
        if self._engine.is_demod_auxiliary or self._engine.is_running:
            self._engine.stop()
        release = getattr(self._engine, "release_hardware", None)
        if callable(release):
            release()
        source_id = self.get_params().source_id
        idle = idle_message_for_source(source_id)
        if had_fatal:
            msg = self._capture_exit_message() or self._last_status_message
            self._config.set_status_message(msg)
            self.status_changed.emit(msg)
            self._spectrum.set_alert_message(msg, tone="error")
        else:
            self._config.set_status_message(idle)
            self._spectrum.clear_alert_message()
            self.status_changed.emit("Detenido")
        self._config.set_controls_busy(connecting=False, running=False)
        self.transport_changed.emit(False, False)
        self._stop_supervision_logging()

    def set_source(self, source_id: str) -> None:
        if self.is_transport_busy():
            return
        current = self.get_params().source_id
        if current == source_id:
            return
        _ok, msg = self._engine.set_source(source_id)
        updated = self.get_params().copy()
        updated.source_id = source_id
        from core.rf.source_profile import analyzer_source_status_hint, apply_analyzer_source_restrictions

        notices = apply_analyzer_source_restrictions(updated)
        updated.max_span_hz = max_span_hz_for_source(
            source_id,
            operating_mode=updated.operating_mode,
            center_freq_hz=updated.center_freq_hz,
        )
        refresh_capture_and_span_limits(updated)
        self.apply_params(updated)
        self._config.set_status_message(msg)
        self.status_changed.emit(msg)
        self.toolbar_sync_requested.emit(self.get_params())
        self.operating_mode_changed.emit(updated.operating_mode)
        from i18n.json_translation import tr

        for key in notices:
            self._notify_mode_restriction_from_key(key)
        hint = analyzer_source_status_hint(source_id)
        if hint:
            self.status_changed.emit(tr(hint))

    def shutdown(self) -> None:
        if self._supervision_engine is not None and self._supervision_engine.is_recording:
            self._stop_supervision_rec()
        if self._supervision_alarm_window is not None:
            self._supervision_alarm_window.force_close()
            self._supervision_alarm_window = None
        self._stop_recording()
        self._audio_out.stop()
        self._engine.stop()

    def persist_config_panel_collapsed(self, collapsed: bool) -> None:
        updated = self.get_params().copy()
        if updated.config_panel_collapsed == bool(collapsed):
            return
        updated.config_panel_collapsed = bool(collapsed)
        self.apply_params(updated)

    def persist_waterfall_panel_collapsed(self, collapsed: bool) -> None:
        updated = self.get_params().copy()
        if updated.waterfall_panel_collapsed == bool(collapsed):
            return
        updated.waterfall_panel_collapsed = bool(collapsed)
        self.apply_params(updated)

    def _on_record_toggled(self, active: bool) -> None:
        if active:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self) -> None:
        from core.monitor.monitor_export_paths import remember_save_path
        from i18n.json_translation import tr

        params = self.get_params()
        if not self._engine.is_running:
            self._config.update_recorder_state(params, recording=False, running=False)
            self.status_changed.emit(tr("monitor_recorder_need_capture"))
            return
        path = self._config.resolve_recorder_output_path(params)
        if path is None:
            return
        mode = (params.recorder_mode or "baseband").lower()
        ok, err = self._recorder.start(path, mode)
        if not ok:
            self._config.update_recorder_state(params, recording=False, running=self._engine.is_running)
            self.status_changed.emit(tr("monitor_recorder_start_error").format(error=err))
            return
        export_key = EXPORT_RECORD_AUDIO if mode == "audio" else EXPORT_RECORD_BASEBAND
        remember_save_path(export_key, str(path))
        label = path.name
        self._spectrum.set_recording_banner(tr("monitor_recording_banner").format(name=label))
        self._config.update_recorder_state(params, recording=True, running=True)
        self.status_changed.emit(tr("monitor_recorder_started").format(path=str(path)))

    def _stop_recording(self) -> None:
        from i18n.json_translation import tr

        if not self._recorder.is_active:
            self._spectrum.set_recording_banner("")
            params = self.get_params()
            self._config.update_recorder_state(
                params,
                recording=False,
                running=self._engine.is_running,
            )
            return
        path = self._recorder.stop()
        self._spectrum.set_recording_banner("")
        params = self.get_params()
        self._config.update_recorder_state(
            params,
            recording=False,
            running=self._engine.is_running,
        )
        if path is not None:
            self.status_changed.emit(tr("monitor_recorder_stopped").format(path=str(path)))

    def _on_recording_iq(self, samples, _sample_rate_hz: float) -> None:
        if self._recorder.is_active and self._recorder.mode == "baseband":
            self._recorder.write_iq(samples)

    def _sync_recorder_ui(self) -> None:
        params = self.get_params()
        self._config.update_recorder_state(
            params,
            recording=self._recorder.is_active,
            running=self._engine.is_running,
        )

    def _on_running_changed(self, running: bool) -> None:
        if not running:
            self._stop_recording()
            self._stop_supervision_logging()
            self._audio_out.stop()
            self._audio_error_shown = False
            self._config.update_audio_output(active=False)
            self._start_guard_until = min(self._start_guard_until, time.monotonic())
            self._trigger_timer.stop()
            self._frame_watchdog.stop()
            if not self._user_stop_requested:
                fatal = self._capture_exit_message()
                if fatal:
                    self._config.set_status_message(fatal)
                    self.status_changed.emit(fatal)
                    self._spectrum.set_alert_message(fatal, tone="error")
        else:
            self._last_frame_at = time.monotonic()
            self._frame_watchdog.start()
            self._start_supervision_logging()
            if self._spectrum.alert_tone() == "error":
                self._spectrum.clear_alert_message()
            params = self.get_params()
            if params.demod_enabled() and not self._audio_out.start(
                stereo=bool(params.demod_wfm_stereo and params.demod_mode.lower() in ("wfm", "fm"))
            ):
                if not self._audio_error_shown:
                    self._audio_error_shown = True
                    from i18n.json_translation import tr

                    err = self._audio_out.last_error or tr("monitor_radio_audio_error")
                    self._config.update_audio_output(active=False, error=err)
            elif params.demod_enabled():
                self._audio_out.set_volume(params.audio_volume)
                self._config.update_audio_output(active=True)
            if params.sweep_trigger_mode == "periodic":
                self._trigger_timer.setInterval(max(200, int(params.sweep_trigger_period_sec * 1000)))
                self._trigger_timer.start()
            elif _sweep_manual_trigger_active(params):
                self._trace_update_armed = False
                self._update_manual_trigger_alert()
            else:
                self._trace_update_armed = True
        connecting = self._engine.is_connecting and not running
        self._config.set_controls_busy(connecting=connecting, running=running)
        self.transport_changed.emit(running, connecting)
        params = self.get_params()
        params.running = running
        self.params_updated.emit(params)
        self._config.set_monitor_params(params)
        self._sync_recorder_ui()

    def auto_tune_sdr(self) -> None:
        if self._auto_tune_busy:
            return
        self._auto_tune_busy = True
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, self._run_auto_tune_sdr)

    def _run_auto_tune_sdr(self) -> None:
        from core.monitor.sdr_auto_tune import compute_sdr_auto_tune
        from i18n.json_translation import tr

        try:
            result = compute_sdr_auto_tune(self.get_params(), self.get_last_frame())
            if not result.ok:
                key = result.summary
                msg = tr(key) if key.startswith("monitor_") else key
                self.status_changed.emit(msg)
                if key == "monitor_auto_tune_not_sdr":
                    from core.monitor.monitor_mode_guard import demod_requires_sdr_mode

                    notice = demod_requires_sdr_mode(self.get_params())
                    if notice is not None:
                        self._notify_mode_restriction(notice)
                return
            self._apply_auto_tune_result(result.params)
            self.status_changed.emit(result.summary)
        finally:
            self._auto_tune_busy = False

    def _apply_auto_tune_result(self, tuned: SpectrumParams) -> None:
        """Aplica AUTO sin bloquear la GUI con apply_params completo durante PLAY."""
        from core.monitor.hackrf_rx_gains import snap_gains_for_source
        from core.monitor.monitor_flow_log import is_auto_tune_hw_unchanged
        from core.monitor.sdr_auto_tune import freeze_auto_tune_hw_for_live_capture, merge_auto_tune_params
        from i18n.json_translation import tr

        prev = self.get_params()
        merged = merge_auto_tune_params(prev, tuned)
        lna, vga, amp, warn_key = snap_gains_for_source(
            merged.source_id,
            merged.lna_gain_db,
            merged.vga_gain_db,
            merged.rf_amp_enable,
        )
        merged.lna_gain_db = lna
        merged.vga_gain_db = vga
        merged.rf_amp_enable = amp
        if merged.capture_mode == "sweep" or merged.operating_mode_enum() is MonitorOperatingMode.SDR:
            merged.rf_attenuation_db = max(0.0, 40.0 - merged.lna_gain_db)
        if warn_key:
            msg = tr(warn_key).format(
                lna=int(merged.lna_gain_db),
                vga=int(merged.vga_gain_db),
                sum_db=int(merged.lna_gain_db) + int(merged.vga_gain_db),
            )
            self.status_changed.emit(msg)
            self._spectrum.set_alert_message(msg, tone="warn")

        if self._rf_runner.is_running or self._engine.is_running:
            if not is_auto_tune_hw_unchanged(prev, merged):
                merged = freeze_auto_tune_hw_for_live_capture(prev, merged)
                self.status_changed.emit(tr("monitor_auto_tune_hw_deferred"))
            self._apply_auto_tune_live(prev, merged)
            return
        self.apply_params(merged)

    def _apply_auto_tune_live(self, prev: SpectrumParams, merged: SpectrumParams) -> None:
        """Ganancias + demod en vivo — sin prepare_params_for_capture ni waterfall."""
        from core.monitor.monitor_flow_log import (
            RF_GAIN_PARAM_KEYS,
            RADIO_PANEL_PATCH_KEYS,
            RADIO_SOFT_PARAM_KEYS,
            changed_param_key_names,
        )
        from core.monitor.sdr_auto_tune import merge_auto_tune_params

        gain_keys = changed_param_key_names(prev, merged, RF_GAIN_PARAM_KEYS)
        if gain_keys:
            self.apply_rf_gain_params(merged)
            prev = self.get_params()
            merged = merge_auto_tune_params(prev, merged)

        patch_keys = changed_param_key_names(prev, merged, RADIO_PANEL_PATCH_KEYS)
        soft_keys = [key for key in patch_keys if key in RADIO_SOFT_PARAM_KEYS]
        if soft_keys:
            self._apply_radio_soft_params(merged, prev, soft_keys)
        else:
            with self._project_params_lock:
                self._project_params = merged.copy()
            self._engine.set_params(
                squelch_db=float(merged.squelch_db),
                squelch_enabled=bool(merged.squelch_enabled),
            )

        current = self.get_params()
        self._config.set_monitor_params(current, prev=prev)
        self.toolbar_sync_requested.emit(current)
        self._spectrum.set_analyzer_params(current)
        self.params_updated.emit(current)
        self._schedule_layout_persist()

    def launch_welle_cli_sdr(self) -> None:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtWidgets import QMessageBox

        from core.monitor.dab_welle_backend import WELLE_PROJECT_URL, launch_welle_cli, probe_welle_cli
        from i18n.json_translation import tr

        probe = probe_welle_cli()
        if not probe.available:
            QDesktopServices.openUrl(QUrl(WELLE_PROJECT_URL))
            self.status_changed.emit(tr("monitor_dab_welle_missing"))
            return

        params = self.get_params()
        vfo_hz = float(params.vfo_freq_hz or params.center_freq_hz)
        parent = self._spectrum.window()

        if self._engine.is_running or self._engine.is_connecting:
            box = QMessageBox(parent)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle(tr("monitor_dab_welle_confirm_title"))
            box.setText(tr("monitor_dab_welle_confirm_body"))
            box.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if box.exec() != QMessageBox.StandardButton.Yes:
                return
            self.stop()

        result = launch_welle_cli(vfo_hz)
        if result.ok:
            self.status_changed.emit(
                tr(result.message_key).format(channel=result.channel, url=result.web_url)
            )
            return
        msg = tr(result.message_key)
        if result.command:
            msg = f"{msg} · {result.command}"
        self.status_changed.emit(msg)

    def _enqueue_frame(self, frame: SpectrumFrame) -> None:
        self.frame_ready.emit(frame)

    def _enqueue_demod_state(self, state) -> None:
        self.demod_state_ready.emit(state)

    def _enqueue_digital_analysis(self, state) -> None:
        self.digital_analysis_ready.emit(state)

    def _push_demod_pcm_direct(self, state) -> None:
        """Audio directo desde hilo demod (sin pasar por cola Qt)."""
        if not self._engine.is_demod_auxiliary and not self._engine.is_running:
            return
        params = self.get_params()
        if not params.demod_enabled() or state.pcm.size <= 0:
            return
        if not self._audio_out.is_active:
            stereo = bool(
                getattr(state, "stereo", False)
                or (
                    params.demod_wfm_stereo
                    and (params.demod_mode or "").lower() in ("wfm", "fm")
                )
            )
            if self._audio_out.start(stereo=stereo):
                self._audio_out.set_volume(params.audio_volume)
                self._config.update_audio_output(active=True)
            if not self._audio_out.is_active:
                return
        if params.audio_muted:
            return
        from core.monitor.demod_dsp import squelch_passes_audio

        squelch_open = squelch_passes_audio(
            squelch_enabled=bool(params.squelch_enabled),
            squelch_db=float(params.squelch_db),
            squelch_open=bool(state.squelch_open),
        )
        self._audio_out.push_pcm(
            state.pcm,
            squelch_open=squelch_open,
            volume=params.audio_volume,
            stereo=bool(getattr(state, "stereo", False)),
        )
        if self._recorder.is_active and self._recorder.mode == "audio" and squelch_open:
            self._recorder.write_pcm(state.pcm)

    def _restart_demod_audio_channels(self, stereo: bool) -> None:
        """Reconfigura mono/estéreo en el hilo GUI (QAudioSink no es thread-safe)."""
        from i18n.json_translation import tr

        params = self.get_params()
        if not params.demod_enabled():
            return
        if not self._audio_out.is_active:
            if not self._audio_out.restart(stereo=stereo):
                err = self._audio_out.last_error or tr("monitor_radio_audio_error")
                self._config.update_audio_output(active=False, error=err)
                return
        else:
            if not self._audio_out.restart(stereo=stereo):
                err = self._audio_out.last_error or tr("monitor_radio_audio_error")
                self._config.update_audio_output(active=False, error=err)
                return
        self._audio_out.set_volume(params.audio_volume)
        self._config.update_audio_output(active=True)

    def _on_demod_state(self, state) -> None:
        try:
            self._handle_demod_ui(state)
        except Exception:
            import logging

            logging.getLogger(__name__).exception("demod ui update failed")

    def _on_digital_analysis(self, state) -> None:
        try:
            self._config.update_digital_analysis(state)
            params = self.get_params()
            if (
                self._supervision_engine is not None
                and params.digital_analysis_active()
                and self._engine.is_running
            ):
                snapshot = self._supervision_engine.process_digital_analysis(
                    vfo_hz=float(params.vfo_freq_hz or params.center_freq_hz),
                    mer_db=state.mer_db,
                    mer_db_smoothed=getattr(state, "mer_db_smoothed", None),
                    sync_ok=bool(getattr(state, "sync_ok", False)),
                    engine_running=True,
                )
                if snapshot.transitions:
                    self._apply_supervision_snapshot(snapshot)
        except Exception:
            import logging

            logging.getLogger(__name__).exception("digital analysis ui update failed")

    def _handle_demod_ui(self, state) -> None:
        params = self.get_params()
        if not params.demod_enabled():
            return
        if not (self._engine.is_running or self._engine.is_demod_auxiliary):
            return
        self._config.update_demod_display(state)
        self._config.update_demod_signal_level(getattr(state, "level_dbfs", None))
        if self._audio_out.is_active:
            self._config.update_audio_output(active=True)

    def _enqueue_status(self, message: str) -> None:
        self.status_changed.emit(message)

    def _on_status_message(self, message: str) -> None:
        self._last_status_message = message
        lower = (message or "").lower()
        if any(token in lower for token in ("desconect", "disconnect", "interrumpida", "captura interrumpida")):
            self._spectrum.set_alert_message(message, tone="error")
        elif "esperando datos" in lower:
            self._spectrum.set_alert_message(message, tone="warn")
        elif "stream iq detenido" in lower or "hackrf_transfer terminó" in lower:
            self._spectrum.set_alert_message(message, tone="error")

    def _update_manual_trigger_alert(self) -> None:
        from i18n.json_translation import tr

        params = self.get_params()
        if not self._capture_is_running():
            return
        if _sweep_manual_trigger_active(params) and not self._trace_update_armed:
            self._spectrum.set_alert_message(tr("monitor_alert_manual_trigger"), tone="info")
        elif self._spectrum.alert_tone() != "error":
            self._spectrum.clear_alert_message()

    def _check_capture_health(self) -> None:
        from core.monitor.monitor_flow_log import log_frame_gap
        from i18n.json_translation import tr

        if not self._capture_is_running():
            return
        params = self.get_params()
        if _sweep_manual_trigger_active(params) and not self._trace_update_armed:
            self._update_manual_trigger_alert()
            return
        if self._last_frame_at <= 0:
            return
        stale_sec = 4.0 if params.capture_mode == "iq" else 12.0
        gap = time.monotonic() - self._last_frame_at
        if gap > stale_sec:
            log_frame_gap(gap, capture_mode=params.capture_mode)
            msg = tr("monitor_alert_no_data")
            self._spectrum.set_alert_message(msg, tone="warn")
            self.status_changed.emit(msg)

    def _maybe_snap_vfo_to_peak(self, frame: SpectrumFrame) -> None:
        if not self._pending_vfo_peak_snap:
            return
        if self._vfo_snap_warmup_frames > 0:
            self._vfo_snap_warmup_frames -= 1
            return
        params = self.get_params()
        if params.capture_mode != "iq" or not params.operating_mode_enum().demod_enabled():
            self._pending_vfo_peak_snap = False
            return
        from core.monitor.iq_fft import dc_exclude_hz, find_peak_excluding_dc
        import numpy as np

        peak = find_peak_excluding_dc(
            np.asarray(frame.freqs_hz, dtype=float),
            np.asarray(frame.power_db, dtype=float),
            center_freq_hz=params.center_freq_hz,
            sample_rate_hz=params.sample_rate_hz,
        )
        self._pending_vfo_peak_snap = False
        if peak is None:
            return
        peak_hz, peak_db = peak
        if abs(peak_hz - params.center_freq_hz) <= dc_exclude_hz(params.sample_rate_hz):
            return
        updated = patch_selected_freq(params, peak_hz)
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, lambda p=updated: self.apply_params(p))
        self.status_changed.emit(f"VFO → {peak_hz / 1e6:.3f} MHz · {peak_db:.0f} dBFS")

    def _deliver_frame(self, frame: SpectrumFrame) -> None:
        params = self.get_params()
        if _sweep_manual_trigger_active(params) and not self._trace_update_armed:
            self._update_manual_trigger_alert()
            return
        if _sweep_manual_trigger_active(params):
            self._trace_update_armed = False
        now = time.monotonic()
        self._last_frame_at = now
        if self._spectrum.alert_tone() in ("warn", "info"):
            self._spectrum.clear_alert_message()
        display = frame
        if params.ref_scale_auto:
            from core.rf.presentation.scale import stabilize_ref_level_dbm, stabilize_ref_range_db

            if self._auto_ref_smooth is None:
                stable_rng = stabilize_ref_range_db(display.ref_range_db, None)
                self._auto_ref_smooth = (display.ref_level_dbm, stable_rng)
            else:
                prev_ref, prev_rng = self._auto_ref_smooth
                stable_ref = stabilize_ref_level_dbm(display.ref_level_dbm, prev_ref)
                stable_rng = stabilize_ref_range_db(display.ref_range_db, prev_rng)
                self._auto_ref_smooth = (stable_ref, stable_rng)
            display = SpectrumFrame(
                freqs_hz=display.freqs_hz,
                power_db=display.power_db,
                center_freq_hz=display.center_freq_hz,
                span_hz=display.span_hz,
                ref_level_dbm=self._auto_ref_smooth[0],
                ref_range_db=self._auto_ref_smooth[1],
            )
        else:
            self._auto_ref_smooth = None
        self._maybe_snap_vfo_to_peak(display)
        processed = display
        self._last_display_frame = processed
        self._spectrum.update_frame(processed)
        self._waterfall.update_frame(processed)
        if self._toolbar_ref is not None and hasattr(self._toolbar_ref, "set_live_display_scale"):
            self._toolbar_ref.set_live_display_scale(
                processed.ref_level_dbm,
                processed.ref_range_db,
            )
        import numpy as np

        self._pending_marker_trace = (
            np.asarray(processed.freqs_hz, dtype=float),
            np.asarray(processed.power_db, dtype=float),
        )
        self._marker_trace_timer.start()
        self._process_supervision_frame(processed)
        if self._rf_runner.is_running:
            self._spectrum.status.set_runtime_telemetry(self._rf_runner.telemetry())
        if params.capture_mode == "iq" and now - self._last_status_peak_emit >= 5.0:
            from core.monitor.iq_fft import find_peak_excluding_dc
            from core.monitor.monitor_flow_log import _ensure_logger

            import numpy as np

            power = np.asarray(processed.power_db, dtype=float).reshape(-1)
            freqs = np.asarray(processed.freqs_hz, dtype=float).reshape(-1)
            peak = find_peak_excluding_dc(
                freqs,
                power,
                center_freq_hz=params.center_freq_hz,
                sample_rate_hz=params.sample_rate_hz,
            )
            if peak is not None:
                self._last_status_peak_emit = now
                _ensure_logger().debug(
                    "iq_peak source=%s peak_mhz=%.3f fc_mhz=%.3f lna=%s vga=%s rate_mhz=%.2f",
                    params.source_id,
                    peak[0] / 1e6,
                    params.center_freq_hz / 1e6,
                    params.lna_gain_db,
                    params.vga_gain_db,
                    params.sample_rate_hz / 1e6,
                )
        if now - self._last_rf_metrics_emit >= 0.5:
            from core.monitor.rf_metrics import compute_rf_link_metrics

            self.rf_metrics_ready.emit(compute_rf_link_metrics(processed, params))
            self._last_rf_metrics_emit = now
        if params.demod_enabled() and params.capture_mode == "iq":
            import numpy as np
            from core.monitor.marker_analysis import interpolate_power_db

            rf_dbm = interpolate_power_db(
                np.asarray(processed.freqs_hz, dtype=float),
                np.asarray(processed.power_db, dtype=float),
                float(params.vfo_freq_hz),
            )
            if rf_dbm is not None:
                self._engine.set_params(squelch_rf_level_dbm=float(rf_dbm))
        if params.ref_scale_auto:
            now = time.monotonic()
            if now - self._last_auto_ref_emit > 0.4:
                self._last_auto_ref_emit = now
                self._engine.set_params(
                    ref_level_dbm=display.ref_level_dbm,
                    ref_range_db=display.ref_range_db,
                )
                self._spectrum.set_display_params(
                    display.ref_level_dbm, display.ref_range_db
                )
                self._waterfall.set_display_params(
                    display.ref_level_dbm, display.ref_range_db
                )
        else:
            self._spectrum.set_display_params(
                params.ref_level_dbm, params.ref_range_db
            )
            self._waterfall.set_display_params(
                params.ref_level_dbm, params.ref_range_db
            )

    def get_last_frame(self) -> Optional[SpectrumFrame]:
        return self._last_display_frame

    def get_spectrum_widget(self) -> MonitorSpectrumWidget:
        return self._spectrum

    def get_waterfall_widget(self) -> MonitorWaterfallWidget:
        return self._waterfall

    def export_spectrum_csv(
        self,
        path: str,
        *,
        export_format: TraceExportFormat | str = TraceExportFormat.CONTROLADORF,
    ) -> tuple[bool, str]:
        from core.monitor.monitor_export import MonitorExportError, export_spectrum_trace_csv
        from i18n.json_translation import tr

        frame = self._last_display_frame
        if frame is None:
            return False, tr("monitor_export_no_trace")
        fmt = (
            export_format
            if isinstance(export_format, TraceExportFormat)
            else TraceExportFormat(str(export_format))
        )
        try:
            export_spectrum_trace_csv(
                frame,
                self.get_params(),
                path,
                export_format=fmt,
            )
        except MonitorExportError as exc:
            return False, tr("monitor_export_error").format(error=str(exc))
        if fmt is TraceExportFormat.WORKBENCH:
            return True, tr("monitor_export_csv_workbench_done").format(path=path)
        if fmt is TraceExportFormat.SOUNDBASE:
            return True, tr("monitor_export_csv_soundbase_done").format(path=path)
        return True, tr("monitor_export_csv_done").format(path=path)

    def export_widget_png(self, widget, path: str) -> tuple[bool, str]:
        from i18n.json_translation import tr

        if widget is None:
            return False, tr("monitor_export_no_widget")
        try:
            image = widget.grab()
            if image.isNull() or not image.save(path):
                return False, tr("monitor_export_error").format(error=path)
            return True, tr("monitor_export_png_done").format(path=path)
        except OSError as exc:
            return False, tr("monitor_export_error").format(error=str(exc))
