"""Barra de herramientas compacta del Monitor (transporte, modo, FC, SPAN, ganancias)."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from core.monitor.hackrf_rx_gains import VGA_GAIN_MAX_DB
from core.monitor.monitor_freq_span_logic import patch_hackrf_vga
from core.monitor.monitor_operating_mode import MODE_CHOICES, MonitorOperatingMode
from core.monitor.spectrum_params import SpectrumParams
from gui.icon_utils import ICON_SIZE_TOOLBAR, get_app_icon
from gui.monitor.monitor_ampt_control import MonitorAmptControl
from gui.monitor.monitor_bw_sweep_controls import (
    MonitorFftControl,
    MonitorRbwControl,
    MonitorSweepControl,
    MonitorVbwControl,
)
from gui.monitor.monitor_export_menu import MonitorExportMenuButton
from gui.monitor.monitor_freq_span_controls import (
    MonitorFreqControl,
    MonitorSpanControl,
    TOOLBAR_FREQ_MIN_WIDTH,
    TOOLBAR_SPAN_MIN_WIDTH,
)
from gui.monitor.monitor_lcd_styles import (
    MONITOR_TOOLBAR_CONTROL_HEIGHT,
    MONITOR_TOOLBAR_GROUP_HEIGHT,
    apply_monitor_toolbar_chrome,
    configure_monitor_toolbar_control,
    configure_monitor_toolbar_group,
    configure_monitor_toolbar_mode_button,
)
from gui.monitor.monitor_lna_control import MonitorLnaControl
from gui.monitor.monitor_numeric_control import MonitorNumericControl
from gui.monitor.monitor_shortcuts import MONITOR_SHORTCUTS
from gui.shortcut_tooltips import tooltip_with_shortcut
from i18n.json_translation import tr


class MonitorToolBarWidget(QWidget):
    """Toolbar Monitor: PLAY/STOP · Analizador/SDR · FC · SPAN · LNA · VGA."""

    params_changed = pyqtSignal(object)
    play_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    trigger_requested = pyqtSignal()
    operating_mode_changed = pyqtSignal(str)

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._params = SpectrumParams()
        self._running = False
        self._connecting = False
        self._syncing = False
        self._last_patch_keys: list[str] = []
        self._transport_btn: Optional[QToolButton] = None
        self._mode_buttons: dict[str, QToolButton] = {}
        self._mode_frame: Optional[QFrame] = None
        self._freq: Optional[MonitorFreqControl] = None
        self._span: Optional[MonitorSpanControl] = None
        self._fft: Optional[MonitorFftControl] = None
        self._rbw: Optional[MonitorRbwControl] = None
        self._vbw: Optional[MonitorVbwControl] = None
        self._sweep: Optional[MonitorSweepControl] = None
        self._ampt: Optional[MonitorAmptControl] = None
        self._lna: Optional[MonitorLnaControl] = None
        self._vga: Optional[MonitorNumericControl] = None
        self._export_btn: Optional[MonitorExportMenuButton] = None
        self._trigger_btn: Optional[QToolButton] = None
        self._build()
        apply_monitor_toolbar_chrome(self)
        self.setMinimumHeight(MONITOR_TOOLBAR_GROUP_HEIGHT + 4)
        self.setMinimumWidth(640)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.set_params(self._params)

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 2)
        root.setSpacing(6)

        self._transport_btn = QToolButton(self)
        self._transport_btn.setObjectName("MonitorToolbarTransportBtn")
        self._transport_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._transport_btn.setMinimumWidth(92)
        self._transport_btn.clicked.connect(self._on_transport_clicked)
        root.addWidget(self._transport_btn)

        mode_frame = QFrame(self)
        mode_frame.setObjectName("MonitorToolbarMode")
        mode_frame.setMinimumWidth(168)
        self._mode_frame = mode_frame
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(8, 4, 8, 4)
        mode_layout.setSpacing(6)
        configure_monitor_toolbar_group(mode_frame, mode_layout)
        mode_group = QButtonGroup(mode_frame)
        mode_group.setExclusive(True)
        for mode in MODE_CHOICES:
            btn = QToolButton(mode_frame)
            btn.setObjectName(f"MonitorToolbarMode_{mode.value}")
            btn.setText(tr(mode.label_key()))
            btn.setCheckable(True)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            configure_monitor_toolbar_mode_button(btn)
            btn.clicked.connect(lambda _checked=False, m=mode: self._on_mode_clicked(m))
            mode_group.addButton(btn)
            self._mode_buttons[mode.value] = btn
            mode_layout.addWidget(btn, stretch=1)
        self._mode_buttons[MonitorOperatingMode.SPECTRUM.value].setChecked(True)
        root.addWidget(mode_frame)

        freq_frame = QFrame(self)
        freq_frame.setObjectName("MonitorToolbarFreqGroup")
        freq_frame.setMinimumWidth(TOOLBAR_FREQ_MIN_WIDTH + TOOLBAR_SPAN_MIN_WIDTH + 20)
        freq_layout = QHBoxLayout(freq_frame)
        freq_layout.setContentsMargins(8, 4, 8, 4)
        freq_layout.setSpacing(6)
        configure_monitor_toolbar_group(freq_frame, freq_layout)

        self._freq = MonitorFreqControl(parent=freq_frame)
        self._freq.bind_patch(self._patch_params)
        configure_monitor_toolbar_control(self._freq)
        freq_layout.addWidget(self._freq, stretch=3)

        self._span = MonitorSpanControl(parent=freq_frame)
        self._span.bind_patch(self._patch_params)
        configure_monitor_toolbar_control(self._span)
        freq_layout.addWidget(self._span, stretch=1)
        root.addWidget(freq_frame)

        rf_frame = QFrame(self)
        rf_frame.setObjectName("MonitorToolbarRfGroup")
        rf_layout = QHBoxLayout(rf_frame)
        rf_layout.setContentsMargins(8, 4, 8, 4)
        rf_layout.setSpacing(6)
        configure_monitor_toolbar_group(rf_frame, rf_layout)

        self._ampt = MonitorAmptControl(parent=rf_frame)
        self._ampt.bind_patch(self._patch_params)
        configure_monitor_toolbar_control(self._ampt)
        rf_layout.addWidget(self._ampt)

        self._lna = MonitorLnaControl(parent=rf_frame)
        self._lna.bind_patch(self._patch_params)
        configure_monitor_toolbar_control(self._lna)
        rf_layout.addWidget(self._lna)

        self._vga = MonitorNumericControl(
            tr("monitor_lcd_vga"),
            suffix=" dB",
            decimals=0,
            minimum=0,
            maximum=VGA_GAIN_MAX_DB,
            step=2,
            parent=rf_frame,
        )
        self._vga.value_changed.connect(self._on_vga_changed)
        configure_monitor_toolbar_control(self._vga)
        rf_layout.addWidget(self._vga)
        root.addWidget(rf_frame)

        root.addStretch(1)

        bw_frame = QFrame(self)
        bw_frame.setObjectName("MonitorToolbarBwGroup")
        bw_layout = QHBoxLayout(bw_frame)
        bw_layout.setContentsMargins(8, 4, 8, 4)
        bw_layout.setSpacing(6)
        configure_monitor_toolbar_group(bw_frame, bw_layout)

        self._fft = MonitorFftControl(parent=bw_frame)
        self._fft.bind_patch(self._patch_params)
        configure_monitor_toolbar_control(self._fft)
        bw_layout.addWidget(self._fft)

        self._rbw = MonitorRbwControl(parent=bw_frame)
        self._rbw.bind_patch(self._patch_params)
        configure_monitor_toolbar_control(self._rbw)
        bw_layout.addWidget(self._rbw)

        self._vbw = MonitorVbwControl(parent=bw_frame)
        self._vbw.bind_patch(self._patch_params)
        configure_monitor_toolbar_control(self._vbw)
        bw_layout.addWidget(self._vbw)

        self._sweep = MonitorSweepControl(parent=bw_frame)
        self._sweep.bind_patch(self._patch_params)
        configure_monitor_toolbar_control(self._sweep)
        bw_layout.addWidget(self._sweep)

        root.addWidget(bw_frame)

        utils_frame = QFrame(self)
        utils_frame.setObjectName("MonitorToolbarUtilsGroup")
        utils_layout = QHBoxLayout(utils_frame)
        utils_layout.setContentsMargins(8, 4, 8, 4)
        utils_layout.setSpacing(6)
        configure_monitor_toolbar_group(utils_frame, utils_layout)

        self._trigger_btn = QToolButton(utils_frame)
        self._trigger_btn.setObjectName("MonitorToolbarTriggerBtn")
        self._trigger_btn.setText(tr("monitor_tb_trigger"))
        self._trigger_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._trigger_btn.setMinimumHeight(28)
        self._trigger_btn.clicked.connect(self._on_trigger_clicked)
        utils_layout.addWidget(self._trigger_btn)

        self._export_btn = MonitorExportMenuButton(utils_frame)
        self._export_btn.apply_icon(get_app_icon("snapshot", ICON_SIZE_TOOLBAR))
        utils_layout.addWidget(self._export_btn)

        root.addWidget(utils_frame)
        self._apply_tooltips()
        self._refresh_trigger_button()
        self._refresh_mode_button_labels()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_mode_button_labels()

    def _refresh_mode_button_labels(self) -> None:
        compact = self.width() < 920
        short_labels = {
            MonitorOperatingMode.SPECTRUM.value: tr("monitor_mode_analyzer_short"),
            MonitorOperatingMode.SDR.value: tr("monitor_mode_sdr_short"),
        }
        for mode in MODE_CHOICES:
            btn = self._mode_buttons.get(mode.value)
            if btn is None:
                continue
            full = tr(mode.label_key())
            btn.setText(short_labels.get(mode.value, full) if compact else full)
            btn.setToolTip(full)
            btn.setMinimumWidth(56 if compact else 68)

    def _apply_tooltips(self) -> None:
        if self._transport_btn is not None:
            if self._connecting:
                base = tr("monitor_tip_connecting")
            elif self._running:
                base = tr("monitor_tip_stop")
            else:
                base = tr("monitor_tip_play")
            self._transport_btn.setToolTip(
                tooltip_with_shortcut(base, MONITOR_SHORTCUTS["transport"])
            )
        for mode in MODE_CHOICES:
            btn = self._mode_buttons.get(mode.value)
            if btn is None:
                continue
            if mode is MonitorOperatingMode.SPECTRUM:
                btn.setToolTip(tr("monitor_tip_mode_analyzer"))
            elif mode is MonitorOperatingMode.SDR:
                btn.setToolTip(tr("monitor_tip_mode_sdr"))
        self._refresh_mode_button_labels()
        if self._freq is not None:
            self._freq._apply_tooltips()
        if self._span is not None:
            self._span._apply_tooltips()
        if self._rbw is not None:
            self._rbw._apply_tooltips()
        if self._fft is not None:
            self._fft._apply_tooltips()
        if self._vbw is not None:
            self._vbw._apply_tooltips()
        if self._sweep is not None:
            self._sweep._apply_tooltips()
        if self._ampt is not None:
            self._ampt._apply_tooltips()
        if self._lna is not None:
            self._lna._apply_tooltips()
        if self._vga is not None:
            self._vga.set_tooltips(tr("monitor_tip_vga"))
        if self._export_btn is not None:
            self._export_btn.setToolTip(tr("monitor_tip_export_menu"))
        if self._trigger_btn is not None:
            self._trigger_btn.setToolTip(
                tooltip_with_shortcut(tr("monitor_tip_trigger"), MONITOR_SHORTCUTS["trigger"])
            )

    def set_live_display_scale(self, ref_level_dbm: float, ref_range_db: float) -> None:
        if self._ampt is not None:
            self._ampt.set_live_scale(ref_level_dbm, ref_range_db)

    def _on_trigger_clicked(self) -> None:
        if self._syncing:
            return
        self.trigger_requested.emit()

    def _refresh_trigger_button(self) -> None:
        if self._trigger_btn is None:
            return
        mode = self._params.sweep_trigger_mode
        manual = mode == "manual"
        periodic = mode == "periodic"
        self._trigger_btn.setVisible(manual or periodic)
        self._trigger_btn.setEnabled(manual or periodic)
        if manual:
            self._trigger_btn.setText(tr("monitor_tb_trigger"))
        elif periodic:
            self._trigger_btn.setText(tr("monitor_tb_trigger_now"))

    def _patch_params(self, updated: SpectrumParams) -> None:
        if self._syncing:
            return
        from core.monitor.monitor_flow_log import TOOLBAR_PARAM_KEYS, diff_param_keys

        prev = self._params.copy()
        self._params = updated.copy()
        self._last_patch_keys = list(diff_param_keys(prev, self._params, TOOLBAR_PARAM_KEYS))
        if not self._last_patch_keys:
            return
        self._refresh_trigger_button()
        self.params_changed.emit(self._params)

    def consume_patch_keys(self) -> list[str]:
        keys = list(self._last_patch_keys)
        self._last_patch_keys = []
        return keys

    def _on_vga_changed(self, value: float) -> None:
        if self._syncing:
            return
        updated = patch_hackrf_vga(self._params, int(value))
        self._patch_params(updated)

    def _on_transport_clicked(self) -> None:
        if self._running or self._connecting:
            self.stop_requested.emit()
        else:
            self.play_requested.emit()

    def _on_mode_clicked(self, mode: MonitorOperatingMode) -> None:
        if self._params.operating_mode == mode.value:
            return
        self.operating_mode_changed.emit(mode.value)

    def set_operating_mode(self, mode: str) -> None:
        normalized = MonitorOperatingMode.normalize(mode)
        btn = self._mode_buttons.get(normalized.value)
        if btn is not None:
            btn.blockSignals(True)
            btn.setChecked(True)
            btn.blockSignals(False)

    def set_running(self, running: bool, *, connecting: bool = False) -> None:
        self._running = running
        self._connecting = connecting
        self._refresh_transport()

    def _refresh_transport(self) -> None:
        if self._transport_btn is None:
            return
        if self._connecting:
            self._transport_btn.setText(tr("monitor_tb_connecting"))
            self._transport_btn.setEnabled(False)
            self._transport_btn.setProperty("monitorState", "connecting")
        elif self._running:
            self._transport_btn.setText(tr("monitor_tb_stop"))
            self._transport_btn.setEnabled(True)
            self._transport_btn.setProperty("monitorState", "running")
        else:
            self._transport_btn.setText(tr("monitor_tb_play"))
            self._transport_btn.setEnabled(True)
            self._transport_btn.setProperty("monitorState", "idle")
        self._transport_btn.style().unpolish(self._transport_btn)
        self._transport_btn.style().polish(self._transport_btn)
        self._apply_tooltips()

    def get_params(self) -> SpectrumParams:
        return self._params.copy()

    def commit_numeric_editing(self) -> None:
        if self._freq is not None:
            self._freq.commit_editing()
        if self._span is not None:
            self._span.commit_editing()
        if self._rbw is not None:
            self._rbw.commit_editing()
        if self._fft is not None:
            self._fft.commit_editing()
        if self._vbw is not None:
            self._vbw.commit_editing()
        if self._sweep is not None:
            self._sweep.commit_editing()

    def set_channelization_service(self, service) -> None:
        if self._freq is not None:
            self._freq.set_channelization_service(service)

    def set_params(self, params: SpectrumParams, *, force: bool = False) -> None:
        prev = self._params
        self._syncing = True
        try:
            self._params = params.copy()
            self.set_operating_mode(params.operating_mode)
            if self._freq is not None:
                freq_force = force and not self._freq.is_user_editing()
                self._freq.set_params(self._params, force=freq_force)
            if self._span is not None:
                span_force = force and not self._span.is_user_editing()
                self._span.set_params(self._params, force=span_force)
            if self._fft is not None:
                self._fft.set_params(self._params)
            if self._rbw is not None:
                self._rbw.set_params(self._params)
            if self._vbw is not None:
                self._vbw.set_params(self._params)
            if self._sweep is not None:
                self._sweep.set_params(self._params)
            if self._ampt is not None:
                self._ampt.set_params(self._params)
            if self._lna is not None and (
                force
                or int(prev.lna_gain_db) != int(params.lna_gain_db)
                or bool(prev.rf_amp_enable) != bool(params.rf_amp_enable)
            ):
                self._lna.set_params(self._params)
            if self._vga is not None and (
                force or int(prev.vga_gain_db) != int(params.vga_gain_db)
            ):
                self._vga.set_value(float(self._params.vga_gain_db), force=force)
            self._refresh_trigger_button()
        finally:
            self._syncing = False
        self._apply_analyzer_source_ui(self._params)

    def _apply_analyzer_source_ui(self, params: SpectrumParams) -> None:
        from core.rf.source_ids import is_analyzer_only_source
        from i18n.json_translation import tr

        blocked = is_analyzer_only_source(params.source_id)
        sdr_btn = self._mode_buttons.get(MonitorOperatingMode.SDR.value)
        if sdr_btn is not None:
            sdr_btn.setEnabled(not blocked)
            if blocked:
                sdr_btn.setToolTip(tr("monitor_source_tip_sdr_blocked"))
            else:
                sdr_btn.setToolTip(tr("monitor_tip_mode_sdr"))
        if self._lna is not None:
            self._lna.setVisible(not blocked)
        if self._vga is not None:
            self._vga.setVisible(not blocked)
        self._refresh_mode_button_labels()

    def recargar_textos(self) -> None:
        self._refresh_mode_button_labels()
        if self._freq is not None:
            self._freq.recargar_textos()
        if self._span is not None:
            self._span.recargar_textos()
        if self._fft is not None:
            self._fft.recargar_textos()
        if self._rbw is not None:
            self._rbw.recargar_textos()
        if self._vbw is not None:
            self._vbw.recargar_textos()
        if self._sweep is not None:
            self._sweep.recargar_textos()
        if self._ampt is not None:
            self._ampt.recargar_textos()
        if self._lna is not None:
            self._lna.recargar_textos()
        if self._vga is not None:
            self._vga.set_title(tr("monitor_lcd_vga"))
        if self._export_btn is not None:
            self._export_btn.recargar_textos()
        if self._trigger_btn is not None:
            self._trigger_btn.setText(tr("monitor_tb_trigger"))
        self._refresh_transport()
        self._apply_tooltips()
        self.set_params(self._params)
