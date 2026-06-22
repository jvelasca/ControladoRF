"""Panel RADIO — recepción FM / AM / DIG (modo SDR)."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.monitor.analog_demod_profiles import (
    DEEMPHASIS_CHOICES,
    demod_ui_limits,
    mode_shows_deemphasis,
    mode_shows_dsb_controls,
    mode_shows_wfm_if_controls,
    normalize_analog_demod_mode,
    snap_vfo_freq_hz,
)
from core.monitor.digital_signal_profiles import (
    DIGITAL_PROFILES,
    MOD_ORDER_CHOICES,
    PROFILE_CHOICES,
    apply_digital_profile_defaults,
)
from core.monitor.receive_mode_logic import (
    RECEIVE_MODES,
    apply_receive_mode,
    is_analog_receive_mode,
    is_digital_receive_mode,
    refresh_digital_profile_for_vfo,
)
from core.monitor.monitor_mode_guard import demod_requires_sdr_mode
from core.monitor.monitor_operating_mode import MonitorOperatingMode
from core.monitor.spectrum_params import SpectrumParams
from core.rf.source_ids import is_analyzer_only_source
from gui.monitor.monitor_filled_value_slider import MonitorFilledValueSlider
from gui.monitor.monitor_digital_panel import MonitorDigitalAnalysisPanel
from gui.monitor.monitor_radio_display import MonitorDemodDisplay
from gui.monitor.monitor_radio_toolbar import MonitorRadioToolbar
from gui.monitor.monitor_radio_icons import make_audio_mute_icon, make_squelch_icon
from gui.monitor.monitor_rf_quality_panel import MonitorRfQualityPanel
from i18n.json_translation import tr


class MonitorRadioPanel(QWidget):
    """Controles de recepción; habilitados solo en modo SDR."""

    params_changed = pyqtSignal(object)
    soft_param_patch = pyqtSignal(object)
    audio_volume_changed = pyqtSignal(float)
    auto_tune_requested = pyqtSignal()
    welle_cli_requested = pyqtSignal()
    mode_restriction = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._mode = MonitorOperatingMode.SPECTRUM
        self._params = SpectrumParams()
        self._toolbar: Optional[MonitorRadioToolbar] = None
        self._form_host: Optional[QWidget] = None
        self._digital_form_host: Optional[QWidget] = None
        self._mode_banner: Optional[QLabel] = None
        self._receive_combo: Optional[QComboBox] = None
        self._bw_spin: Optional[QSpinBox] = None
        self._snap_spin: Optional[QSpinBox] = None
        self._deemph_combo: Optional[QComboBox] = None
        self._noise_blank_spin: Optional[QDoubleSpinBox] = None
        self._agc_attack_spin: Optional[QSpinBox] = None
        self._agc_decay_spin: Optional[QSpinBox] = None
        self._mode_form: Optional[QFormLayout] = None
        self._vfo_spin: Optional[QDoubleSpinBox] = None
        self._squelch_slider: Optional[MonitorFilledValueSlider] = None
        self._volume_slider: Optional[MonitorFilledValueSlider] = None
        self._mute_btn: Optional[QToolButton] = None
        self._digital_profile_combo: Optional[QComboBox] = None
        self._digital_mod_combo: Optional[QComboBox] = None
        self._digital_symbol_spin: Optional[QDoubleSpinBox] = None
        self._demod_display: Optional[MonitorDemodDisplay] = None
        self._digital_panel: Optional[MonitorDigitalAnalysisPanel] = None
        self._rf_quality: Optional[MonitorRfQualityPanel] = None
        self._audio_status: Optional[QLabel] = None
        self._analog_widgets: tuple[QWidget, ...] = ()
        self._digital_widgets: tuple[QWidget, ...] = ()
        self._demod_click_targets: tuple[QWidget, ...] = ()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._toolbar = MonitorRadioToolbar(self)
        self._toolbar.auto_tune_requested.connect(self.auto_tune_requested.emit)
        self._toolbar.wfm_stereo_toggled.connect(self._on_wfm_stereo_toggled)
        self._toolbar.wfm_rds_toggled.connect(self._on_wfm_rds_toggled)
        self._toolbar.show_demod_bw_toggled.connect(self._on_show_demod_bw_toggled)
        self._toolbar.wfm_lowpass_toggled.connect(self._on_wfm_lowpass_toggled)
        self._toolbar.iq_correction_toggled.connect(self._on_iq_correction_toggled)
        self._toolbar.iq_invert_toggled.connect(self._on_iq_invert_toggled)
        layout.addWidget(self._toolbar)

        self._mode_banner = QLabel()
        self._mode_banner.setObjectName("MonitorRadioModeBanner")
        self._mode_banner.setWordWrap(True)
        self._mode_banner.setVisible(False)
        layout.addWidget(self._mode_banner)

        self._form_host = QWidget(self)
        form = QFormLayout(self._form_host)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setContentsMargins(0, 0, 0, 0)

        self._receive_combo = QComboBox()
        for mode in RECEIVE_MODES:
            self._receive_combo.addItem(tr(f"monitor_demod_{mode}"), mode)
        self._receive_combo.setToolTip(tr("monitor_radio_receive_tip"))
        self._receive_combo.currentIndexChanged.connect(self._emit_receive_patch)

        self._bw_spin = QSpinBox()
        self._bw_spin.setRange(100, 500_000)
        self._bw_spin.setSingleStep(100)
        self._bw_spin.setSuffix(" Hz")
        self._bw_spin.setToolTip(tr("monitor_radio_bandwidth_tip"))
        self._bw_spin.valueChanged.connect(self._emit_receive_patch)

        self._snap_spin = QSpinBox()
        self._snap_spin.setRange(1, 1_000_000)
        self._snap_spin.setSingleStep(100)
        self._snap_spin.setSuffix(" Hz")
        self._snap_spin.setToolTip(tr("monitor_radio_snap_interval_tip"))
        self._snap_spin.valueChanged.connect(self._emit_receive_patch)

        self._deemph_combo = QComboBox()
        for choice in DEEMPHASIS_CHOICES:
            self._deemph_combo.addItem(tr(f"monitor_demod_deemph_{choice}"), choice)
        self._deemph_combo.setToolTip(tr("monitor_radio_deemphasis_tip"))
        self._deemph_combo.currentIndexChanged.connect(self._emit_receive_patch)

        self._noise_blank_spin = QDoubleSpinBox()
        self._noise_blank_spin.setRange(0.0, 30.0)
        self._noise_blank_spin.setDecimals(1)
        self._noise_blank_spin.setSuffix(" dB")
        self._noise_blank_spin.setToolTip(tr("monitor_radio_noise_blanker_tip"))
        self._noise_blank_spin.valueChanged.connect(self._emit_receive_patch)

        self._agc_attack_spin = QSpinBox()
        self._agc_attack_spin.setRange(1, 500)
        self._agc_attack_spin.valueChanged.connect(self._emit_receive_patch)

        self._agc_decay_spin = QSpinBox()
        self._agc_decay_spin.setRange(1, 500)
        self._agc_decay_spin.valueChanged.connect(self._emit_receive_patch)

        self._vfo_spin = QDoubleSpinBox()
        self._vfo_spin.setRange(0.0, 6_000_000_000.0)
        self._vfo_spin.setDecimals(0)
        self._vfo_spin.setSuffix(" Hz")
        self._vfo_spin.setSingleStep(25_000.0)
        self._vfo_spin.setToolTip(tr("monitor_radio_vfo_tip"))
        self._vfo_spin.valueChanged.connect(self._emit_receive_patch)

        self._squelch_slider = MonitorFilledValueSlider(
            minimum=-120.0,
            maximum=0.0,
            step=0.1,
            suffix=" dBFS",
            decimals=1,
            slider_kind="SquelchSlider",
        )
        self._squelch_slider.setToolTip(tr("monitor_radio_squelch_tip"))
        self._squelch_slider.valueChanged.connect(self._on_squelch_slider_changed)

        self._squelch_btn = QToolButton()
        self._squelch_btn.setObjectName("MonitorRadioSquelchBtn")
        self._squelch_btn.setCheckable(True)
        self._squelch_btn.setChecked(True)
        self._squelch_btn.setAutoRaise(True)
        self._squelch_btn.setFixedSize(28, 28)
        self._squelch_btn.setToolTip(tr("monitor_radio_squelch_enable_tip"))
        self._squelch_btn.toggled.connect(self._on_squelch_toggled)

        squelch_row = QHBoxLayout()
        squelch_row.setContentsMargins(0, 0, 0, 0)
        squelch_row.setSpacing(6)
        squelch_row.addWidget(self._squelch_btn)
        squelch_row.addWidget(self._squelch_slider, stretch=1)
        squelch_host = QWidget()
        squelch_host.setLayout(squelch_row)

        self._volume_slider = MonitorFilledValueSlider(
            minimum=0.0,
            maximum=100.0,
            step=1.0,
            suffix=" %",
            decimals=0,
            slider_kind="VolumeSlider",
        )
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        self._volume_slider.setMinimumWidth(0)

        self._mute_btn = QToolButton()
        self._mute_btn.setObjectName("MonitorRadioMuteBtn")
        self._mute_btn.setCheckable(True)
        self._mute_btn.setAutoRaise(True)
        self._mute_btn.setFixedSize(28, 28)
        self._mute_btn.setToolTip(tr("monitor_radio_mute_tip"))
        self._mute_btn.toggled.connect(self._on_mute_toggled)

        volume_row = QHBoxLayout()
        volume_row.setContentsMargins(0, 0, 0, 0)
        volume_row.setSpacing(6)
        volume_row.addWidget(self._mute_btn)
        volume_row.addWidget(self._volume_slider, stretch=1)
        volume_host = QWidget()
        volume_host.setLayout(volume_row)

        form.addRow(tr("monitor_radio_receive"), self._receive_combo)
        form.addRow(tr("monitor_radio_vfo"), self._vfo_spin)
        form.addRow(tr("monitor_radio_bandwidth"), self._bw_spin)
        form.addRow(tr("monitor_radio_snap_interval"), self._snap_spin)
        form.addRow(tr("monitor_radio_deemphasis"), self._deemph_combo)
        form.addRow(tr("monitor_radio_noise_blanker"), self._noise_blank_spin)
        form.addRow(tr("monitor_radio_agc_attack"), self._agc_attack_spin)
        form.addRow(tr("monitor_radio_agc_decay"), self._agc_decay_spin)
        form.addRow(tr("monitor_radio_squelch"), squelch_host)
        form.addRow(tr("monitor_radio_volume"), volume_host)
        self._mode_form = form
        layout.addWidget(self._form_host)

        self._demod_display = MonitorDemodDisplay(self)
        layout.addWidget(self._demod_display)

        self._digital_form_host = QWidget(self)
        digital_form = QFormLayout(self._digital_form_host)
        digital_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        digital_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self._digital_profile_combo = QComboBox()
        for profile_id in PROFILE_CHOICES:
            self._digital_profile_combo.addItem(
                tr(DIGITAL_PROFILES[profile_id].label_key),
                profile_id,
            )
        self._digital_profile_combo.currentIndexChanged.connect(self._emit_digital_profile_patch)

        self._digital_mod_combo = QComboBox()
        for order, label_key in MOD_ORDER_CHOICES:
            self._digital_mod_combo.addItem(tr(label_key), order)
        self._digital_mod_combo.currentIndexChanged.connect(self._emit_receive_patch)

        self._digital_symbol_spin = QDoubleSpinBox()
        self._digital_symbol_spin.setRange(1_000.0, 20_000_000.0)
        self._digital_symbol_spin.setDecimals(0)
        self._digital_symbol_spin.setSuffix(" sym/s")
        self._digital_symbol_spin.setSingleStep(25_000.0)
        self._digital_symbol_spin.valueChanged.connect(self._emit_receive_patch)

        digital_form.addRow(tr("monitor_digital_profile"), self._digital_profile_combo)
        digital_form.addRow(tr("monitor_digital_mod_order"), self._digital_mod_combo)
        digital_form.addRow(tr("monitor_digital_symbol_rate"), self._digital_symbol_spin)
        layout.addWidget(self._digital_form_host)

        self._digital_panel = MonitorDigitalAnalysisPanel(self)
        self._digital_panel.welle_cli_requested.connect(self.welle_cli_requested.emit)
        layout.addWidget(self._digital_panel)

        self._analog_widgets = (
            self._bw_spin,
            self._snap_spin,
            self._deemph_combo,
            self._noise_blank_spin,
            self._agc_attack_spin,
            self._agc_decay_spin,
            self._squelch_btn,
            self._squelch_slider,
            self._volume_slider,
            self._mute_btn,
            self._demod_display,
        )
        self._digital_widgets = (
            self._digital_profile_combo,
            self._digital_mod_combo,
            self._digital_symbol_spin,
            self._digital_panel,
        )
        self._demod_click_targets = (
            self._receive_combo,
            self._vfo_spin,
            self._bw_spin,
            self._snap_spin,
            self._deemph_combo,
            self._noise_blank_spin,
            self._agc_attack_spin,
            self._agc_decay_spin,
            self._squelch_btn,
            self._squelch_slider,
            self._volume_slider,
            self._mute_btn,
            self._demod_display,
            self._digital_profile_combo,
            self._digital_mod_combo,
            self._digital_symbol_spin,
            self._digital_panel,
        )
        for widget in self._demod_click_targets:
            if widget is not None:
                widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._rf_quality = MonitorRfQualityPanel(self)
        self._rf_quality.bandwidth_changed.connect(self._on_rf_bandwidth_changed)
        layout.addWidget(self._rf_quality)

        layout.addStretch(1)

        self._audio_status = QLabel()
        self._audio_status.setWordWrap(True)
        self._audio_status.setMinimumHeight(self.fontMetrics().lineSpacing() * 2 + 4)
        layout.addWidget(self._audio_status)

        self._refresh_mode_ui()

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        return QSize(0, hint.height())

    def _emit_digital_profile_patch(self, *_args) -> None:
        if self._mode is not MonitorOperatingMode.SDR:
            self._notify_demod_blocked()
            return
        updated = self._params.copy()
        if self._digital_profile_combo is not None:
            profile = self._digital_profile_combo.currentData()
            if profile:
                updated = apply_digital_profile_defaults(updated, str(profile))
                updated.demod_mode = "dig"
                updated.digital_analysis_enabled = True
                updated.audio_enabled = False
        self._apply_common_fields(updated)
        self._params = updated
        self.params_changed.emit(updated)

    def _emit_soft_param_patch(self, **fields: object) -> None:
        """Parche mínimo de toggles WFM — solo los campos tocados (evita pisar estado vivo)."""
        if self._mode is not MonitorOperatingMode.SDR:
            self._notify_demod_blocked()
            return
        updated = self._params.copy()
        for key, value in fields.items():
            setattr(updated, key, value)
        self._params = updated
        self.soft_param_patch.emit(dict(fields))

    def _emit_receive_patch(self, *_args) -> None:
        if self._mode is not MonitorOperatingMode.SDR:
            self._notify_demod_blocked()
            return
        updated = self._params.copy()
        mode_changed = False
        if self._receive_combo is not None:
            mode = self._receive_combo.currentData()
            if mode:
                new_mode = str(mode)
                prev = (self._params.demod_mode or "wfm").lower()
                if prev == "fm":
                    prev = "wfm"
                mode_changed = new_mode != prev
                if mode_changed:
                    updated = apply_receive_mode(updated, new_mode)
        if mode_changed:
            self._sync_analog_fields_from_params(updated)
        self._apply_common_fields(updated)
        if is_digital_receive_mode(updated):
            updated = refresh_digital_profile_for_vfo(updated)
        self._params = updated
        self._sync_digital_widgets_from_params()
        self._sync_rf_bandwidth_strip()
        self.params_changed.emit(updated)
        self._refresh_mode_ui()

    def _apply_toolbar_toggle_fields(self, updated: SpectrumParams) -> None:
        if self._toolbar is not None:
            for attr, field in (
                ("_stereo_btn", "demod_wfm_stereo"),
                ("_rds_btn", "demod_wfm_rds"),
                ("_bw_btn", "show_demod_bandwidth"),
                ("_lowpass_btn", "demod_wfm_lowpass"),
                ("_iq_corr_btn", "demod_iq_correction"),
                ("_iq_inv_btn", "demod_iq_invert"),
            ):
                btn = getattr(self._toolbar, attr, None)
                if btn is not None:
                    setattr(updated, field, bool(btn.isChecked()))
        if self._mute_btn is not None:
            updated.audio_muted = bool(self._mute_btn.isChecked())

    def _apply_common_fields(self, updated: SpectrumParams) -> None:
        if self._vfo_spin is not None:
            vfo = float(self._vfo_spin.value())
            if is_analog_receive_mode(updated):
                vfo = snap_vfo_freq_hz(vfo, updated.demod_snap_interval)
            updated.vfo_freq_hz = vfo
            if updated.freq_readout == "f":
                updated.selected_freq_hz = vfo
        if is_analog_receive_mode(updated):
            if self._bw_spin is not None:
                updated.demod_bandwidth_hz = float(self._bw_spin.value())
            if self._snap_spin is not None:
                updated.demod_snap_interval = float(self._snap_spin.value())
            if self._deemph_combo is not None and self._deemph_combo.isEnabled():
                choice = self._deemph_combo.currentData()
                if choice:
                    updated.demod_deemphasis = str(choice)
            if self._noise_blank_spin is not None and self._noise_blank_spin.isEnabled():
                updated.demod_noise_blanker_db = float(self._noise_blank_spin.value())
            if self._agc_attack_spin is not None and self._agc_attack_spin.isEnabled():
                updated.demod_agc_attack = float(self._agc_attack_spin.value())
            if self._agc_decay_spin is not None and self._agc_decay_spin.isEnabled():
                updated.demod_agc_decay = float(self._agc_decay_spin.value())
            if self._squelch_slider is not None:
                updated.squelch_db = float(self._squelch_slider.value())
            if self._squelch_btn is not None:
                updated.squelch_enabled = bool(self._squelch_btn.isChecked())
        if is_digital_receive_mode(updated):
            if self._digital_mod_combo is not None and self._digital_mod_combo.isEnabled():
                order = self._digital_mod_combo.currentData()
                if order is not None:
                    updated.digital_mod_order = int(order)
            if self._digital_symbol_spin is not None and self._digital_symbol_spin.isEnabled():
                updated.digital_symbol_rate_hz = float(self._digital_symbol_spin.value())
        self._apply_toolbar_toggle_fields(updated)

    def _on_wfm_stereo_toggled(self, checked: bool) -> None:
        self._emit_soft_param_patch(demod_wfm_stereo=bool(checked))

    def _on_wfm_rds_toggled(self, checked: bool) -> None:
        self._emit_soft_param_patch(demod_wfm_rds=bool(checked))

    def _on_show_demod_bw_toggled(self, checked: bool) -> None:
        self._emit_soft_param_patch(show_demod_bandwidth=bool(checked))

    def _on_wfm_lowpass_toggled(self, checked: bool) -> None:
        self._emit_soft_param_patch(demod_wfm_lowpass=bool(checked))

    def _on_iq_correction_toggled(self, checked: bool) -> None:
        self._emit_soft_param_patch(demod_iq_correction=bool(checked))

    def _on_iq_invert_toggled(self, checked: bool) -> None:
        self._emit_soft_param_patch(demod_iq_invert=bool(checked))

    def _on_rf_bandwidth_changed(self, bw_hz: float) -> None:
        if self._mode is not MonitorOperatingMode.SDR:
            return
        updated = self._params.copy()
        updated.demod_bandwidth_hz = float(bw_hz)
        if self._bw_spin is not None:
            self._bw_spin.blockSignals(True)
            self._bw_spin.setValue(int(round(bw_hz)))
            self._bw_spin.blockSignals(False)
        self._params = updated
        self.params_changed.emit(updated)

    def _sync_rf_bandwidth_strip(self) -> None:
        if self._rf_quality is None or not is_analog_receive_mode(self._params):
            return
        mode = normalize_analog_demod_mode(self._params.demod_mode)
        limits = demod_ui_limits(mode)
        self._rf_quality.configure_demod_bandwidth(
            demod_bw_hz=float(self._params.demod_bandwidth_hz),
            min_hz=float(limits.bw_min_hz),
            max_hz=float(limits.bw_max_hz),
            step_hz=float(limits.bw_step_hz),
        )

    def _on_squelch_slider_changed(self, _value: float) -> None:
        self._emit_receive_patch()

    def _on_squelch_toggled(self, enabled: bool) -> None:
        if self._mode is not MonitorOperatingMode.SDR:
            return
        updated = self._params.copy()
        updated.squelch_enabled = bool(enabled)
        self._params = updated
        if self._squelch_slider is not None:
            self._squelch_slider.setEnabled(enabled)
        self._refresh_squelch_button()
        self.params_changed.emit(updated)

    def _on_volume_changed(self, value: float) -> None:
        if self._mode is not MonitorOperatingMode.SDR:
            return
        vol = max(0.0, min(1.0, float(value) / 100.0))
        self._params = self._params.copy()
        self._params.audio_volume = vol
        self.audio_volume_changed.emit(vol)

    def _on_mute_toggled(self, muted: bool) -> None:
        if self._mode is not MonitorOperatingMode.SDR:
            return
        updated = self._params.copy()
        updated.audio_muted = bool(muted)
        self._params = updated
        self._refresh_mute_button()
        self.params_changed.emit(updated)

    def _refresh_squelch_button(self) -> None:
        if self._squelch_btn is None:
            return
        enabled = bool(self._params.squelch_enabled)
        self._squelch_btn.blockSignals(True)
        self._squelch_btn.setChecked(enabled)
        self._squelch_btn.setIcon(make_squelch_icon(self, enabled=enabled))
        self._squelch_btn.setToolTip(
            tr("monitor_radio_squelch_on") if enabled else tr("monitor_radio_squelch_off")
        )
        self._squelch_btn.blockSignals(False)
        if self._squelch_slider is not None:
            self._squelch_slider.setEnabled(enabled)

    def _refresh_mute_button(self) -> None:
        if self._mute_btn is None:
            return
        muted = bool(self._params.audio_muted)
        self._mute_btn.blockSignals(True)
        self._mute_btn.setChecked(muted)
        self._mute_btn.setIcon(make_audio_mute_icon(self, muted=muted))
        self._mute_btn.setToolTip(
            tr("monitor_radio_mute_on") if muted else tr("monitor_radio_mute_off")
        )
        self._mute_btn.blockSignals(False)

    def _notify_demod_blocked(self) -> None:
        notice = demod_requires_sdr_mode(self._params)
        if notice is not None:
            self.mode_restriction.emit(notice)

    def _demod_target_at(self, pos) -> QWidget | None:
        widget = self.childAt(pos)
        while widget is not None and widget is not self:
            if widget in self._demod_click_targets:
                return widget
            widget = widget.parentWidget()
        return None

    def mousePressEvent(self, event) -> None:
        if self._mode is MonitorOperatingMode.SPECTRUM and self._demod_target_at(event.pos()) is not None:
            self._notify_demod_blocked()
            event.accept()
            return
        super().mousePressEvent(event)

    def update_squelch_rf_level(self, rf_dbm: float | None) -> None:
        if self._squelch_slider is not None:
            self._squelch_slider.set_indicator_value(rf_dbm)

    def update_demod_signal_level(self, level_dbfs: float | None) -> None:
        self.update_squelch_rf_level(level_dbfs)

    def update_demod_state(self, state) -> None:
        if self._demod_display is not None and is_analog_receive_mode(self._params):
            self._demod_display.update_state(state)
        if self._rf_quality is not None and (self._params.demod_mode or "").lower() in ("wfm", "fm"):
            if bool(self._params.demod_wfm_rds):
                self._rf_quality.update_rds_info(state)
            else:
                self._rf_quality.clear_rds_info()

    def update_digital_analysis(self, state) -> None:
        if not is_digital_receive_mode(self._params):
            return
        if self._digital_panel is not None:
            self._digital_panel.update_state(state)

    def update_rf_metrics(self, metrics) -> None:
        if self._rf_quality is not None:
            self._rf_quality.update_metrics(metrics)

    def update_audio_output(self, *, active: bool, error: str = "") -> None:
        if self._audio_status is None:
            return
        if is_digital_receive_mode(self._params):
            if error:
                self._audio_status.setText(error)
                self._audio_status.setStyleSheet("color: #e07070;")
            else:
                self._audio_status.setText(tr("monitor_radio_digital_active"))
                self._audio_status.setStyleSheet("color: #6ecf8a;")
            return
        if error:
            self._audio_status.setText(error)
            self._audio_status.setStyleSheet("color: #e07070;")
        elif active:
            self._audio_status.setText(tr("monitor_radio_audio_live"))
            self._audio_status.setStyleSheet("color: #6ecf8a;")
        elif self._mode is MonitorOperatingMode.SDR:
            self._audio_status.setText(tr("monitor_demod_waiting"))
            self._audio_status.setStyleSheet("")
        else:
            self._refresh_mode_ui()

    def set_operating_mode(self, mode: MonitorOperatingMode | str) -> None:
        self._mode = MonitorOperatingMode.normalize(mode)
        self._refresh_mode_ui()

    def set_audio_volume_only(self, volume: float) -> None:
        """Actualiza volumen sin refrescar demod/VU."""
        vol = max(0.0, min(1.0, float(volume)))
        self._params = self._params.copy()
        self._params.audio_volume = vol
        if self._volume_slider is not None and not self._volume_slider.is_interacting():
            target = int(round(vol * 100))
            if abs(self._volume_slider.value() - target) >= 1:
                self._volume_slider.block_signals(True)
                self._volume_slider.set_value(target)
                self._volume_slider.block_signals(False)

    def set_params(self, params: SpectrumParams) -> None:
        self._params = params.copy()
        self._mode = MonitorOperatingMode.normalize(params.operating_mode)
        self._sync_widgets_from_params()
        self._sync_rf_bandwidth_strip()
        self._refresh_mode_ui()

    def sync_params_snapshot(self, params: SpectrumParams) -> None:
        """Actualiza _params interno sin repintar widgets (tras parche soft del controlador)."""
        self._params = params.copy()
        self._mode = MonitorOperatingMode.normalize(params.operating_mode)

    def sync_bandwidth_ui(self, params: SpectrumParams) -> None:
        """Franja BW demod + botón overlay — sin repintar todo el panel."""
        self._params = self._params.copy()
        self._params.demod_mode = params.demod_mode
        self._params.demod_bandwidth_hz = float(params.demod_bandwidth_hz)
        self._params.show_demod_bandwidth = bool(params.show_demod_bandwidth)
        self._params.operating_mode = params.operating_mode
        self._params.capture_mode = params.capture_mode
        self._params.audio_enabled = bool(params.audio_enabled)
        self._params.selected_freq_hz = float(params.selected_freq_hz)
        self._params.vfo_freq_hz = float(params.vfo_freq_hz)
        self._params.freq_readout = str(params.freq_readout or "fc")
        self._params.demod_wfm_stereo = bool(params.demod_wfm_stereo)
        self._params.demod_wfm_rds = bool(params.demod_wfm_rds)
        self._params.demod_wfm_lowpass = bool(getattr(params, "demod_wfm_lowpass", True))
        self._params.demod_iq_correction = bool(getattr(params, "demod_iq_correction", False))
        self._params.demod_iq_invert = bool(getattr(params, "demod_iq_invert", False))
        self._sync_rf_bandwidth_strip()
        if self._toolbar is not None:
            self._toolbar.sync_wfm_options(
                stereo=bool(self._params.demod_wfm_stereo),
                rds=bool(self._params.demod_wfm_rds),
                show_demod_bw=bool(self._params.show_demod_bandwidth),
                lowpass=bool(self._params.demod_wfm_lowpass),
                iq_correction=bool(self._params.demod_iq_correction),
                iq_invert=bool(self._params.demod_iq_invert),
            )

    def _sync_widgets_from_params(self) -> None:
        p = self._params
        if self._receive_combo is not None:
            mode = normalize_analog_demod_mode(p.demod_mode) if is_analog_receive_mode(p) else (p.demod_mode or "dig").lower()
            if mode not in RECEIVE_MODES:
                mode = "wfm"
            idx = self._receive_combo.findData(mode)
            if idx >= 0:
                self._receive_combo.blockSignals(True)
                self._receive_combo.setCurrentIndex(idx)
                self._receive_combo.blockSignals(False)
        self._sync_analog_fields_from_params(p)
        if self._vfo_spin is not None:
            self._vfo_spin.blockSignals(True)
            self._vfo_spin.setValue(p.vfo_freq_hz)
            self._vfo_spin.blockSignals(False)
        if self._squelch_slider is not None and not self._squelch_slider.is_interacting():
            if abs(self._squelch_slider.value() - float(p.squelch_db)) > 0.05:
                self._squelch_slider.block_signals(True)
                self._squelch_slider.set_value(p.squelch_db)
                self._squelch_slider.block_signals(False)
        self._refresh_squelch_button()
        self._sync_rf_bandwidth_strip()
        if self._volume_slider is not None and not self._volume_slider.is_interacting():
            target = int(round(p.audio_volume * 100))
            if abs(self._volume_slider.value() - target) >= 1:
                self._volume_slider.block_signals(True)
                self._volume_slider.set_value(target)
                self._volume_slider.block_signals(False)
        self._refresh_mute_button()
        if self._toolbar is not None:
            self._toolbar.sync_wfm_options(
                stereo=bool(p.demod_wfm_stereo),
                rds=bool(p.demod_wfm_rds),
                show_demod_bw=bool(p.show_demod_bandwidth),
                lowpass=bool(getattr(p, "demod_wfm_lowpass", True)),
                iq_correction=bool(getattr(p, "demod_iq_correction", False)),
                iq_invert=bool(getattr(p, "demod_iq_invert", False)),
            )
        self._sync_digital_widgets_from_params()

    def _sync_analog_fields_from_params(self, params: SpectrumParams | None = None) -> None:
        p = params or self._params
        if self._bw_spin is not None:
            self._bw_spin.blockSignals(True)
            self._bw_spin.setValue(int(round(p.demod_bandwidth_hz)))
            self._bw_spin.blockSignals(False)
        if self._snap_spin is not None:
            self._snap_spin.blockSignals(True)
            self._snap_spin.setValue(int(round(p.demod_snap_interval)))
            self._snap_spin.blockSignals(False)
        if self._deemph_combo is not None:
            idx = self._deemph_combo.findData(p.demod_deemphasis)
            if idx < 0:
                idx = self._deemph_combo.findData("none")
            if idx >= 0:
                self._deemph_combo.blockSignals(True)
                self._deemph_combo.setCurrentIndex(idx)
                self._deemph_combo.blockSignals(False)
        if self._noise_blank_spin is not None:
            self._noise_blank_spin.blockSignals(True)
            self._noise_blank_spin.setValue(float(p.demod_noise_blanker_db))
            self._noise_blank_spin.blockSignals(False)
        if self._agc_attack_spin is not None:
            self._agc_attack_spin.blockSignals(True)
            self._agc_attack_spin.setValue(int(round(p.demod_agc_attack)))
            self._agc_attack_spin.blockSignals(False)
        if self._agc_decay_spin is not None:
            self._agc_decay_spin.blockSignals(True)
            self._agc_decay_spin.setValue(int(round(p.demod_agc_decay)))
            self._agc_decay_spin.blockSignals(False)

    def _set_form_row_visible(self, field: QWidget, visible: bool) -> None:
        field.setVisible(visible)
        if self._mode_form is not None:
            label = self._mode_form.labelForField(field)
            if label is not None:
                label.setVisible(visible)

    def _refresh_analog_mode_fields(self) -> None:
        mode = normalize_analog_demod_mode(self._params.demod_mode)
        show_deemph = mode_shows_deemphasis(mode)
        show_dsb = mode_shows_dsb_controls(mode)
        show_wfm = mode_shows_wfm_if_controls(mode)
        self._apply_demod_ui_limits(mode)
        self._set_form_row_visible(self._deemph_combo, show_deemph)
        self._set_form_row_visible(self._noise_blank_spin, show_dsb or show_wfm)
        self._set_form_row_visible(self._agc_attack_spin, show_dsb)
        self._set_form_row_visible(self._agc_decay_spin, show_dsb)
        self._set_form_row_visible(self._bw_spin, False)
        if self._deemph_combo is not None:
            is_nfm = mode == "nfm"
            self._deemph_combo.setEnabled(show_deemph and not is_nfm)
            if is_nfm:
                idx = self._deemph_combo.findData("none")
                if idx >= 0:
                    self._deemph_combo.blockSignals(True)
                    self._deemph_combo.setCurrentIndex(idx)
                    self._deemph_combo.blockSignals(False)

    def _apply_demod_ui_limits(self, mode: str) -> None:
        limits = demod_ui_limits(mode)
        if self._bw_spin is not None:
            self._bw_spin.setRange(limits.bw_min_hz, limits.bw_max_hz)
            self._bw_spin.setSingleStep(limits.bw_step_hz)
            if not (limits.bw_min_hz <= self._bw_spin.value() <= limits.bw_max_hz):
                self._bw_spin.blockSignals(True)
                self._bw_spin.setValue(
                    int(round(self._params.demod_bandwidth_hz or limits.bw_min_hz))
                )
                self._bw_spin.blockSignals(False)
        if self._rf_quality is not None:
            self._rf_quality.configure_demod_bandwidth(
                demod_bw_hz=float(self._params.demod_bandwidth_hz),
                min_hz=float(limits.bw_min_hz),
                max_hz=float(limits.bw_max_hz),
                step_hz=float(limits.bw_step_hz),
            )
        if self._snap_spin is not None:
            self._snap_spin.setRange(limits.snap_min_hz, limits.snap_max_hz)
            self._snap_spin.setSingleStep(limits.snap_step_hz)
            if self._vfo_spin is not None:
                self._vfo_spin.setSingleStep(float(limits.snap_step_hz))

    def _sync_digital_widgets_from_params(self) -> None:
        p = self._params
        if self._digital_profile_combo is not None:
            idx = self._digital_profile_combo.findData(p.digital_profile)
            if idx < 0:
                idx = self._digital_profile_combo.findData("custom")
            if idx >= 0:
                self._digital_profile_combo.blockSignals(True)
                self._digital_profile_combo.setCurrentIndex(idx)
                self._digital_profile_combo.blockSignals(False)
        if self._digital_symbol_spin is not None:
            self._digital_symbol_spin.blockSignals(True)
            self._digital_symbol_spin.setValue(p.digital_symbol_rate_hz)
            self._digital_symbol_spin.blockSignals(False)
        if self._digital_mod_combo is not None:
            idx = self._digital_mod_combo.findData(int(p.digital_mod_order or 4))
            if idx < 0:
                idx = 0
            self._digital_mod_combo.blockSignals(True)
            self._digital_mod_combo.setCurrentIndex(idx)
            self._digital_mod_combo.blockSignals(False)
        is_dab = p.digital_profile == "dab_iii"
        if self._digital_mod_combo is not None:
            self._digital_mod_combo.setEnabled(not is_dab)
        if self._digital_symbol_spin is not None:
            self._digital_symbol_spin.setEnabled(not is_dab)

    def _refresh_mode_ui(self) -> None:
        sdr = self._mode is MonitorOperatingMode.SDR
        analyzer_only = is_analyzer_only_source(self._params.source_id)
        iq_capture = self._params.capture_mode == "iq"
        is_dig = sdr and is_digital_receive_mode(self._params)
        is_analog = sdr and is_analog_receive_mode(self._params)
        digital_active = iq_capture and is_dig

        if self._mode_banner is not None:
            if analyzer_only:
                self._mode_banner.setText(tr("monitor_source_radio_analyzer_only_banner"))
                self._mode_banner.setStyleSheet(
                    "color: #e0a060; background: rgba(224, 160, 96, 24);"
                    "padding: 6px 8px; border-radius: 4px;"
                )
                self._mode_banner.setVisible(True)
            elif not sdr:
                self._mode_banner.setText(tr("monitor_radio_spectrum_mode_banner"))
                self._mode_banner.setStyleSheet(
                    "color: #c9a227; background: rgba(201, 162, 39, 24);"
                    "padding: 6px 8px; border-radius: 4px;"
                )
                self._mode_banner.setVisible(True)
            else:
                self._mode_banner.setVisible(False)

        effective_sdr = sdr and not analyzer_only
        if self._form_host is not None:
            self._form_host.setEnabled(effective_sdr)
        if self._toolbar is not None:
            self._toolbar.set_auto_enabled(effective_sdr and is_analog)
            show_fm = effective_sdr and is_analog and normalize_analog_demod_mode(self._params.demod_mode) == "wfm"
            self._toolbar.set_wfm_toggles_visible(show_fm)
            self._toolbar.set_wfm_toggles_enabled(effective_sdr and show_fm)

        for widget in (self._receive_combo, self._vfo_spin):
            if widget is not None:
                widget.setEnabled(effective_sdr)

        for widget in self._analog_widgets:
            widget.setEnabled(effective_sdr and is_analog)
            widget.setVisible(not is_dig or widget is not self._demod_display)

        if self._demod_display is not None:
            self._demod_display.setVisible(is_analog)

        self._refresh_analog_mode_fields()

        if self._digital_form_host is not None:
            self._digital_form_host.setVisible(is_dig)
            self._digital_form_host.setEnabled(effective_sdr and is_dig and iq_capture)

        for widget in self._digital_widgets:
            widget.setEnabled(effective_sdr and is_dig and iq_capture)
            widget.setVisible(is_dig)

        if self._digital_panel is not None:
            self._digital_panel.setVisible(is_dig)
            is_dab = is_dig and self._params.digital_profile == "dab_iii"
            self._digital_panel.set_welle_controls_visible(effective_sdr and is_dab)
            if not effective_sdr or not is_dig:
                self._digital_panel.set_idle(message=tr("monitor_digital_select_dig"))
            elif not iq_capture:
                self._digital_panel.set_idle(message=tr("monitor_digital_iq_required"))
            elif not digital_active:
                self._digital_panel.set_idle(message=tr("monitor_digital_idle"))

        if self._rf_quality is not None:
            self._rf_quality.setVisible(effective_sdr and (is_analog or is_dig))
            if analyzer_only:
                self._rf_quality.set_idle(message=tr("monitor_source_rf_quality_analyzer_only"))
            elif not sdr:
                self._rf_quality.set_idle(message=tr("monitor_rf_sdr_only"))
            elif self._mode is MonitorOperatingMode.SUPERVISION:
                self._rf_quality.set_idle(message=tr("monitor_rf_supervision_off"))

        demod_tip = (
            tr("monitor_source_warn_demod_analyzer_only")
            if analyzer_only
            else tr("monitor_mode_warn_demod_sdr_only")
        )
        for widget in self._demod_click_targets:
            if widget is None:
                continue
            if self._mode is MonitorOperatingMode.SDR:
                widget.setToolTip("")
            elif not widget.isEnabled():
                widget.setToolTip(demod_tip)

        if self._audio_status is not None:
            if is_dig and sdr:
                self._audio_status.setText(tr("monitor_radio_digital_active"))
            elif sdr and is_analog:
                self._audio_status.setText(tr("monitor_radio_audio_live"))
            elif self._mode is MonitorOperatingMode.SUPERVISION:
                self._audio_status.setText(tr("monitor_radio_supervision_pending"))
            else:
                self._audio_status.setText(tr("monitor_radio_audio_off"))
                self._audio_status.setStyleSheet("color: #9aa8b0;")

    def recargar_textos(self) -> None:
        if self._receive_combo is not None:
            for i, mode in enumerate(RECEIVE_MODES):
                self._receive_combo.setItemText(i, tr(f"monitor_demod_{mode}"))
        if self._deemph_combo is not None:
            for i, choice in enumerate(DEEMPHASIS_CHOICES):
                self._deemph_combo.setItemText(i, tr(f"monitor_demod_deemph_{choice}"))
        if self._demod_display is not None:
            self._demod_display.recargar_textos()
        if self._digital_panel is not None:
            self._digital_panel.recargar_textos()
        if self._digital_profile_combo is not None:
            for i, profile_id in enumerate(PROFILE_CHOICES):
                self._digital_profile_combo.setItemText(i, tr(DIGITAL_PROFILES[profile_id].label_key))
        if self._digital_mod_combo is not None:
            for i, (order, label_key) in enumerate(MOD_ORDER_CHOICES):
                self._digital_mod_combo.setItemText(i, tr(label_key))
        if self._toolbar is not None:
            self._toolbar.recargar_textos()
        if self._rf_quality is not None:
            self._rf_quality.recargar_textos()
        self._refresh_mode_ui()
