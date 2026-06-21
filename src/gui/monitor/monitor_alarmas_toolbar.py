"""Barra de iconos compartida del panel ALARMAS y ventana flotante.

Controles: ventana flotante, umbrales, agrupación, localizar, REC, reloj,
configuración de logs y abrir último registro. La ayuda (i) usa ``monitor_alarmas_intro``.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QStyle, QToolButton, QWidget

from gui.monitor.monitor_info_button import MonitorInfoButton
from gui.monitor.monitor_shortcuts import MONITOR_SHORTCUTS
from gui.monitor.monitor_supervision_icons import make_gear_icon, make_record_icon, toolbar_icon_color
from gui.shortcut_tooltips import tooltip_with_shortcut
from i18n.json_translation import tr

if TYPE_CHECKING:
    from core.monitor.supervision.supervision_log_session import SupervisionLogSessionRecord
    from gui.monitor.monitor_supervision_tree_widget import MonitorSupervisionTreeWidget

_TOOL_BTN_SIZE = QSize(22, 20)
_TOOL_ICON_SIZE = QSize(14, 14)


class MonitorAlarmasToolbarWidget(QWidget):
    popout_requested = pyqtSignal()
    thresholds_requested = pyqtSignal()
    rec_toggle_requested = pyqtSignal()
    log_settings_requested = pyqtSignal()
    last_log_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._tree: MonitorSupervisionTreeWidget | None = None
        self._rec_active = False
        self._rec_blink_on = False
        self._rec_blink_timer = QTimer(self)
        self._rec_blink_timer.setInterval(500)
        self._rec_blink_timer.timeout.connect(self._on_rec_blink)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._popout_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_TitleBarNormalButton,
            "monitor_alarmas_tool_popout",
            shortcut=MONITOR_SHORTCUTS["supervision_tree"],
        )
        self._popout_btn.clicked.connect(self.popout_requested.emit)

        self._thresholds_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "monitor_alarmas_tool_thresholds",
            shortcut=MONITOR_SHORTCUTS["thresholds"],
        )
        self._thresholds_btn.clicked.connect(self.thresholds_requested.emit)

        self._group_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_FileDialogListView,
            "monitor_supervision_tool_group",
        )

        self._locate_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_ArrowRight,
            "monitor_supervision_tool_locate",
            shortcut=MONITOR_SHORTCUTS["locate"],
        )

        for btn in (
            self._popout_btn,
            self._thresholds_btn,
            self._group_btn,
            self._locate_btn,
        ):
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addSpacing(6)

        self._rec_btn = QToolButton(self)
        self._rec_btn.setObjectName("MonitorSupervisionRecBtn")
        self._rec_btn.setCheckable(True)
        self._rec_btn.setIconSize(_TOOL_ICON_SIZE)
        self._rec_btn.setFixedSize(_TOOL_BTN_SIZE)
        self._rec_btn.setToolTip(tr("monitor_alarmas_rec_toggle"))
        self._rec_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._rec_btn.setAutoRaise(True)
        self._rec_btn.clicked.connect(self.rec_toggle_requested.emit)
        self._update_rec_icon()
        layout.addWidget(self._rec_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._clock_label = QLabel("—")
        self._clock_label.setObjectName("MonitorSupervisionRecClock")
        self._clock_label.setToolTip(tr("monitor_alarmas_rec_clock_tip"))
        layout.addWidget(self._clock_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._settings_btn = self._make_gear_tool_button("monitor_alarmas_tool_log_settings")
        self._settings_btn.clicked.connect(self.log_settings_requested.emit)
        layout.addWidget(self._settings_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._last_log_btn = self._make_tool_button(
            QStyle.StandardPixmap.SP_DialogOpenButton,
            "monitor_alarmas_open_last_log",
        )
        self._last_log_btn.clicked.connect(self.last_log_requested.emit)
        layout.addWidget(self._last_log_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch(1)

        self._info = MonitorInfoButton(
            title_key="monitor_cfg_alarmas",
            body_key="monitor_alarmas_intro",
        )
        layout.addWidget(self._info, alignment=Qt.AlignmentFlag.AlignVCenter)

        from gui.app_chrome_styles import apply_monitor_freq_manager_styles

        apply_monitor_freq_manager_styles(self)

    def bind_supervision_tree(self, tree: MonitorSupervisionTreeWidget) -> None:
        self._tree = tree
        self._group_btn.clicked.connect(lambda: tree.show_group_menu(self._group_btn))
        self._locate_btn.clicked.connect(tree.trigger_locate_selected)

    def set_rec_status(
        self,
        *,
        active: bool,
        elapsed_s: int = 0,
        last: Optional[SupervisionLogSessionRecord] = None,
        active_session: Optional[SupervisionLogSessionRecord] = None,
    ) -> None:
        self._rec_active = bool(active)
        self._rec_btn.blockSignals(True)
        self._rec_btn.setChecked(self._rec_active)
        self._rec_btn.blockSignals(False)
        if self._rec_active:
            self._rec_blink_timer.start()
            self._update_rec_icon()
        else:
            self._rec_blink_on = False
            self._rec_blink_timer.stop()
            self._update_rec_icon()
        self._clock_label.setText(
            self._format_clock(active, elapsed_s, last, active_session)
        )
        has_log = last is not None or self._rec_active
        if hasattr(self, "_last_log_btn"):
            self._last_log_btn.setEnabled(has_log)

    def _update_rec_icon(self) -> None:
        bright = not self._rec_active or self._rec_blink_on
        self._rec_btn.setIcon(make_record_icon(bright=bright))

    def _on_rec_blink(self) -> None:
        if not self._rec_active:
            return
        self._rec_blink_on = not self._rec_blink_on
        self._update_rec_icon()

    @staticmethod
    def _format_hms(total_seconds: int) -> str:
        seconds = max(0, int(total_seconds))
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    @staticmethod
    def _format_iso_short(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return "—"
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.strftime("%H:%M:%S")
        except ValueError:
            return text[:8] if len(text) >= 8 else text

    def _format_clock(
        self,
        active: bool,
        elapsed_s: int,
        last: Optional[SupervisionLogSessionRecord],
        active_session: Optional[SupervisionLogSessionRecord] = None,
    ) -> str:
        if active and active_session is not None:
            return tr("monitor_status_rec_active").format(
                start=self._format_iso_short(active_session.started_at_utc),
                elapsed=self._format_hms(elapsed_s),
            )
        if active:
            return tr("monitor_alarmas_rec_clock_active").format(
                elapsed=self._format_hms(elapsed_s)
            )
        if last is not None and last.ended_at_utc:
            return tr("monitor_alarmas_rec_clock_last").format(
                start=self._format_iso_short(last.started_at_utc),
                end=self._format_iso_short(last.ended_at_utc),
                duration=self._format_hms(last.duration_s),
            )
        return tr("monitor_alarmas_rec_clock_idle")

    def _make_tool_button(
        self,
        icon: QStyle.StandardPixmap,
        tip_key: str,
        *,
        shortcut: str = "",
    ) -> QToolButton:
        btn = QToolButton(self)
        btn.setObjectName("MonitorSupervisionToolBtn")
        style = self.style()
        if style is not None:
            btn.setIcon(style.standardIcon(icon))
        btn.setIconSize(_TOOL_ICON_SIZE)
        btn.setFixedSize(_TOOL_BTN_SIZE)
        btn.setToolTip(
            tooltip_with_shortcut(tr(tip_key), shortcut) if shortcut else tr(tip_key)
        )
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setAutoRaise(True)
        return btn

    def _make_gear_tool_button(self, tip_key: str) -> QToolButton:
        btn = QToolButton(self)
        btn.setObjectName("MonitorSupervisionToolBtn")
        btn.setIcon(make_gear_icon(_TOOL_ICON_SIZE.width(), toolbar_icon_color(self)))
        btn.setIconSize(_TOOL_ICON_SIZE)
        btn.setFixedSize(_TOOL_BTN_SIZE)
        btn.setToolTip(tr(tip_key))
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setAutoRaise(True)
        return btn

    def recargar_textos(self) -> None:
        self._popout_btn.setToolTip(
            tooltip_with_shortcut(
                tr("monitor_alarmas_tool_popout"),
                MONITOR_SHORTCUTS["supervision_tree"],
            )
        )
        self._thresholds_btn.setToolTip(
            tooltip_with_shortcut(
                tr("monitor_alarmas_tool_thresholds"),
                MONITOR_SHORTCUTS["thresholds"],
            )
        )
        self._group_btn.setToolTip(tr("monitor_supervision_tool_group"))
        self._locate_btn.setToolTip(
            tooltip_with_shortcut(
                tr("monitor_supervision_tool_locate"),
                MONITOR_SHORTCUTS["locate"],
            )
        )
        self._rec_btn.setToolTip(tr("monitor_alarmas_rec_toggle"))
        self._clock_label.setToolTip(tr("monitor_alarmas_rec_clock_tip"))
        self._settings_btn.setIcon(
            make_gear_icon(_TOOL_ICON_SIZE.width(), toolbar_icon_color(self))
        )
        self._settings_btn.setToolTip(tr("monitor_alarmas_tool_log_settings"))
        self._last_log_btn.setToolTip(tr("monitor_alarmas_open_last_log"))
        self._info.recargar_textos()
