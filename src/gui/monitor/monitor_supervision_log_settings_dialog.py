"""Diálogo de rutas, disparador CSV e inicio de REC para logs de supervisión."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.monitor.supervision.supervision_log_paths import (
    resolve_supervision_log_directory,
    resolve_supervision_log_export_directory,
)
from core.monitor.supervision.supervision_models import SupervisionSettings, SupervisionState
from i18n.json_translation import tr


class MonitorSupervisionLogSettingsDialog(QDialog):
    """Edita ``log_directory``, ``log_export_directory``, ``log_trigger`` y ``rec_start_mode``."""

    def __init__(
        self,
        state: SupervisionState,
        *,
        project_file_path: str = "",
        project_name: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._project_file_path = project_file_path
        self._project_name = project_name
        self.setWindowTitle(tr("monitor_alarmas_log_settings_title"))
        self.setMinimumWidth(420)
        self._build_ui()
        self._load_settings(state.settings)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._log_dir_edit = QLineEdit()
        self._log_dir_edit.setPlaceholderText(self._default_log_directory())
        form.addRow(tr("monitor_alarmas_log_directory"), self._folder_row(self._log_dir_edit, self._browse_log_directory))

        self._export_dir_edit = QLineEdit()
        self._export_dir_edit.setPlaceholderText(self._default_export_directory())
        form.addRow(
            tr("monitor_alarmas_log_export_directory"),
            self._folder_row(self._export_dir_edit, self._browse_export_directory),
        )

        self._trigger_combo = QComboBox()
        self._trigger_combo.addItem(tr("monitor_alarmas_log_manual"), "manual")
        self._trigger_combo.addItem(tr("monitor_alarmas_log_play"), "play")
        self._trigger_combo.addItem(tr("monitor_alarmas_log_auto"), "auto")
        form.addRow(tr("monitor_alarmas_log_trigger"), self._trigger_combo)

        self._rec_start_combo = QComboBox()
        self._rec_start_combo.addItem(tr("monitor_alarmas_rec_start_manual"), "manual")
        self._rec_start_combo.addItem(tr("monitor_alarmas_rec_start_play"), "play")
        form.addRow(tr("monitor_alarmas_rec_start_mode"), self._rec_start_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _folder_row(self, edit: QLineEdit, browse_handler) -> QWidget:
        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        edit.setMinimumWidth(0)
        row_layout.addWidget(edit, stretch=1)
        browse_btn = QPushButton(tr("monitor_recorder_browse"))
        browse_btn.clicked.connect(browse_handler)
        row_layout.addWidget(browse_btn)
        return row

    def _default_log_directory(self) -> str:
        return str(
            resolve_supervision_log_directory(
                self._state,
                project_file_path=self._project_file_path or None,
                project_name=self._project_name,
            )
        )

    def _default_export_directory(self) -> str:
        return str(
            resolve_supervision_log_export_directory(
                self._state,
                project_file_path=self._project_file_path or None,
                project_name=self._project_name,
            )
        )

    def _browse_log_directory(self) -> None:
        start = self._log_dir_edit.text().strip() or self._default_log_directory()
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("monitor_alarmas_log_directory"),
            start,
        )
        if folder:
            self._log_dir_edit.setText(folder)

    def _browse_export_directory(self) -> None:
        start = self._export_dir_edit.text().strip() or self._default_export_directory()
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("monitor_alarmas_log_export_directory"),
            start,
        )
        if folder:
            self._export_dir_edit.setText(folder)

    def _load_settings(self, settings: SupervisionSettings) -> None:
        self._log_dir_edit.setText(settings.log_directory or "")
        self._export_dir_edit.setText(settings.log_export_directory or "")
        idx = self._trigger_combo.findData(settings.log_trigger)
        if idx < 0:
            idx = self._trigger_combo.findData("manual")
        if idx >= 0:
            self._trigger_combo.setCurrentIndex(idx)
        rec_idx = self._rec_start_combo.findData(settings.rec_start_mode)
        if rec_idx < 0:
            rec_idx = self._rec_start_combo.findData("manual")
        if rec_idx >= 0:
            self._rec_start_combo.setCurrentIndex(rec_idx)

    def get_settings(self) -> SupervisionSettings:
        settings = self._state.settings
        settings.log_directory = self._log_dir_edit.text().strip()
        settings.log_export_directory = self._export_dir_edit.text().strip()
        trigger = self._trigger_combo.currentData()
        settings.log_trigger = str(trigger or "manual")  # type: ignore[assignment]
        rec_start = self._rec_start_combo.currentData()
        settings.rec_start_mode = str(rec_start or "manual")  # type: ignore[assignment]
        return settings

    def recargar_textos(self) -> None:
        self.setWindowTitle(tr("monitor_alarmas_log_settings_title"))
