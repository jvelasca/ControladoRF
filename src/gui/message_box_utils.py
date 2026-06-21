"""Cuadros de diálogo con textos traducidos (independientes del idioma del SO)."""
from __future__ import annotations

from enum import Enum

from PyQt6.QtWidgets import QDialogButtonBox, QMessageBox

from i18n.json_translation import tr


class SaveDiscardCancel(Enum):
    SAVE = "save"
    DISCARD = "discard"
    CANCEL = "cancel"


_STANDARD_DIALOG_BUTTONS = {
    QDialogButtonBox.StandardButton.Ok: "ok",
    QDialogButtonBox.StandardButton.Cancel: "cancel",
    QDialogButtonBox.StandardButton.Close: "close",
    QDialogButtonBox.StandardButton.Save: "msgbox_save",
    QDialogButtonBox.StandardButton.Yes: "inventory_yes",
    QDialogButtonBox.StandardButton.No: "inventory_no",
}


def localize_dialog_button_box(button_box: QDialogButtonBox) -> None:
    """Traduce los botones estándar de un QDialogButtonBox."""
    for standard, key in _STANDARD_DIALOG_BUTTONS.items():
        button = button_box.button(standard)
        if button is not None:
            button.setText(tr(key))


def ask_save_discard_cancel(parent, title: str, text: str) -> SaveDiscardCancel:
    """Pregunta Guardar / No guardar / Cancelar con textos de la app."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)
    save_btn = box.addButton(tr("msgbox_save"), QMessageBox.ButtonRole.AcceptRole)
    discard_btn = box.addButton(tr("msgbox_discard"), QMessageBox.ButtonRole.DestructiveRole)
    cancel_btn = box.addButton(tr("cancel"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(save_btn)
    box.setEscapeButton(cancel_btn)
    box.exec()
    clicked = box.clickedButton()
    if clicked == save_btn:
        return SaveDiscardCancel.SAVE
    if clicked == discard_btn:
        return SaveDiscardCancel.DISCARD
    return SaveDiscardCancel.CANCEL


def ask_yes_no(parent, title: str, text: str, *, default_yes: bool = False) -> bool:
    """Pregunta Sí / No con textos de la app."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)
    yes_btn = box.addButton(tr("inventory_yes"), QMessageBox.ButtonRole.YesRole)
    no_btn = box.addButton(tr("inventory_no"), QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(yes_btn if default_yes else no_btn)
    box.setEscapeButton(no_btn)
    box.exec()
    return box.clickedButton() == yes_btn
