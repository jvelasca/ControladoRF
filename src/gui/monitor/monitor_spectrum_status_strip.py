"""Franja de estado bajo el espectro — frecuencias, SPAN, amplitud y entrada RF."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QToolButton, QWidget

from core.monitor.amplitude_units import amplitude_axis_label, dbm_to_display, format_amplitude_value
from core.monitor.monitor_bw_sweep_logic import effective_sweep_time_ms
from core.monitor.monitor_format import format_bw_hz, format_sweep_ms
from core.monitor.monitor_freq_span_logic import display_span_hz, patch_hackrf_amp
from core.monitor.spectrum_params import SpectrumParams
from core.rf.types import RfTelemetry
from gui.monitor.monitor_freq_menu import populate_freq_menu
from gui.monitor.monitor_spectrum_overlays import _SLIDER_QSS
from gui.monitor.monitor_status_dialogs import (
    edit_center_freq_dialog,
    edit_freq_start_dialog,
    edit_freq_step_dialog,
    edit_freq_stop_dialog,
    edit_lna_dialog,
    edit_ref_level_dialog,
    edit_ref_range_dialog,
    edit_span_dialog,
    edit_vga_dialog,
)
from gui.monitor.monitor_bw_menus import (
    populate_detector_menu,
    populate_rbw_menu,
    populate_sweep_menu,
    populate_trace_menu,
    populate_vbw_menu,
)
from gui.monitor.monitor_freq_mode_button import MonitorFreqModeButton
from gui.monitor.monitor_status_format import format_freq_compact, format_step_compact
from i18n.json_translation import tr


class _StatusSeparator(QFrame):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorStatusSeparator")
        self.setFrameShape(QFrame.Shape.VLine)
        self.setFixedWidth(1)


class _StatusField(QLabel):
    """Texto azul clicable — abre diálogo al pulsar."""

    clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorSpectrumStatusText")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        font = QFont("Consolas", 8)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class _ReadoutModeButton(MonitorFreqModeButton):
    """Botón FC/F en la franja de estado."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorStatusReadoutModeBtn")
        self.setFixedSize(20, 18)


