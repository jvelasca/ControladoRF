"""Diálogo de contraseña para activar el modo desarrollador."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from core.developer_mode import verify_developer_password
from gui.dialog_styles import apply_professional_dialog_style
from i18n.json_translation import tr


def prompt_developer_password(parent: Optional[QWidget] = None) -> bool:
    """Solicita la contraseña de desarrollador. Devuelve True si es correcta."""
    dialog = DeveloperPasswordDialog(parent)
    return dialog.exec() == QDialog.DialogCode.Accepted


class DeveloperPasswordDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(360)
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.returnPressed.connect(self._on_accept)

        intro = QLabel(tr("config_dev_password_intro"))
        intro.setWordWrap(True)

        form = QFormLayout()
        form.addRow(tr("config_dev_password_label"), self._password)

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(self._button_box)

        self.recargar_textos()
        apply_professional_dialog_style(self)

    def recargar_textos(self) -> None:
        self.setWindowTitle(tr("config_dev_password_title"))
        ok_btn = self._button_box.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = self._button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_btn:
            ok_btn.setText(tr("ok"))
        if cancel_btn:
            cancel_btn.setText(tr("cancel"))

    def _on_accept(self) -> None:
        if verify_developer_password(self._password.text()):
            self.accept()
            return
        self._password.clear()
        self._password.setPlaceholderText(tr("config_dev_password_wrong"))
        self._password.setFocus(Qt.FocusReason.OtherFocusReason)
