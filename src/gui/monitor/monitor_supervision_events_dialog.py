"""Visor de histórico de eventos de supervisión."""
from __future__ import annotations

from typing import Callable, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.monitor.supervision.alarm_log_repository import AlarmLogEntry
from gui.configurable_table_header import setup_resizable_header
from gui.dialog_styles import apply_professional_dialog_style, build_dialog_header
from i18n.json_translation import tr


class MonitorSupervisionEventsDialog(QDialog):
    """Tabla filtrable de eventos (SQLite + CSV de sesión)."""

    _COL_TIME = 0
    _COL_TYPE = 1
    _COL_CHANNEL = 2
    _COL_FREQ = 3
    _COL_SEVERITY = 4
    _COL_PHASE = 5
    _COL_SNR = 6
    _COL_DETAIL = 7

    def __init__(
        self,
        *,
        query_entries: Callable[[str, str], List[AlarmLogEntry]],
        export_csv: Callable[[str, List[AlarmLogEntry]], tuple[bool, str]],
        export_txt: Callable[[str, List[AlarmLogEntry]], tuple[bool, str]],
        log_path: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._query_entries = query_entries
        self._export_csv = export_csv
        self._export_txt = export_txt
        self._log_path = log_path
        self._entries: List[AlarmLogEntry] = []
        self.setWindowTitle(tr("monitor_supervision_events_title"))
        apply_professional_dialog_style(self)
        self.resize(920, 520)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(
            build_dialog_header(
                tr("monitor_supervision_events_title"),
                tr("monitor_supervision_events_intro"),
            )
        )

        self._log_label = QLabel()
        self._log_label.setWordWrap(True)
        self._log_label.setVisible(bool(self._log_path))
        if self._log_path:
            self._log_label.setText(tr("monitor_supervision_log_path").format(path=self._log_path))
        layout.addWidget(self._log_label)

        filters = QHBoxLayout()
        filters.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("monitor_supervision_events_filter_search"))
        self._search.textChanged.connect(self._apply_filters)

        self._severity = QComboBox()
        self._severity.addItem(tr("monitor_supervision_events_filter_all_severity"), "")
        self._severity.addItem(tr("monitor_supervision_state_warning"), "warning")
        self._severity.addItem(tr("monitor_supervision_state_critical"), "critical")
        self._severity.currentIndexChanged.connect(self.refresh)

        self._phase = QComboBox()
        self._phase.addItem(tr("monitor_supervision_events_filter_all_phase"), "")
        self._phase.addItem(tr("monitor_supervision_events_phase_raised"), "raised")
        self._phase.addItem(tr("monitor_supervision_events_phase_latched"), "latched")
        self._phase.addItem(tr("monitor_supervision_events_phase_cleared"), "cleared")
        self._phase.addItem(tr("monitor_supervision_state_acked"), "acked")
        self._phase.currentIndexChanged.connect(self.refresh)

        self._refresh_btn = QPushButton(tr("monitor_supervision_events_refresh"))
        self._refresh_btn.clicked.connect(self.refresh)

        self._export_csv_btn = QPushButton(tr("monitor_supervision_events_export_csv"))
        self._export_csv_btn.clicked.connect(lambda: self._on_export("csv"))

        self._export_txt_btn = QPushButton(tr("monitor_supervision_events_export_txt"))
        self._export_txt_btn.clicked.connect(lambda: self._on_export("txt"))

        filters.addWidget(self._search, stretch=2)
        filters.addWidget(self._severity)
        filters.addWidget(self._phase)
        filters.addWidget(self._refresh_btn)
        filters.addWidget(self._export_csv_btn)
        filters.addWidget(self._export_txt_btn)
        layout.addLayout(filters)

        self._summary = QLabel()
        layout.addWidget(self._summary)

        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels(
            [
                tr("monitor_supervision_events_col_time"),
                tr("monitor_supervision_events_col_type"),
                tr("monitor_supervision_col_channel"),
                tr("monitor_supervision_col_freq"),
                tr("monitor_supervision_col_state"),
                tr("monitor_supervision_events_col_phase"),
                tr("monitor_supervision_col_snr"),
                tr("monitor_supervision_col_detail"),
            ]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        setup_resizable_header(self._table.horizontalHeader(), 8)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def refresh(self) -> None:
        severity = str(self._severity.currentData() or "")
        phase = str(self._phase.currentData() or "")
        self._entries = self._query_entries(severity, phase)
        self._apply_filters()

    def _apply_filters(self) -> None:
        needle = self._search.text().strip().casefold()
        rows = self._entries
        if needle:
            rows = [
                entry
                for entry in rows
                if needle in entry.label.casefold()
                or needle in entry.channel_key.casefold()
                or needle in entry.message.casefold()
            ]
        self._populate_table(rows)
        self._summary.setText(
            tr("monitor_supervision_events_summary").format(
                shown=len(rows),
                total=len(self._entries),
            )
        )

    def _populate_table(self, rows: List[AlarmLogEntry]) -> None:
        from core.monitor.supervision.alarm_catalog import alarm_type_label

        self._table.setRowCount(len(rows))
        for row_index, entry in enumerate(rows):
            values = (
                entry.timestamp_utc.replace("T", " "),
                alarm_type_label(entry.alarm_type, tr),
                entry.label or entry.channel_key,
                self._format_freq(entry.frequency_mhz),
                self._format_severity(entry.severity),
                self._format_phase(entry.phase),
                self._format_optional(entry.snr_db, suffix=" dB"),
                entry.message or entry.rule,
            )
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if col in (self._COL_FREQ, self._COL_SNR):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._table.setItem(row_index, col, item)

    def _on_export(self, fmt: str) -> None:
        from core.monitor.monitor_export_paths import (
            EXPORT_ALARM_CSV,
            EXPORT_ALARM_TXT,
            resolve_save_path,
        )

        visible_rows = self._visible_entries()
        if fmt == "txt":
            default_path = resolve_save_path(EXPORT_ALARM_TXT, "supervision_alarm_report.txt")
            path, _filter = QFileDialog.getSaveFileName(
                self,
                tr("monitor_supervision_events_export_txt"),
                default_path,
                tr("monitor_export_filter_txt"),
            )
            if not path:
                return
            ok, message = self._export_txt(path, visible_rows)
            if ok:
                from core.monitor.monitor_export_paths import remember_save_path

                remember_save_path(EXPORT_ALARM_TXT, path)
        else:
            default_path = resolve_save_path(EXPORT_ALARM_CSV, "supervision_events_export.csv")
            path, _filter = QFileDialog.getSaveFileName(
                self,
                tr("monitor_supervision_events_export_csv"),
                default_path,
                tr("monitor_export_filter_csv"),
            )
            if not path:
                return
            ok, message = self._export_csv(path, visible_rows)
            if ok:
                from core.monitor.monitor_export_paths import remember_save_path

                remember_save_path(EXPORT_ALARM_CSV, path)
        if ok:
            QMessageBox.information(
                self,
                tr("monitor_supervision_events_export_title"),
                message,
            )
        else:
            QMessageBox.warning(
                self,
                tr("monitor_supervision_events_export_title"),
                message,
            )

    def _visible_entries(self) -> List[AlarmLogEntry]:
        needle = self._search.text().strip().casefold()
        rows = self._entries
        if not needle:
            return list(rows)
        return [
            entry
            for entry in rows
            if needle in entry.label.casefold()
            or needle in entry.channel_key.casefold()
            or needle in entry.message.casefold()
        ]

    @staticmethod
    def _format_freq(value) -> str:
        if value is None:
            return ""
        try:
            return f"{float(value):.3f}"
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _format_optional(value, *, suffix: str = "") -> str:
        if value is None:
            return ""
        try:
            return f"{float(value):.1f}{suffix}"
        except (TypeError, ValueError):
            return str(value)

    def _format_severity(self, severity: str) -> str:
        mapping = {
            "warning": tr("monitor_supervision_state_warning"),
            "critical": tr("monitor_supervision_state_critical"),
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