class MonitorSpectrumStatusStrip(QFrame):
    """Línea de estado: Frecuencias | SPAN | Ref/Rng | LNA · P · VGA."""

    params_changed = pyqtSignal(object)

    _FREQ_VISIBILITY = (
        ("status_show_start", "monitor_status_start"),
        ("status_show_center", "monitor_status_center"),
        ("status_show_stop", "monitor_status_stop"),
        ("status_show_step", "monitor_status_step"),
        ("status_show_readout", "monitor_status_readout"),
    )
    _SPAN_VISIBILITY = (("status_show_span", "monitor_status_span"),)
    _BW_VISIBILITY = (
        ("status_show_rbw", "monitor_status_rbw"),
        ("status_show_vbw", "monitor_status_vbw"),
        ("status_show_sweep", "monitor_status_sweep"),
    )
    _TRACE_VISIBILITY = (
        ("status_show_trace", "monitor_status_trace"),
        ("status_show_detector", "monitor_status_detector"),
    )
    _AMP_VISIBILITY = (
        ("status_show_ref", "monitor_status_ref"),
        ("status_show_ref_range", "monitor_status_range"),
    )
    _RF_VISIBILITY = (
        ("status_show_lna", "monitor_status_lna"),
        ("status_show_preamp", "monitor_status_preamp"),
        ("status_show_vga", "monitor_status_vga"),
    )
    _MOTOR_VISIBILITY = (
        ("status_show_capture", "monitor_status_capture"),
        ("status_show_fps", "monitor_status_fps"),
    )

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorSpectrumStatusStrip")
        self.setStyleSheet(_SLIDER_QSS)
        self._params = SpectrumParams()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(6)

        self._start_field = _StatusField(self)
        self._center_field = _StatusField(self)
        self._stop_field = _StatusField(self)
        self._step_field = _StatusField(self)
        self._readout_mode_btn = _ReadoutModeButton(self)
        self._span_field = _StatusField(self)
        self._fi_filter_field = _StatusField(self)
        self._rbw_field = _StatusField(self)
        self._vbw_field = _StatusField(self)
        self._sweep_field = _StatusField(self)
        self._trace_field = _StatusField(self)
        self._detector_field = _StatusField(self)
        self._ref_field = _StatusField(self)
        self._range_field = _StatusField(self)
        self._lna_field = _StatusField(self)
        self._preamp_field = _StatusField(self)
        self._vga_field = _StatusField(self)
        self._capture_field = _StatusField(self)
        self._fps_field = _StatusField(self)
        self._runtime_telemetry: RfTelemetry | None = None

        self._start_field.clicked.connect(self._edit_start)
        self._center_field.clicked.connect(self._edit_center)
        self._stop_field.clicked.connect(self._edit_stop)
        self._step_field.clicked.connect(self._edit_step)
        self._readout_mode_btn.mode_changed.connect(self._on_readout_mode_changed)
        self._span_field.clicked.connect(self._edit_span)
        self._fi_filter_field.clicked.connect(self._show_fi_filter_menu)
        self._rbw_field.clicked.connect(self._show_rbw_menu)
        self._vbw_field.clicked.connect(self._show_vbw_menu)
        self._sweep_field.clicked.connect(self._show_sweep_menu)
        self._trace_field.clicked.connect(self._show_trace_menu)
        self._detector_field.clicked.connect(self._show_detector_menu)
        self._ref_field.clicked.connect(self._edit_ref)
        self._range_field.clicked.connect(self._edit_range)
        self._lna_field.clicked.connect(self._edit_lna)
        self._preamp_field.clicked.connect(self._toggle_preamp)
        self._vga_field.clicked.connect(self._edit_vga)

        self._sep_span = _StatusSeparator(self)
        self._sep_fi = _StatusSeparator(self)
        self._sep_bw = _StatusSeparator(self)
        self._sep_trace = _StatusSeparator(self)
        self._sep_amp = _StatusSeparator(self)
        self._sep_rf = _StatusSeparator(self)
        self._sep_motor = _StatusSeparator(self)

        self._fields_row = QHBoxLayout()
        self._fields_row.setContentsMargins(0, 0, 0, 0)
        self._fields_row.setSpacing(8)
        for widget in (
            self._start_field,
            self._center_field,
            self._stop_field,
            self._step_field,
            self._readout_mode_btn,
            self._sep_span,
            self._span_field,
            self._sep_fi,
            self._fi_filter_field,
            self._sep_bw,
            self._rbw_field,
            self._vbw_field,
            self._sweep_field,
            self._sep_trace,
            self._trace_field,
            self._detector_field,
            self._sep_amp,
            self._ref_field,
            self._range_field,
            self._sep_rf,
            self._lna_field,
            self._preamp_field,
            self._vga_field,
            self._sep_motor,
            self._capture_field,
            self._fps_field,
        ):
            self._fields_row.addWidget(widget)
        self._fields_row.addStretch(1)

        self._menu_btn = QToolButton(self)
        self._menu_btn.setObjectName("MonitorOverlayMenuBtn")
        self._menu_btn.setText("…")
        self._menu_btn.setFixedSize(20, 16)
        self._menu_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._menu_btn.clicked.connect(self._show_menu)

        layout.addLayout(self._fields_row, stretch=1)
        layout.addWidget(self._menu_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self._apply_tooltips()

    def set_runtime_telemetry(self, telemetry: RfTelemetry) -> None:
        self._runtime_telemetry = telemetry
        self._refresh_runtime_fields()

    def _refresh_runtime_fields(self) -> None:
        params = self._params
        tel = self._runtime_telemetry
        if tel is None or tel.acquisition_mode == "unknown":
            self._capture_field.hide()
            self._fps_field.hide()
            self._sep_motor.setVisible(False)
            return
        mode_key = "monitor_status_cap_iq" if tel.acquisition_mode == "iq_stream" else "monitor_status_cap_sweep"
        cap_parts = [tr(mode_key)]
        if not params.status_show_rbw:
            if tel.frame_bins > 0:
                cap_parts.append(f"{tel.frame_bins} pts")
            if tel.rbw_effective_hz > 0:
                cap_parts.append(format_bw_hz(tel.rbw_effective_hz))
        if tel.last_capture_ms > 0 and tel.acquisition_mode != "iq_stream":
            cap_parts.append(f"{tel.last_capture_ms:.0f} ms")
        self._set_field_styled(
            self._capture_field,
            params.status_show_capture,
            tr("monitor_status_line_capture").format(value=" · ".join(cap_parts)),
            tone="normal",
        )
        fps_text = f"{tel.fps:.1f}" if tel.fps > 0.1 else "—"
        self._set_field(
            self._fps_field,
            params.status_show_fps,
            tr("monitor_status_line_fps").format(fps=fps_text),
        )
        motor_visible = params.status_show_capture or params.status_show_fps
        self._sep_motor.setVisible(
            motor_visible
            and (
                params.status_show_lna
                or params.status_show_preamp
                or params.status_show_vga
                or params.status_show_att
                or params.status_show_ref
                or params.status_show_ref_range
            )
        )

    def set_params(self, params: SpectrumParams) -> None:
        self._params = params.copy()
        unit = params.amplitude_unit
        auto_scale = params.ref_scale_auto

        self._set_field(
            self._start_field,
            params.status_show_start,
            tr("monitor_status_line_start").format(freq=format_freq_compact(params.freq_start_hz())),
        )
        self._set_field(
            self._center_field,
            params.status_show_center,
            tr("monitor_status_line_center").format(freq=format_freq_compact(params.center_freq_hz)),
        )
        self._set_field(
            self._stop_field,
            params.status_show_stop,
            tr("monitor_status_line_stop").format(freq=format_freq_compact(params.freq_stop_hz())),
        )
        self._set_field(
            self._step_field,
            params.status_show_step,
            tr("monitor_status_line_step").format(step=format_step_compact(params.freq_step_hz)),
        )

        if params.status_show_readout:
            self._readout_mode_btn.set_mode(params.freq_readout)
            self._readout_mode_btn.show()
        else:
            self._readout_mode_btn.hide()

        self._set_field(
            self._span_field,
            params.status_show_span,
            (
                tr("monitor_status_line_bandwidth").format(
                    bw=format_freq_compact(display_span_hz(params)),
                )
                if params.capture_mode == "iq"
                else tr("monitor_status_line_span").format(
                    span=format_freq_compact(display_span_hz(params))
                )
            ),
        )
        fi_visible = params.capture_mode == "iq" and params.status_show_span
        if fi_visible:
            from core.monitor.hackrf_baseband import format_baseband_filter_mhz

            auto_suffix = (
                f" {tr('monitor_lcd_auto_suffix')}" if params.baseband_filter_auto else ""
            )
            fi_text = tr("monitor_status_line_fi_filter").format(
                bw=f"{format_baseband_filter_mhz(params.baseband_filter_bw_hz)} MHz{auto_suffix}",
            )
            tone = "auto" if params.baseband_filter_auto else "manual"
            self._set_field_styled(self._fi_filter_field, True, fi_text, tone=tone)
        else:
            self._fi_filter_field.hide()

        from core.monitor.monitor_bw_profile import (
            format_resolution_status,
            format_smoothing_status,
            uses_iq_resolution,
        )

        rbw_text = format_resolution_status(params)
        vbw_text = format_smoothing_status(params)
        if params.capture_mode == "iq":
            swt_text = tr("monitor_lcd_swt_na")
            sweep_tone = "normal"
        else:
            swt_val = format_sweep_ms(effective_sweep_time_ms(params))
            swt_text = swt_val
            trigger_mode = params.sweep_trigger_mode
            if trigger_mode == "manual":
                swt_text += f" · {tr('monitor_sweep_trigger_manual')}"
            elif trigger_mode == "periodic":
                swt_text += f" · {tr('monitor_sweep_trigger_periodic')} {params.sweep_trigger_period_sec:g}s"
            sweep_tone = (
                "special"
                if trigger_mode != "continuous"
                else ("auto" if params.sweep_auto else "manual")
            )
        rbw_auto = params.fft_auto if uses_iq_resolution(params) else params.rbw_auto
        self._set_field_styled(
            self._rbw_field,
            params.status_show_rbw,
            tr("monitor_status_line_resolution").format(value=rbw_text),
            tone="auto" if rbw_auto else "manual",
        )
        self._set_field_styled(
            self._vbw_field,
            params.status_show_vbw,
            tr("monitor_status_line_smooth").format(value=vbw_text),
            tone="auto" if params.trace_smooth_auto else "manual",
        )
        self._set_field_styled(
            self._sweep_field,
            params.status_show_sweep,
            tr("monitor_status_line_sweep").format(sweep=swt_text),
            tone=sweep_tone,
        )

        trace_tone = "special" if params.trace_mode != "clear_write" else "normal"
        self._set_field_styled(
            self._trace_field,
            params.status_show_trace,
            tr("monitor_status_line_trace").format(trace=tr(f"monitor_trace_{params.trace_mode}")),
            tone=trace_tone,
        )
        det_tone = "manual" if params.detector != "rms" else "normal"
        self._set_field_styled(
            self._detector_field,
            params.status_show_detector,
            tr("monitor_status_line_detector").format(det=tr(f"monitor_detector_{params.detector}")),
            tone=det_tone,
        )

        if params.status_show_ref:
            if auto_scale:
                ref_text = tr("monitor_ampt_auto")
            else:
                display = dbm_to_display(
                    params.ref_level_dbm, unit, ref_offset_db=params.ref_offset_db
                )
                ref_text = f"{format_amplitude_value(display, unit)} {amplitude_axis_label(unit)}"
            self._set_field_styled(
                self._ref_field,
                True,
                tr("monitor_status_line_ref").format(ref=ref_text),
                tone="auto" if auto_scale else "manual",
            )
        else:
            self._ref_field.hide()

        if params.status_show_ref_range:
            if auto_scale:
                range_text = tr("monitor_ampt_auto")
            else:
                db_div = params.ref_range_db / max(params.vertical_divisions, 1)
                range_text = tr("monitor_status_range_value").format(
                    range_db=f"{params.ref_range_db:.0f}",
                    db_div=f"{db_div:.0f}",
                )
            self._set_field_styled(
                self._range_field,
                True,
                tr("monitor_status_line_res").format(res=range_text),
                tone="auto" if auto_scale else "manual",
            )
        else:
            self._range_field.hide()

        self._set_field(
            self._lna_field,
            params.status_show_lna,
            tr("monitor_status_line_lna").format(gain=f"{int(params.lna_gain_db)}"),
        )
        self._set_field(
            self._preamp_field,
            params.status_show_preamp,
            tr("monitor_status_line_preamp").format(
                state=tr("monitor_status_preamp_on" if params.rf_amp_enable else "monitor_status_preamp_off")
            ),
        )
        self._set_field(
            self._vga_field,
            params.status_show_vga or params.status_show_att,
            tr("monitor_status_line_vga").format(gain=f"{int(params.vga_gain_db)}"),
        )

        freq_visible = any(getattr(params, key) for key, _ in self._FREQ_VISIBILITY)
        amp_visible = any(getattr(params, key) for key, _ in self._AMP_VISIBILITY)
        rf_visible = any(
            getattr(params, key)
            for key, _ in self._RF_VISIBILITY
        ) or params.status_show_att

        bw_visible = any(getattr(params, key) for key, _ in self._BW_VISIBILITY)
        trace_visible = any(getattr(params, key) for key, _ in self._TRACE_VISIBILITY)

        self._sep_span.setVisible(params.status_show_span and freq_visible)
        self._sep_fi.setVisible(
            params.capture_mode == "iq" and params.status_show_span and freq_visible
        )
        self._sep_bw.setVisible(bw_visible and (freq_visible or params.status_show_span))
        self._sep_trace.setVisible(trace_visible and (bw_visible or freq_visible or params.status_show_span))
        self._sep_amp.setVisible(amp_visible and (trace_visible or bw_visible or params.status_show_span or freq_visible))
        self._sep_rf.setVisible(
            rf_visible and (amp_visible or trace_visible or bw_visible or params.status_show_span or freq_visible)
        )
        self._refresh_runtime_fields()

    @staticmethod
    def _set_field(field: _StatusField, visible: bool, text: str) -> None:
        if visible:
            field.setText(text)
            field.show()
        else:
            field.hide()

    @staticmethod
    def _set_field_styled(field: _StatusField, visible: bool, text: str, *, tone: str = "normal") -> None:
        field.setProperty("statusTone", tone)
        field.style().unpolish(field)
        field.style().polish(field)
        MonitorSpectrumStatusStrip._set_field(field, visible, text)

    def recargar_textos(self) -> None:
        self._apply_tooltips()
        self.set_params(self._params)

    def _apply_tooltips(self) -> None:
        self._menu_btn.setToolTip(tr("monitor_tip_status_menu"))
        self._start_field.setToolTip(tr("monitor_tip_status_edit_start"))
        self._center_field.setToolTip(tr("monitor_tip_status_edit_center"))
        self._stop_field.setToolTip(tr("monitor_tip_status_edit_stop"))
        self._step_field.setToolTip(tr("monitor_tip_status_edit_step"))
        self._readout_mode_btn.setToolTip(tr("monitor_tip_status_readout"))
        self._span_field.setToolTip(
            tr("monitor_tip_status_edit_bandwidth")
            if self._params.capture_mode == "iq"
            else tr("monitor_tip_status_edit_span")
        )
        self._fi_filter_field.setToolTip(tr("monitor_tip_status_edit_fi_filter"))
        self._rbw_field.setToolTip(tr("monitor_tip_status_edit_rbw"))
        self._vbw_field.setToolTip(tr("monitor_tip_status_edit_vbw"))
        self._sweep_field.setToolTip(tr("monitor_tip_status_edit_sweep"))
        self._trace_field.setToolTip(tr("monitor_tip_status_edit_trace"))
        self._detector_field.setToolTip(tr("monitor_tip_status_edit_detector"))
        self._ref_field.setToolTip(tr("monitor_tip_status_edit_ref"))
        self._range_field.setToolTip(tr("monitor_tip_status_edit_res"))
        self._lna_field.setToolTip(tr("monitor_tip_status_edit_lna"))
        self._preamp_field.setToolTip(tr("monitor_tip_status_edit_preamp"))
        self._vga_field.setToolTip(tr("monitor_tip_status_edit_vga"))

    def _apply_dialog_result(self, updated: Optional[SpectrumParams]) -> None:
        if updated is None:
            return
        self._params = updated
        self.set_params(updated)
        self.params_changed.emit(updated)

    def _edit_start(self) -> None:
        self._apply_dialog_result(edit_freq_start_dialog(self._params, parent=self.window()))

    def _edit_center(self) -> None:
        self._apply_dialog_result(edit_center_freq_dialog(self._params, parent=self.window()))

    def _edit_stop(self) -> None:
        self._apply_dialog_result(edit_freq_stop_dialog(self._params, parent=self.window()))

    def _edit_step(self) -> None:
        self._apply_dialog_result(edit_freq_step_dialog(self._params, parent=self.window()))

    def _edit_span(self) -> None:
        self._apply_dialog_result(edit_span_dialog(self._params, parent=self.window()))

    def _show_fi_filter_menu(self) -> None:
        from gui.monitor.monitor_bw_menus import populate_bb_filter_menu

        menu = QMenu(self)
        populate_bb_filter_menu(menu, lambda: self._params, self._patch, parent=self.window())
        menu.exec(self._fi_filter_field.mapToGlobal(self._fi_filter_field.rect().bottomLeft()))

    def _show_rbw_menu(self) -> None:
        menu = QMenu(self)
        populate_rbw_menu(menu, lambda: self._params, self._patch, parent=self.window())
        menu.exec(self._rbw_field.mapToGlobal(self._rbw_field.rect().bottomLeft()))

    def _show_vbw_menu(self) -> None:
        menu = QMenu(self)
        populate_vbw_menu(menu, lambda: self._params, self._patch)
        menu.exec(self._vbw_field.mapToGlobal(self._vbw_field.rect().bottomLeft()))

    def _show_sweep_menu(self) -> None:
        menu = QMenu(self)
        populate_sweep_menu(menu, lambda: self._params, self._patch)
        menu.exec(self._sweep_field.mapToGlobal(self._sweep_field.rect().bottomLeft()))

    def _show_trace_menu(self) -> None:
        menu = QMenu(self)
        populate_trace_menu(menu, lambda: self._params, self._patch)
        menu.exec(self._trace_field.mapToGlobal(self._trace_field.rect().bottomLeft()))

    def _show_detector_menu(self) -> None:
        menu = QMenu(self)
        populate_detector_menu(menu, lambda: self._params, self._patch)
        menu.exec(self._detector_field.mapToGlobal(self._detector_field.rect().bottomLeft()))

    def _edit_ref(self) -> None:
        self._apply_dialog_result(edit_ref_level_dialog(self._params, parent=self.window()))

    def _edit_range(self) -> None:
        self._apply_dialog_result(edit_ref_range_dialog(self._params, parent=self.window()))

    def _edit_lna(self) -> None:
        self._apply_dialog_result(edit_lna_dialog(self._params, parent=self.window()))

    def _toggle_preamp(self) -> None:
        updated = patch_hackrf_amp(self._params, enabled=not self._params.rf_amp_enable)
        self._patch(updated)

    def _edit_vga(self) -> None:
        self._apply_dialog_result(edit_vga_dialog(self._params, parent=self.window()))

    def _on_readout_mode_changed(self, mode: str) -> None:
        from core.monitor.monitor_freq_span_logic import patch_freq_readout

        self._patch(patch_freq_readout(self._params, mode))

    def _show_freq_menu(self) -> None:
        menu = QMenu(self)
        populate_freq_menu(menu, self._params, patch=self._patch, parent=self.window())
        menu.exec(
            self._readout_mode_btn.mapToGlobal(self._readout_mode_btn.rect().bottomLeft())
        )

    def _patch(self, updated: SpectrumParams) -> None:
        self._params = updated
        self.set_params(updated)
        self.params_changed.emit(updated)

    def _show_menu(self) -> None:
        menu = QMenu(self)
        freq_menu = menu.addMenu(tr("monitor_status_group_freq"))
        for attr, label_key in self._FREQ_VISIBILITY:
            self._add_visibility_action(freq_menu, attr, label_key)
        span_menu = menu.addMenu(tr("monitor_status_group_span"))
        for attr, label_key in self._SPAN_VISIBILITY:
            self._add_visibility_action(span_menu, attr, label_key)
        bw_menu = menu.addMenu(tr("monitor_status_group_bw"))
        for attr, label_key in self._BW_VISIBILITY:
            self._add_visibility_action(bw_menu, attr, label_key)
        trace_menu = menu.addMenu(tr("monitor_status_group_trace"))
        for attr, label_key in self._TRACE_VISIBILITY:
            self._add_visibility_action(trace_menu, attr, label_key)
        amp_menu = menu.addMenu(tr("monitor_status_group_amp"))
        for attr, label_key in self._AMP_VISIBILITY:
            self._add_visibility_action(amp_menu, attr, label_key)
        rf_menu = menu.addMenu(tr("monitor_status_group_rf"))
        for attr, label_key in self._RF_VISIBILITY:
            self._add_visibility_action(rf_menu, attr, label_key)
        motor_menu = menu.addMenu(tr("monitor_status_group_motor"))
        for attr, label_key in self._MOTOR_VISIBILITY:
            self._add_visibility_action(motor_menu, attr, label_key)
        menu.exec(self._menu_btn.mapToGlobal(self._menu_btn.rect().bottomLeft()))

    def _add_visibility_action(self, menu: QMenu, attr: str, label_key: str) -> None:
        act = menu.addAction(tr(label_key))
        act.setCheckable(True)
        act.setChecked(bool(getattr(self._params, attr)))

        def _set_visible(checked: bool, key=attr) -> None:
            updated = self._params.copy()
            setattr(updated, key, bool(checked))
            self._patch(updated)

        act.triggered.connect(_set_visible)
