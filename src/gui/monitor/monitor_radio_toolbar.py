"""Barra de iconos del panel RADIO (AUTO, FM Broad, WFM, ayuda)."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QToolButton, QWidget

from gui.monitor.monitor_info_button import MonitorInfoButton
from gui.monitor.monitor_radio_icons import (
    make_auto_tune_icon,
    make_demod_bw_icon,
    make_fm_broadcast_icon,
    make_iq_correction_icon,
    make_iq_invert_icon,
    make_lowpass_icon,
    make_rds_icon,
    make_stereo_icon,
)
from i18n.json_translation import tr

_TOOL_BTN_SIZE = QSize(28, 26)
_TOOL_ICON_SIZE = QSize(18, 18)


class MonitorRadioToolbar(QWidget):
    auto_tune_requested = pyqtSignal()
    fm_broadcast_requested = pyqtSignal()
    wfm_stereo_toggled = pyqtSignal(bool)
    wfm_rds_toggled = pyqtSignal(bool)
    show_demod_bw_toggled = pyqtSignal(bool)
    wfm_lowpass_toggled = pyqtSignal(bool)
    iq_correction_toggled = pyqtSignal(bool)
    iq_invert_toggled = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._auto_btn: QToolButton | None = None
        self._fm_btn: QToolButton | None = None
        self._stereo_btn: QToolButton | None = None
        self._rds_btn: QToolButton | None = None
        self._bw_btn: QToolButton | None = None
        self._lowpass_btn: QToolButton | None = None
        self._iq_corr_btn: QToolButton | None = None
        self._iq_inv_btn: QToolButton | None = None
        self._info: MonitorInfoButton | None = None
        self._syncing = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._auto_btn = self._make_tool_button(
            icon_factory=make_auto_tune_icon,
            tip_key="monitor_auto_tune_tip",
            object_name="MonitorRadioAutoTuneBtn",
        )
        self._auto_btn.clicked.connect(self.auto_tune_requested.emit)
        layout.addWidget(self._auto_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._fm_btn = self._make_tool_button(
            icon_factory=make_fm_broadcast_icon,
            tip_key="monitor_fm_broadcast_tip",
            object_name="MonitorRadioFmBroadcastBtn",
        )
        self._fm_btn.clicked.connect(self.fm_broadcast_requested.emit)
        layout.addWidget(self._fm_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addSpacing(4)

        self._stereo_btn = self._make_toggle_button(
            icon_factory=make_stereo_icon,
            tip_key="monitor_radio_wfm_stereo_tip",
            object_name="MonitorRadioStereoBtn",
        )
        self._stereo_btn.toggled.connect(self.wfm_stereo_toggled.emit)
        layout.addWidget(self._stereo_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._rds_btn = self._make_toggle_button(
            icon_factory=make_rds_icon,
            tip_key="monitor_radio_wfm_rds_tip",
            object_name="MonitorRadioRdsBtn",
        )
        self._rds_btn.toggled.connect(self.wfm_rds_toggled.emit)
        layout.addWidget(self._rds_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._bw_btn = self._make_toggle_button(
            icon_factory=make_demod_bw_icon,
            tip_key="monitor_radio_show_demod_bw_tip",
            object_name="MonitorRadioDemodBwBtn",
        )
        self._bw_btn.toggled.connect(self.show_demod_bw_toggled.emit)
        layout.addWidget(self._bw_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._lowpass_btn = self._make_toggle_button(
            icon_factory=make_lowpass_icon,
            tip_key="monitor_radio_wfm_lowpass_tip",
            object_name="MonitorRadioLowpassBtn",
        )
        self._lowpass_btn.toggled.connect(self.wfm_lowpass_toggled.emit)
        layout.addWidget(self._lowpass_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._iq_corr_btn = self._make_toggle_button(
            icon_factory=make_iq_correction_icon,
            tip_key="monitor_radio_iq_correction_tip",
            object_name="MonitorRadioIqCorrectionBtn",
        )
        self._iq_corr_btn.toggled.connect(self.iq_correction_toggled.emit)
        layout.addWidget(self._iq_corr_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._iq_inv_btn = self._make_toggle_button(
            icon_factory=make_iq_invert_icon,
            tip_key="monitor_radio_iq_invert_tip",
            object_name="MonitorRadioIqInvertBtn",
        )
        self._iq_inv_btn.toggled.connect(self.iq_invert_toggled.emit)
        layout.addWidget(self._iq_inv_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch(1)

        self._info = MonitorInfoButton(
            title_key="monitor_radio_info_title",
            body_key="monitor_radio_info_body",
        )
        layout.addWidget(self._info, alignment=Qt.AlignmentFlag.AlignVCenter)

        from gui.app_chrome_styles import apply_monitor_freq_manager_styles

        apply_monitor_freq_manager_styles(self)

    def _make_tool_button(
        self,
        *,
        icon_factory,
        tip_key: str,
        object_name: str,
    ) -> QToolButton:
        btn = QToolButton(self)
        btn.setObjectName(object_name)
        btn.setIcon(icon_factory(self))
        btn.setIconSize(_TOOL_ICON_SIZE)
        btn.setFixedSize(_TOOL_BTN_SIZE)
        btn.setToolTip(tr(tip_key))
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setAutoRaise(True)
        return btn

    def _make_toggle_button(
        self,
        *,
        icon_factory,
        tip_key: str,
        object_name: str,
    ) -> QToolButton:
        btn = self._make_tool_button(
            icon_factory=icon_factory,
            tip_key=tip_key,
            object_name=object_name,
        )
        btn.setCheckable(True)
        return btn

    def set_auto_enabled(self, enabled: bool) -> None:
        if self._auto_btn is not None:
            self._auto_btn.setEnabled(enabled)
            self._auto_btn.setVisible(enabled)

    def set_fm_enabled(self, enabled: bool) -> None:
        if self._fm_btn is not None:
            self._fm_btn.setEnabled(enabled)
            self._fm_btn.setVisible(enabled)

    def set_wfm_toggles_visible(self, visible: bool) -> None:
        for btn in (
            self._stereo_btn,
            self._rds_btn,
            self._bw_btn,
            self._lowpass_btn,
            self._iq_corr_btn,
            self._iq_inv_btn,
        ):
            if btn is not None:
                btn.setVisible(visible)

    def set_wfm_toggles_enabled(self, enabled: bool) -> None:
        for btn in (
            self._stereo_btn,
            self._rds_btn,
            self._bw_btn,
            self._lowpass_btn,
            self._iq_corr_btn,
            self._iq_inv_btn,
        ):
            if btn is not None:
                btn.setEnabled(enabled)

    def sync_wfm_options(
        self,
        *,
        stereo: bool,
        rds: bool,
        show_demod_bw: bool,
        lowpass: bool,
        iq_correction: bool,
        iq_invert: bool,
    ) -> None:
        self._syncing = True
        for btn, value in (
            (self._stereo_btn, stereo),
            (self._rds_btn, rds),
            (self._bw_btn, show_demod_bw),
            (self._lowpass_btn, lowpass),
            (self._iq_corr_btn, iq_correction),
            (self._iq_inv_btn, iq_invert),
        ):
            if btn is not None:
                btn.blockSignals(True)
                btn.setChecked(bool(value))
                btn.blockSignals(False)
        self._syncing = False

    def recargar_textos(self) -> None:
        if self._auto_btn is not None:
            self._auto_btn.setToolTip(tr("monitor_auto_tune_tip"))
            self._auto_btn.setIcon(make_auto_tune_icon(self))
        if self._fm_btn is not None:
            self._fm_btn.setToolTip(tr("monitor_fm_broadcast_tip"))
            self._fm_btn.setIcon(make_fm_broadcast_icon(self))
        if self._stereo_btn is not None:
            self._stereo_btn.setToolTip(tr("monitor_radio_wfm_stereo_tip"))
            self._stereo_btn.setIcon(make_stereo_icon(self))
        if self._rds_btn is not None:
            self._rds_btn.setToolTip(tr("monitor_radio_wfm_rds_tip"))
            self._rds_btn.setIcon(make_rds_icon(self))
        if self._bw_btn is not None:
            self._bw_btn.setToolTip(tr("monitor_radio_show_demod_bw_tip"))
            self._bw_btn.setIcon(make_demod_bw_icon(self))
        if self._lowpass_btn is not None:
            self._lowpass_btn.setToolTip(tr("monitor_radio_wfm_lowpass_tip"))
            self._lowpass_btn.setIcon(make_lowpass_icon(self))
        if self._iq_corr_btn is not None:
            self._iq_corr_btn.setToolTip(tr("monitor_radio_iq_correction_tip"))
            self._iq_corr_btn.setIcon(make_iq_correction_icon(self))
        if self._iq_inv_btn is not None:
            self._iq_inv_btn.setToolTip(tr("monitor_radio_iq_invert_tip"))
            self._iq_inv_btn.setIcon(make_iq_invert_icon(self))
        if self._info is not None:
            self._info.recargar_textos()
