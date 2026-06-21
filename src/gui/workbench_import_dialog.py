"""Diálogo de importación de show Shure Wireless Workbench."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from gui.dialog_styles import apply_professional_dialog_style
from gui.message_box_utils import localize_dialog_button_box
from importers.workbench_models import WorkbenchShow
from i18n.json_translation import tr


class WorkbenchImportDialog(QDialog):
    """Confirma modo de importación tras elegir un fichero `.shw`."""

    MODE_NEW_PROJECT = "new_project"
    MODE_REPLACE_INVENTORY = "replace_inventory"

    def __init__(
        self,
        show: WorkbenchShow,
        parent=None,
        *,
        allow_replace: bool = True,
    ) -> None:
        super().__init__(parent)
        self._show = show
        self._allow_replace = allow_replace
        self._selected_mode = self.MODE_NEW_PROJECT

        self.setWindowTitle(tr("workbench_import_title"))
        self.setMinimumWidth(480)
        apply_professional_dialog_style(self)

        summary = QLabel(
            tr(
                "workbench_import_summary",
                name=show.info.name or tr("project_untitled_show"),
                devices=len(show.devices),
                channels=show.channel_count,
                customer=show.info.customer or "—",
            )
        )
        summary.setWordWrap(True)

        self._radio_new = QRadioButton(tr("workbench_import_mode_new"))
        self._radio_replace = QRadioButton(tr("workbench_import_mode_replace"))
        self._radio_new.setChecked(True)
        self._radio_replace.setEnabled(allow_replace)
        if not allow_replace:
            self._radio_replace.setToolTip(tr("workbench_import_replace_requires_project"))

        group_box = QGroupBox(tr("workbench_import_mode_group"))
        mode_layout = QVBoxLayout(group_box)
        mode_layout.addWidget(self._radio_new)
        mode_layout.addWidget(self._radio_replace)

        button_group = QButtonGroup(self)
        button_group.addButton(self._radio_new)
        button_group.addButton(self._radio_replace)

        form = QFormLayout()
        form.addRow(tr("workbench_import_file"), QLabel(show.source_path))
        form.addRow(tr("workbench_import_version"), QLabel(show.workbench_version or "—"))
        if show.has_coordination and show.coordination:
            coord = show.coordination
            coord_detail = tr(
                "workbench_import_coordination_hint",
                included=coord.included_channel_count,
                active=coord.active_channel_count,
                assigned=coord.assigned_frequency_count,
            )
        else:
            coord_detail = tr("workbench_import_coordination_none")
        form.addRow(tr("workbench_import_coordination"), QLabel(coord_detail))

        self._import_coordination = QCheckBox(tr("workbench_import_coordination_enable"))
        self._import_coordination.setChecked(bool(show.has_coordination))
        self._import_coordination.setEnabled(bool(show.has_coordination))

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        localize_dialog_button_box(self._buttons)

        layout = QVBoxLayout(self)
        layout.addWidget(summary)
        layout.addLayout(form)
        layout.addWidget(group_box)
        layout.addWidget(self._import_coordination)
        layout.addWidget(self._buttons)

    @property
    def selected_mode(self) -> str:
        if self._radio_replace.isChecked():
            return self.MODE_REPLACE_INVENTORY
        return self.MODE_NEW_PROJECT

    @property
    def import_coordination(self) -> bool:
        return self._import_coordination.isChecked()

    def recargar_textos(self) -> None:
        self.setWindowTitle(tr("workbench_import_title"))
