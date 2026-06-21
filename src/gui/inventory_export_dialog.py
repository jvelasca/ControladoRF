"""Diálogo para exportar la lista de inventario RF."""

from __future__ import annotations



import os

from pathlib import Path



from PyQt6.QtCore import Qt

from PyQt6.QtWidgets import (

    QButtonGroup,

    QDialog,

    QDialogButtonBox,

    QFileDialog,

    QFormLayout,

    QGroupBox,

    QHBoxLayout,

    QLabel,

    QLineEdit,

    QMessageBox,

    QPushButton,

    QRadioButton,

    QVBoxLayout,

)



from core.inventory_export import (

    EXPORT_FORMAT_CSV,

    EXPORT_FORMAT_JSON,

    EXPORT_FORMAT_PDF,

    InventoryExportError,

    build_inventory_list_export,

    default_export_filename,

    export_inventory_csv,

    export_inventory_json,

)

from gui.dialog_styles import add_dialog_separator, apply_professional_dialog_style, build_dialog_header

from gui.inventory_export_labels import (

    build_inventory_export_labels,

    format_bool,

    format_device_type,

)

from gui.inventory_export_pdf import export_inventory_pdf

from gui.message_box_utils import localize_dialog_button_box

from i18n.json_translation import tr





class InventoryExportDialog(QDialog):

    """Confirma formato, ruta y exporta solo la lista del inventario."""



    def __init__(

        self,

        parent,

        *,

        project,

        project_name: str,

        default_dir: str,

    ) -> None:

        super().__init__(parent)

        self._project = project

        self._project_name = project_name

        self._default_dir = default_dir

        self._document = build_inventory_list_export(project, project_name=project_name)

        self._channel_count = int(self._document.get("list", {}).get("channel_count", 0))



        self.setWindowTitle(tr("inventory_export_title"))

        self.setMinimumWidth(560)

        apply_professional_dialog_style(self)



        summary = tr(

            "inventory_export_summary",

            project=project_name or tr("project_untitled_show"),

            count=self._channel_count,

        )

        self._header = build_dialog_header(tr("inventory_export_title"), summary, icon_name="export")



        format_group = QGroupBox(tr("inventory_export_format_group"))

        format_layout = QVBoxLayout(format_group)

        format_layout.setSpacing(6)

        self._radio_csv = QRadioButton(tr("inventory_export_format_csv"))

        self._radio_json = QRadioButton(tr("inventory_export_format_json"))

        self._radio_pdf = QRadioButton(tr("inventory_export_format_pdf"))

        self._radio_csv.setChecked(True)

        for radio in (self._radio_csv, self._radio_json, self._radio_pdf):

            format_layout.addWidget(radio)



        button_group = QButtonGroup(self)

        button_group.addButton(self._radio_csv, 0)

        button_group.addButton(self._radio_json, 1)

        button_group.addButton(self._radio_pdf, 2)

        button_group.idClicked.connect(self._on_format_changed)



        self._path_edit = QLineEdit()

        self._path_edit.setText(self._default_path_for_format(EXPORT_FORMAT_CSV))

        self._browse_btn = QPushButton(tr("inventory_export_browse"))

        self._browse_btn.clicked.connect(self._browse_path)



        path_row = QHBoxLayout()

        path_row.setContentsMargins(0, 0, 0, 0)

        path_row.addWidget(self._path_edit, stretch=1)

        path_row.addWidget(self._browse_btn)



        path_group = QGroupBox(tr("inventory_export_path_group"))

        path_form = QFormLayout(path_group)

        path_form.setContentsMargins(12, 12, 12, 12)

        path_form.addRow(tr("inventory_export_path_label"), path_row)



        self._hint = QLabel(tr("inventory_export_hint"))

        self._hint.setWordWrap(True)

        self._hint.setObjectName("DialogStatusLabel")



        self._buttons = QDialogButtonBox(

            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save

        )

        self._buttons.accepted.connect(self._on_export)

        self._buttons.rejected.connect(self.reject)

        localize_dialog_button_box(self._buttons)



        layout = QVBoxLayout(self)

        layout.setContentsMargins(16, 16, 16, 12)

        layout.setSpacing(12)

        layout.addWidget(self._header)

        add_dialog_separator(layout)

        layout.addWidget(format_group)

        layout.addWidget(path_group)

        layout.addWidget(self._hint)

        layout.addWidget(self._buttons)



        self.recargar_textos()



    def recargar_textos(self) -> None:

        summary = tr(

            "inventory_export_summary",

            project=self._project_name or tr("project_untitled_show"),

            count=self._channel_count,

        )

        self.setWindowTitle(tr("inventory_export_title"))

        self._header._title_label.setText(tr("inventory_export_title"))  # type: ignore[attr-defined]

        if self._header._subtitle_label is not None:  # type: ignore[attr-defined]

            self._header._subtitle_label.setText(summary)

        self._hint.setText(tr("inventory_export_hint"))

        self._radio_csv.setText(tr("inventory_export_format_csv"))

        self._radio_json.setText(tr("inventory_export_format_json"))

        self._radio_pdf.setText(tr("inventory_export_format_pdf"))

        self._browse_btn.setText(tr("inventory_export_browse"))

        localize_dialog_button_box(self._buttons)



    def _on_format_changed(self, button_id: int) -> None:

        mapping = {0: EXPORT_FORMAT_CSV, 1: EXPORT_FORMAT_JSON, 2: EXPORT_FORMAT_PDF}

        new_format = mapping.get(button_id, EXPORT_FORMAT_CSV)

        current = self._path_edit.text().strip()

        directory = str(Path(current).parent) if current and Path(current).parent.name else self._default_dir

        self._path_edit.setText(os.path.join(directory, default_export_filename(self._project_name, new_format)))



    def _default_path_for_format(self, export_format: str) -> str:

        filename = default_export_filename(self._project_name, export_format)

        return os.path.join(self._default_dir, filename)



    def _browse_path(self) -> None:

        export_format = self._current_format()

        path, _ = QFileDialog.getSaveFileName(

            self,

            tr("inventory_export_save_title"),

            self._path_edit.text() or self._default_path_for_format(export_format),

            _file_filter(export_format),

        )

        if path:

            self._path_edit.setText(_ensure_extension(path, export_format))



    def _current_format(self) -> str:

        if self._radio_json.isChecked():

            return EXPORT_FORMAT_JSON

        if self._radio_pdf.isChecked():

            return EXPORT_FORMAT_PDF

        return EXPORT_FORMAT_CSV



    def _on_export(self) -> None:

        export_format = self._current_format()

        path = _ensure_extension(self._path_edit.text().strip(), export_format)

        if not path:

            QMessageBox.warning(self, tr("error_title"), tr("inventory_export_path_required"))

            return

        try:

            self._write_export(path, export_format)

        except InventoryExportError as exc:

            QMessageBox.critical(self, tr("error_title"), tr("inventory_export_error", error=str(exc)))

            return

        self.accept()



    def _write_export(self, path: str, export_format: str) -> None:

        labels = build_inventory_export_labels()

        bool_labels = {True: labels.bool_true, False: labels.bool_false}

        if export_format == EXPORT_FORMAT_JSON:

            export_inventory_json(self._document, path)

        elif export_format == EXPORT_FORMAT_CSV:

            formatters = {

                "device_type": lambda value: format_device_type(str(value or ""), labels),

                "coordination_include": lambda value: format_bool(value, labels),

                "coordination_active": lambda value: format_bool(value, labels),

                "locked": lambda value: format_bool(value, labels),

            }

            export_inventory_csv(

                self._document,

                path,

                field_labels=labels.field_labels,

                bool_labels=bool_labels,

                value_formatters=formatters,

            )

        elif export_format == EXPORT_FORMAT_PDF:

            export_inventory_pdf(self._document, path, labels=labels)

        else:

            raise InventoryExportError(f"Unsupported format: {export_format}")





def _extension(export_format: str) -> str:

    if export_format == EXPORT_FORMAT_JSON:

        return "json"

    if export_format == EXPORT_FORMAT_PDF:

        return "pdf"

    return "csv"





def _ensure_extension(path: str, export_format: str) -> str:

    ext = _extension(export_format)

    suffix = Path(path).suffix.lower()

    if suffix != f".{ext}":

        return str(Path(path).with_suffix(f".{ext}"))

    return path





def _file_filter(export_format: str) -> str:

    if export_format == EXPORT_FORMAT_JSON:

        return tr("inventory_export_filter_json")

    if export_format == EXPORT_FORMAT_PDF:

        return tr("inventory_export_filter_pdf")

    return tr("inventory_export_filter_csv")


