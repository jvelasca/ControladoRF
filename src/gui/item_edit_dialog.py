"""Diálogo para crear o editar un item."""
from __future__ import annotations

from typing import Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.dialog_styles import apply_professional_dialog_style
from i18n.json_translation import tr


class ItemEditDialog(QDialog):
    """Formulario modal de nombre y descripción."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        name: str = "",
        description: str = "",
        title_key: str = "items_dialog_add_title",
    ) -> None:
        super().__init__(parent)
        self._title_key = title_key
        self._name_edit = QLineEdit(name)
        self._desc_edit = QTextEdit(description)
        self._desc_edit.setMaximumHeight(100)
        self._setup_ui()
        self.recargar_textos()
        apply_professional_dialog_style(self)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._name_caption = QLabel()
        form.addRow(self._name_caption, self._name_edit)
        self._desc_caption = QLabel()
        form.addRow(self._desc_caption, self._desc_edit)
        layout.addLayout(form)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    def recargar_textos(self) -> None:
        self.setWindowTitle(tr(self._title_key))
        self._name_caption.setText(tr("items_field_name"))
        self._desc_caption.setText(tr("items_field_description"))
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("items_btn_save"))
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))

    def get_values(self) -> Tuple[str, str]:
        return self._name_edit.text(), self._desc_edit.toPlainText()
