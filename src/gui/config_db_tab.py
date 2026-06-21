"""
config_db_tab.py
----------------
Pestaña de base de datos con dos niveles:
- Usuario: estado y resumen de registros.
- Desarrollador: configuración, mantenimiento, explorador y consola SQL.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from db import DatabaseService, DatabaseSettings, JOURNAL_MODES, SYNCHRONOUS_MODES, format_file_size
from db.exceptions import DatabaseError
from i18n.json_translation import tr
from utils.theme_utils import is_dark_mode


class DatabaseConfigTab(QWidget):
    """Estado resumido (todos) y herramientas completas (modo desarrollador)."""

    def __init__(
        self,
        db_service: Optional[DatabaseService],
        *,
        developer_mode: bool = False,
        get_config: Optional[Callable[[], Dict]] = None,
        set_config: Optional[Callable[[Dict], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._db_service = db_service
        self._developer_mode = developer_mode
        self._get_config = get_config
        self._set_config = set_config
        self._loading = False
        self._setup_ui()
        self.set_developer_mode(developer_mode)
        self.recargar_textos()

    def set_developer_mode(self, enabled: bool) -> None:
        self._developer_mode = enabled
        self._developer_panel.setVisible(enabled)
        self._user_intro.setVisible(not enabled)
        self._dev_intro.setVisible(enabled)
        if self._developer_lock is not None:
            self._developer_lock.sync_from_config()
        self.recargar_textos()

    def _on_developer_lock_changed(self, unlocked: bool) -> None:
        self.set_developer_mode(bool(unlocked))

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        self._user_intro = QLabel()
        self._user_intro.setWordWrap(True)
        layout.addWidget(self._user_intro)

        self._dev_intro = QLabel()
        self._dev_intro.setWordWrap(True)
        layout.addWidget(self._dev_intro)

        self._summary_group = QGroupBox()
        summary_layout = QVBoxLayout(self._summary_group)
        summary_header = QHBoxLayout()
        summary_header.addStretch(1)
        self._developer_lock: Optional[DeveloperLockButton] = None
        if self._get_config is not None and self._set_config is not None:
            self._developer_lock = DeveloperLockButton(
                get_config=self._get_config,
                set_config=self._set_config,
                parent=self,
            )
            self._developer_lock.unlocked_changed.connect(self._on_developer_lock_changed)
            summary_header.addWidget(self._developer_lock, alignment=Qt.AlignmentFlag.AlignVCenter)
        summary_layout.addLayout(summary_header)
        self._summary_connected = QLabel()
        self._summary_path = QLabel()
        self._summary_size = QLabel()
        self._summary_records = QLabel()
        self._summary_tables = QLabel()
        for label in (
            self._summary_connected,
            self._summary_path,
            self._summary_size,
            self._summary_records,
            self._summary_tables,
        ):
            label.setWordWrap(True)
            summary_layout.addWidget(label)
        self._refresh_summary_btn = QPushButton()
        self._refresh_summary_btn.clicked.connect(self.refresh_status)
        summary_layout.addWidget(self._refresh_summary_btn)
        layout.addWidget(self._summary_group)

        self._developer_panel = QWidget()
        dev_layout = QVBoxLayout(self._developer_panel)
        dev_layout.setContentsMargins(0, 0, 0, 0)

        self._connection_group = QGroupBox()
        conn_layout = QGridLayout(self._connection_group)
        self._filename_label = QLabel()
        self._filename_edit = QLineEdit()
        self._path_label = QLabel()
        self._path_value = QLineEdit()
        self._path_value.setReadOnly(True)
        self._timeout_label = QLabel()
        self._timeout_spin = QDoubleSpinBox()
        self._timeout_spin.setRange(1.0, 300.0)
        self._timeout_spin.setDecimals(1)
        self._timeout_spin.setSingleStep(1.0)
        self._open_folder_btn = QPushButton()
        self._open_folder_btn.clicked.connect(self._open_database_folder)
        conn_layout.addWidget(self._filename_label, 0, 0)
        conn_layout.addWidget(self._filename_edit, 0, 1)
        conn_layout.addWidget(self._path_label, 1, 0)
        conn_layout.addWidget(self._path_value, 1, 1)
        conn_layout.addWidget(self._open_folder_btn, 2, 0, 1, 2)
        conn_layout.addWidget(self._timeout_label, 3, 0)
        conn_layout.addWidget(self._timeout_spin, 3, 1)
        dev_layout.addWidget(self._connection_group)

        self._pragmas_group = QGroupBox()
        pragma_layout = QGridLayout(self._pragmas_group)
        self._journal_label = QLabel()
        self._journal_combo = QComboBox()
        for mode in JOURNAL_MODES:
            self._journal_combo.addItem(mode, mode)
        self._foreign_keys = QCheckBox()
        self._sync_label = QLabel()
        self._sync_combo = QComboBox()
        for mode in SYNCHRONOUS_MODES:
            self._sync_combo.addItem(mode, mode)
        self._status_migrations = QLabel()
        self._status_pragmas = QLabel()
        self._status_migrations.setWordWrap(True)
        self._status_pragmas.setWordWrap(True)
        pragma_layout.addWidget(self._journal_label, 0, 0)
        pragma_layout.addWidget(self._journal_combo, 0, 1)
        pragma_layout.addWidget(self._foreign_keys, 1, 0, 1, 2)
        pragma_layout.addWidget(self._sync_label, 2, 0)
        pragma_layout.addWidget(self._sync_combo, 2, 1)
        pragma_layout.addWidget(self._status_migrations, 3, 0, 1, 2)
        pragma_layout.addWidget(self._status_pragmas, 4, 0, 1, 2)
        dev_layout.addWidget(self._pragmas_group)

        self._backup_group = QGroupBox()
        backup_layout = QGridLayout(self._backup_group)
        self._backup_dir_label = QLabel()
        self._backup_dir_edit = QLineEdit()
        self._backup_browse_btn = QPushButton()
        self._backup_browse_btn.clicked.connect(self._browse_backup_dir)
        self._auto_backup = QCheckBox()
        backup_row = QHBoxLayout()
        backup_row.addWidget(self._backup_dir_edit, stretch=1)
        backup_row.addWidget(self._backup_browse_btn)
        backup_layout.addWidget(self._backup_dir_label, 0, 0)
        backup_layout.addLayout(backup_row, 0, 1)
        backup_layout.addWidget(self._auto_backup, 1, 0, 1, 2)
        dev_layout.addWidget(self._backup_group)

        self._explorer_group = QGroupBox()
        explorer_layout = QVBoxLayout(self._explorer_group)
        explorer_toolbar = QHBoxLayout()
        self._table_combo = QComboBox()
        self._table_combo.currentIndexChanged.connect(self._load_table_preview)
        self._preview_refresh_btn = QPushButton()
        self._preview_refresh_btn.clicked.connect(self._load_table_preview)
        explorer_toolbar.addWidget(self._table_combo, stretch=1)
        explorer_toolbar.addWidget(self._preview_refresh_btn)
        explorer_layout.addLayout(explorer_toolbar)
        self._preview_table = QTableWidget(0, 0)
        self._preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._preview_table.horizontalHeader().setStretchLastSection(True)
        self._preview_table.setAlternatingRowColors(True)
        explorer_layout.addWidget(self._preview_table)
        dev_layout.addWidget(self._explorer_group)

        self._sql_group = QGroupBox()
        sql_layout = QVBoxLayout(self._sql_group)
        sql_input_row = QHBoxLayout()
        self._sql_input = QLineEdit()
        self._sql_input.setPlaceholderText("SELECT * FROM inventory_channels LIMIT 10")
        self._sql_input.returnPressed.connect(self._on_execute_sql)
        self._sql_execute_btn = QPushButton()
        self._sql_execute_btn.clicked.connect(self._on_execute_sql)
        sql_input_row.addWidget(self._sql_input, stretch=1)
        sql_input_row.addWidget(self._sql_execute_btn)
        sql_layout.addLayout(sql_input_row)
        self._sql_result = QTextEdit()
        self._sql_result.setReadOnly(True)
        self._sql_result.setMaximumHeight(120)
        sql_layout.addWidget(self._sql_result)
        dev_layout.addWidget(self._sql_group)

        self._maintenance_group = QGroupBox()
        maint_layout = QGridLayout(self._maintenance_group)
        self._btn_integrity = QPushButton()
        self._btn_integrity.clicked.connect(self._on_integrity)
        self._btn_vacuum = QPushButton()
        self._btn_vacuum.clicked.connect(self._on_vacuum)
        self._btn_analyze = QPushButton()
        self._btn_analyze.clicked.connect(self._on_analyze)
        self._btn_backup = QPushButton()
        self._btn_backup.clicked.connect(self._on_backup)
        self._btn_migrations = QPushButton()
        self._btn_migrations.clicked.connect(self._on_migrations)
        self._btn_reconnect = QPushButton()
        self._btn_reconnect.clicked.connect(self._on_reconnect)
        self._btn_apply = QPushButton()
        self._btn_apply.clicked.connect(self._on_apply_settings)
        buttons = [
            self._btn_integrity,
            self._btn_vacuum,
            self._btn_analyze,
            self._btn_backup,
            self._btn_migrations,
            self._btn_reconnect,
        ]
        for index, btn in enumerate(buttons):
            maint_layout.addWidget(btn, index // 2, index % 2)
        maint_layout.addWidget(self._btn_apply, 3, 0, 1, 2)
        dev_layout.addWidget(self._maintenance_group)

        layout.addWidget(self._developer_panel)

        self._message_label = QLabel()
        self._message_label.setWordWrap(True)
        layout.addWidget(self._message_label)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._load_values()
        self._set_service_enabled(self._db_service is not None)
        self.refresh_status()

    def _set_service_enabled(self, enabled: bool) -> None:
        self._refresh_summary_btn.setEnabled(enabled)
        for widget in (
            self._filename_edit,
            self._timeout_spin,
            self._journal_combo,
            self._foreign_keys,
            self._sync_combo,
            self._backup_dir_edit,
            self._backup_browse_btn,
            self._auto_backup,
            self._open_folder_btn,
            self._table_combo,
            self._preview_refresh_btn,
            self._sql_input,
            self._sql_execute_btn,
            self._btn_integrity,
            self._btn_vacuum,
            self._btn_analyze,
            self._btn_backup,
            self._btn_migrations,
            self._btn_reconnect,
            self._btn_apply,
        ):
            widget.setEnabled(enabled)

    def _load_values(self) -> None:
        if self._db_service is None:
            return
        self._loading = True
        settings = self._db_service.settings
        self._filename_edit.setText(settings.db_filename)
        self._path_value.setText(str(settings.resolved_path(self._db_service.data_dir)))
        self._timeout_spin.setValue(settings.timeout_seconds)
        idx = self._journal_combo.findData(settings.journal_mode)
        if idx >= 0:
            self._journal_combo.setCurrentIndex(idx)
        self._foreign_keys.setChecked(settings.foreign_keys)
        idx_sync = self._sync_combo.findData(settings.synchronous)
        if idx_sync >= 0:
            self._sync_combo.setCurrentIndex(idx_sync)
        self._backup_dir_edit.setText(settings.backup_dir)
        self._auto_backup.setChecked(settings.auto_backup_on_startup)
        self._loading = False

    def _collect_settings(self) -> DatabaseSettings:
        return DatabaseSettings(
            db_filename=self._filename_edit.text().strip() or "app.db",
            journal_mode=str(self._journal_combo.currentData()),
            foreign_keys=self._foreign_keys.isChecked(),
            synchronous=str(self._sync_combo.currentData()),
            timeout_seconds=float(self._timeout_spin.value()),
            backup_dir=self._backup_dir_edit.text().strip(),
            auto_backup_on_startup=self._auto_backup.isChecked(),
        )

    def refresh_status(self) -> None:
        if self._db_service is None:
            self._summary_connected.setText(tr("config_db_unavailable"))
            self._summary_path.clear()
            self._summary_size.clear()
            self._summary_records.clear()
            self._summary_tables.clear()
            return

        status = self._db_service.maintenance.get_status()
        self._path_value.setText(status.path)
        conn_text = (
            tr("config_db_status_connected")
            if status.connected
            else tr("config_db_status_disconnected")
        )
        self._summary_connected.setText(
            tr("config_db_summary_connected", state=conn_text)
        )
        self._summary_path.setText(tr("config_db_summary_path", path=status.path))
        self._summary_size.setText(
            tr("config_db_summary_size", size=format_file_size(status.size_bytes))
        )

        try:
            counts = self._db_service.maintenance.table_row_counts()
        except DatabaseError:
            counts = []

        total_rows = sum(count for _, count in counts)
        self._summary_records.setText(
            tr("config_db_summary_records", count=total_rows)
        )
        if counts:
            lines = [
                tr("config_db_summary_table_line", table=name, count=count)
                for name, count in counts
            ]
            self._summary_tables.setText(
                tr("config_db_summary_tables_title") + "\n" + "\n".join(lines)
            )
        else:
            self._summary_tables.setText(tr("config_db_summary_tables_empty"))

        migrations = (
            ", ".join(status.schema_versions)
            if status.schema_versions
            else tr("config_db_none")
        )
        self._status_migrations.setText(tr("config_db_status_migrations", list=migrations))
        self._status_pragmas.setText(
            tr(
                "config_db_status_pragmas",
                journal=status.journal_mode,
                fk=status.foreign_keys,
                sync=status.synchronous,
            )
        )

        if self._developer_mode:
            self._reload_table_combo(counts)

    def _reload_table_combo(self, counts: List[tuple[str, int]]) -> None:
        current = self._table_combo.currentData()
        self._table_combo.blockSignals(True)
        self._table_combo.clear()
        for name, count in counts:
            self._table_combo.addItem(f"{name} ({count})", name)
        if current:
            idx = self._table_combo.findData(current)
            if idx >= 0:
                self._table_combo.setCurrentIndex(idx)
        self._table_combo.blockSignals(False)
        self._load_table_preview()

    def _load_table_preview(self) -> None:
        if self._db_service is None or not self._developer_mode:
            return
        table = self._table_combo.currentData()
        if not table:
            self._preview_table.setRowCount(0)
            self._preview_table.setColumnCount(0)
            return
        try:
            columns, rows = self._db_service.maintenance.fetch_table_preview(table, limit=50)
        except DatabaseError as exc:
            self._message_label.setText(str(exc))
            return
        self._preview_table.setColumnCount(len(columns))
        self._preview_table.setHorizontalHeaderLabels(columns)
        self._preview_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row):
                self._preview_table.setItem(
                    row_index, col_index, QTableWidgetItem(value)
                )
        self._preview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

    def _open_database_folder(self) -> None:
        if self._db_service is None:
            return
        folder = Path(self._db_service.database.config.path).parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _browse_backup_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, tr("config_db_backup_browse"))
        if directory:
            self._backup_dir_edit.setText(directory)

    def _show_info(self, title_key: str, message: str) -> None:
        QMessageBox.information(self, tr(title_key), message)

    def _show_error(self, error: Exception) -> None:
        QMessageBox.critical(self, tr("error_title"), tr("config_db_error", error=str(error)))

    def _on_apply_settings(self) -> None:
        if self._db_service is None:
            return
        try:
            settings = self._collect_settings()
            self._db_service.save_settings(settings)
            self._db_service.reconnect()
            self.refresh_status()
            self._show_info("config_db_apply_ok_title", tr("config_db_apply_ok"))
        except DatabaseError as exc:
            self._show_error(exc)

    def _on_integrity(self) -> None:
        if self._db_service is None:
            return
        try:
            ok, detail = self._db_service.maintenance.check_integrity()
            if ok:
                self._show_info("config_db_integrity_ok_title", tr("config_db_integrity_ok"))
            else:
                self._show_info(
                    "config_db_integrity_fail_title",
                    tr("config_db_integrity_fail", detail=detail),
                )
        except DatabaseError as exc:
            self._show_error(exc)

    def _on_vacuum(self) -> None:
        if self._db_service is None:
            return
        try:
            self._db_service.maintenance.vacuum()
            self.refresh_status()
            self._show_info("config_db_vacuum_ok_title", tr("config_db_vacuum_ok"))
        except DatabaseError as exc:
            self._show_error(exc)

    def _on_analyze(self) -> None:
        if self._db_service is None:
            return
        try:
            self._db_service.maintenance.analyze()
            self._show_info("config_db_analyze_ok_title", tr("config_db_analyze_ok"))
        except DatabaseError as exc:
            self._show_error(exc)

    def _on_backup(self) -> None:
        if self._db_service is None:
            return
        try:
            settings = self._collect_settings()
            path = self._db_service.maintenance.backup(
                backup_dir=settings.resolved_backup_dir(self._db_service.data_dir)
            )
            self._show_info("config_db_backup_ok_title", tr("config_db_backup_ok", path=str(path)))
        except DatabaseError as exc:
            self._show_error(exc)

    def _on_migrations(self) -> None:
        if self._db_service is None:
            return
        try:
            applied = self._db_service.maintenance.apply_migrations()
            self.refresh_status()
            if applied:
                self._show_info(
                    "config_db_migrations_ok_title",
                    tr("config_db_migrations_ok", count=len(applied), list=", ".join(applied)),
                )
            else:
                self._show_info("config_db_migrations_ok_title", tr("config_db_migrations_none"))
        except DatabaseError as exc:
            self._show_error(exc)

    def _on_reconnect(self) -> None:
        if self._db_service is None:
            return
        try:
            self._db_service.reconnect()
            self.refresh_status()
            self._show_info("config_db_reconnect_ok_title", tr("config_db_reconnect_ok"))
        except DatabaseError as exc:
            self._show_error(exc)

    def _on_execute_sql(self) -> None:
        if self._db_service is None:
            return
        sql = self._sql_input.text().strip()
        if not sql:
            return
        try:
            result = self._db_service.maintenance.execute_sql(sql)
            if result.kind == "select":
                message = tr("config_db_sql_rows", count=result.row_count)
                if result.columns:
                    lines = [" | ".join(result.columns)]
                    for row in result.rows[:20]:
                        lines.append(" | ".join(row))
                    if result.row_count > 20:
                        lines.append("…")
                    self._sql_result.setPlainText(message + "\n" + "\n".join(lines))
                else:
                    self._sql_result.setPlainText(message)
            else:
                self._sql_result.setPlainText(
                    tr("config_db_sql_affected", count=result.row_count)
                )
            self.refresh_status()
        except DatabaseError as exc:
            self._sql_result.setPlainText(str(exc))

    def recargar_textos(self) -> None:
        self._summary_group.setTitle(tr("config_db_summary_group"))
        self._user_intro.setText(tr("config_db_user_intro"))
        self._dev_intro.setText(tr("config_db_dev_intro"))
        self._connection_group.setTitle(tr("config_db_connection"))
        self._filename_label.setText(tr("config_db_filename"))
        self._path_label.setText(tr("config_db_path"))
        self._timeout_label.setText(tr("config_db_timeout"))
        self._open_folder_btn.setText(tr("config_db_open_folder"))
        self._pragmas_group.setTitle(tr("config_db_pragmas"))
        self._journal_label.setText(tr("config_db_journal_mode"))
        self._foreign_keys.setText(tr("config_db_foreign_keys"))
        self._sync_label.setText(tr("config_db_synchronous"))
        self._backup_group.setTitle(tr("config_db_backup"))
        self._backup_dir_label.setText(tr("config_db_backup_dir"))
        self._backup_browse_btn.setText(tr("config_db_backup_browse"))
        self._auto_backup.setText(tr("config_db_auto_backup"))
        self._explorer_group.setTitle(tr("config_db_explorer_group"))
        self._preview_refresh_btn.setText(tr("config_db_btn_refresh"))
        self._sql_group.setTitle(tr("config_db_sql_group"))
        self._sql_execute_btn.setText(tr("config_db_sql_execute"))
        self._maintenance_group.setTitle(tr("config_db_maintenance"))
        self._btn_integrity.setText(tr("config_db_btn_integrity"))
        self._btn_vacuum.setText(tr("config_db_btn_vacuum"))
        self._btn_analyze.setText(tr("config_db_btn_analyze"))
        self._btn_backup.setText(tr("config_db_btn_backup"))
        self._btn_migrations.setText(tr("config_db_btn_migrations"))
        self._btn_reconnect.setText(tr("config_db_btn_reconnect"))
        self._btn_apply.setText(tr("config_db_btn_apply"))
        self._refresh_summary_btn.setText(tr("config_db_btn_refresh"))
        if self._developer_lock is not None:
            self._developer_lock.recargar_textos()
        self.refresh_status()
        self._apply_hint_style()

    def _apply_hint_style(self) -> None:
        hint_color = "#858585" if is_dark_mode() else "#6A6A6A"
        hint_style = f"color: {hint_color}; font-size: 11px;"
        self._user_intro.setStyleSheet(hint_style)
        self._dev_intro.setStyleSheet(hint_style)
        self._message_label.setStyleSheet(hint_style)
