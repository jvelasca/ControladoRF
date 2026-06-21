"""Resumen de supervisión en la barra de estado principal de la aplicación.

Integrado en ``AppStatusBarPanel`` entre la ruta del proyecto y el workspace activo.

Emite señales conectadas al ``MonitorController`` (alarmas, REC, configuración, último log).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QStyle, QToolButton, QWidget

from core.monitor.supervision.supervision_models import AlarmSummaryCounts
from gui.monitor.monitor_supervision_icons import make_gear_icon, make_record_icon, toolbar_icon_color
from i18n.json_translation import tr

if TYPE_CHECKING:
    from core.monitor.supervision.supervision_log_session import SupervisionLogSessionRecord

_DOT_PX = 10
_REC_BTN_SIZE = QSize(22, 20)
_ICON_SIZE = QSize(14, 14)


def _status_separator(parent: QWidget) -> QFrame:
    sep = QFrame(parent)
    sep.setObjectName("StatusBarSeparator")
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setFrameShadow(QFrame.Shadow.Plain)
    sep.setFixedWidth(1)
    sep.setMinimumHeight(14)
    sep.setMaximumHeight(18)
    return sep


class _AlarmCountBadge(QWidget):
    """Círculo de color compacto + contador entre paréntesis al lado."""

    clicked = pyqtSignal()

    def __init__(self, tone: str, tip_key: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._tone = tone
        self._count = 0
        self.setToolTip(tr(tip_key))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 2, 0)
        row.setSpacing(2)
        self._dot = QLabel(self)
        self._dot.setFixedSize(_DOT_PX, _DOT_PX)
        self._dot.setObjectName(f"SupervisionStatusDot{tone.title()}")
        self._count_label = QLabel(self)
        self._count_label.setObjectName("SupervisionStatusBadgeCount")
        self._count_label.setStyleSheet("font-size: 10px; padding: 0px; margin: 0px;")
        row.addWidget(self._dot)
        row.addWidget(self._count_label)
        self._apply_dot_style()
        self.set_count(0)

    def set_count(self, count: int) -> None:
        self._count = max(0, int(count))
        text = str(self._count) if self._count <= 999 else "999+"
        self._count_label.setText(f"({text})")

    def _apply_dot_style(self) -> None:
        colors = {
            "green": "#16a34a",
            "yellow": "#ea580c",
            "red": "#dc2626",
        }
        bg = colors.get(self._tone, "#64748b")
        radius = _DOT_PX // 2
        self._dot.setStyleSheet(
            f"""
            QLabel#SupervisionStatusDot{self._tone.title()} {{
                background-color: {bg};
                border-radius: {radius}px;
                min-width: {_DOT_PX}px;
                max-width: {_DOT_PX}px;
                min-height: {_DOT_PX}px;
                max-height: {_DOT_PX}px;
            }}
            """
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class SupervisionStatusBarWidget(QWidget):
    """Alarmas (izq) | registro REC (dcha) dentro del bloque de supervisión."""

    alarms_requested = pyqtSignal()
    rec_toggle_requested = pyqtSignal()
    log_settings_requested = pyqtSignal()
    last_log_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SupervisionStatusBarWidget")
        self._rec_active = False
        self._rec_blink_on = False
        self._rec_blink_timer = QTimer(self)
        self._rec_blink_timer.setInterval(500)
        self._rec_blink_timer.timeout.connect(self._on_rec_blink)
        self._build_ui()
        self.setVisible(False)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._alarms_group = QWidget(self)
        self._alarms_group.setObjectName("SupervisionStatusAlarmsGroup")
        alarms_layout = QHBoxLayout(self._alarms_group)
        alarms_layout.setContentsMargins(0, 0, 0, 0)
        alarms_layout.setSpacing(6)

        self._green_badge = _AlarmCountBadge("green", "monitor_status_supervision_ok")
        self._yellow_badge = _AlarmCountBadge("yellow", "monitor_status_supervision_warning")
        self._red_badge = _AlarmCountBadge("red", "monitor_status_supervision_critical")
        for badge in (self._green_badge, self._yellow_badge, self._red_badge):
            badge.clicked.connect(self.alarms_requested.emit)
            alarms_layout.addWidget(badge)

        layout.addWidget(self._alarms_group)
        layout.addWidget(_status_separator(self))

        self._log_group = QWidget(self)
        self._log_group.setObjectName("SupervisionStatusLogGroup")
        log_layout = QHBoxLayout(self._log_group)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(4)

        self._rec_btn = QToolButton(self)
        self._rec_btn.setObjectName("MonitorSupervisionRecBtn")
        self._rec_btn.setCheckable(True)
        self._rec_btn.setIconSize(_ICON_SIZE)
        self._rec_btn.setFixedSize(_REC_BTN_SIZE)
        self._rec_btn.setToolTip(tr("monitor_alarmas_rec_toggle"))
        self._rec_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._rec_btn.setAutoRaise(True)
        self._rec_btn.clicked.connect(self.rec_toggle_requested.emit)
        self._update_rec_icon()
        log_layout.addWidget(self._rec_btn)

        self._clock_label = QLabel(tr("monitor_alarmas_rec_clock_idle"))
        self._clock_label.setObjectName("SupervisionStatusRecClock")
        self._clock_label.setToolTip(tr("monitor_alarmas_rec_clock_tip"))
        log_layout.addWidget(self._clock_label)

        log_layout.addWidget(_status_separator(self))

        self._last_log_btn = QToolButton(self)
        self._last_log_btn.setObjectName("MonitorSupervisionToolBtn")
        style = self.style()
        if style is not None:
            self._last_log_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self._last_log_btn.setIconSize(_ICON_SIZE)
        self._last_log_btn.setFixedSize(_REC_BTN_SIZE)
        self._last_log_btn.setToolTip(tr("monitor_alarmas_open_last_log"))
        self._last_log_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._last_log_btn.setAutoRaise(True)
        self._last_log_btn.clicked.connect(self.last_log_requested.emit)
        log_layout.addWidget(self._last_log_btn)

        self._settings_btn = QToolButton(self)
        self._settings_btn.setObjectName("MonitorSupervisionToolBtn")
        self._settings_btn.setIcon(make_gear_icon(_ICON_SIZE.width(), toolbar_icon_color(self)))
        self._settings_btn.setIconSize(_ICON_SIZE)
        self._settings_btn.setFixedSize(_REC_BTN_SIZE)
        self._settings_btn.setToolTip(tr("monitor_alarmas_tool_log_settings"))
        self._settings_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._settings_btn.setAutoRaise(True)
        self._settings_btn.clicked.connect(self.log_settings_requested.emit)
        log_layout.addWidget(self._settings_btn)

        layout.addWidget(self._log_group)

    def set_supervision_active(self, active: bool) -> None:
        self.setVisible(bool(active))

    def set_alarm_counts(self, counts: AlarmSummaryCounts | None) -> None:
        if counts is None:
            self._green_badge.set_count(0)
            self._yellow_badge.set_count(0)
            self._red_badge.set_count(0)
            return
        self._green_badge.set_count(counts.ok)
        self._yellow_badge.set_count(counts.warning_active + counts.warning_latched)
        self._red_badge.set_count(counts.critical_active + counts.critical_latched)

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
        has_last = last is not None and last.directory.exists()
        self._last_log_btn.setEnabled(has_last or (active_session is not None))

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
        active_session: Optional[SupervisionLogSessionRecord],
    ) -> str:
        if active and active_session is not None:
            return tr("monitor_status_rec_active").format(
                start=self._format_iso_short(active_session.started_at_utc),
                elapsed=self._format_hms(elapsed_s),
            )
        if last is not None and last.ended_at_utc:
            return tr("monitor_alarmas_rec_clock_last").format(
                start=self._format_iso_short(last.started_at_utc),
                end=self._format_iso_short(last.ended_at_utc),
                duration=self._format_hms(last.duration_s),
            )
        return tr("monitor_alarmas_rec_clock_idle")

    def recargar_textos(self) -> None:
        self._green_badge.setToolTip(tr("monitor_status_supervision_ok"))
        self._yellow_badge.setToolTip(tr("monitor_status_supervision_warning"))
        self._red_badge.setToolTip(tr("monitor_status_supervision_critical"))
        self._rec_btn.setToolTip(tr("monitor_alarmas_rec_toggle"))
        self._clock_label.setToolTip(tr("monitor_alarmas_rec_clock_tip"))
        self._last_log_btn.setToolTip(tr("monitor_alarmas_open_last_log"))
        self._settings_btn.setIcon(make_gear_icon(_ICON_SIZE.width(), toolbar_icon_color(self)))
        self._settings_btn.setToolTip(tr("monitor_alarmas_tool_log_settings"))
