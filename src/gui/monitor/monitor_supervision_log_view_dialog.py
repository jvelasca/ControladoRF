"""Visor del log CSV de la sesión de supervisión."""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.monitor.supervision.alarm_log_repository import AlarmLogEntry
from gui.configurable_table_header import setup_resizable_header
from gui.dialog_styles import apply_professional_dialog_style, build_dialog_header
from i18n.json_translation import tr


class MonitorSupervisionLogViewDialog(QDialog):
    """Muestra entradas del log CSV activo (desde el inicio del registro)."""

    _COL_TIME = 0
    _COL_TYPE = 1
    _COL_CHANNEL = 2
    _COL_FREQ = 3
    _COL_SEVERITY = 4
    _COL_PHASE = 5
    _COL_DETAIL = 6

    def __init__(
        self,
        entries: List[AlarmLogEntry],
        *,
        log_path: str = "",
        scope_title: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._entries = list(entries or [])
        self._log_path = log_path
        self._scope_title = scope_title.strip()
        self.setWindowTitle(tr("monitor_supervision_log_view_title"))
        apply_professional_dialog_style(self)
        self.resize(860, 480)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        subtitle = tr("monitor_supervision_log_view_intro")
        if self._scope_title:
            subtitle = tr("monitor_supervision_log_view_intro_scope").format(scope=self._scope_title)
        layout.addWidget(
            build_dialog_header(tr("monitor_supervision_log_view_title"), subtitle)
        )

        if self._log_path:
            path_label = QLabel(tr("monitor_supervision_log_path").format(path=self._log_path))
            path_label.setWordWrap(True)
            layout.addWidget(path_label)

        self._summary = QLabel()
        layout.addWidget(self._summary)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            [
                tr("monitor_supervision_events_col_time"),
                tr("monitor_supervision_events_col_type"),
                tr("monitor_supervision_col_channel"),
                tr("monitor_supervision_col_freq"),
                tr("monitor_supervision_col_state"),
                tr("monitor_supervision_events_col_phase"),
                tr("monitor_supervision_col_detail"),
            ]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        setup_resizable_header(self._table.horizontalHeader(), 7)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate_table()

    def _populate_table(self) -> None:
        from core.monitor.supervision.alarm_catalog import alarm_type_label

        rows = self._entries
        self._table.setRowCount(len(rows))
        for row_index, entry in enumerate(rows):
            values = (
                entry.timestamp_utc.replace("T", " "),
                alarm_type_label(entry.alarm_type, tr),
                entry.label or entry.channel_key,
                self._format_freq(entry.frequency_mhz),
                self._format_severity(entry.severity),
                self._format_phase(entry.phase),
                entry.message or entry.rule,
            )
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if col in (self._COL_FREQ,):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._table.setItem(row_index, col, item)

        if rows:
            summary = tr("monitor_supervision_log_view_summary").format(count=len(rows))
        else:
            summary = tr("monitor_supervision_log_view_empty")
        self._summary.setText(summary)

    @staticmethod
    def _format_freq(value) -> str:
        if value is None:
            return ""
        try:
            return f"{float(value):.3f}"
        except (TypeError, ValueError):
            return str(value)

    def _format_severity(self, severity: str) -> str:
        mapping = {
            "warning": tr("monitor_supervision_state_warning"),
            "critical": tr("monitor_supervision_state_critical"),
            "critica": tr("monitor_severity_critica"),
            "menor": tr("monitor_severity_menor"),
            "aviso": tr("monitor_severity_aviso"),
            "comentario": tr("monitor_severity_comentario"),
        }
        return mapping.get(severity, severity)

    def _format_phase(self, phase: str) -> str:
        mapping = {
            "raised": tr("monitor_supervision_events_phase_raised"),
            "latched": tr("monitor_supervision_events_phase_latched"),
            "cleared": tr("monitor_supervision_events_phase_cleared"),
            "acked": tr("monitor_supervision_state_acked"),
        }
        return mapping.get(phase, phase)
