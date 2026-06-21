"""Botón candado para modo desarrollador (contraseña 1493)."""
from __future__ import annotations

from typing import Callable, Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QToolButton, QWidget

from core.developer_mode import read_developer_mode, write_developer_mode
from gui.developer_password_dialog import prompt_developer_password
from gui.icon_utils import ICON_SIZE_BUTTON, get_app_icon


from i18n.json_translation import tr


class DeveloperLockButton(QToolButton):
    """Candado: cerrado = herramientas protegidas; abierto = modo desarrollador."""

    unlocked_changed = pyqtSignal(bool)

    def __init__(
        self,
        *,
        get_config: Callable[[], Dict],
        set_config: Callable[[Dict], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._get_config = get_config
        self._set_config = set_config
        self._syncing = False
        self.setCheckable(True)
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(28, 26)
        self.clicked.connect(self._on_clicked)
        self.sync_from_config()
        self.recargar_textos()

    def is_unlocked(self) -> bool:
        return self.isChecked()

    def sync_from_config(self) -> None:
        unlocked = read_developer_mode(self._get_config)
        self._syncing = True
        self.setChecked(unlocked)
        self._syncing = False
        self._refresh_icon()

    def recargar_textos(self) -> None:
        if self.isChecked():
            self.setToolTip(tr("config_dev_lock_open_tip"))
        else:
            self.setToolTip(tr("config_dev_lock_closed_tip"))

    def _refresh_icon(self) -> None:
        name = "unlock" if self.isChecked() else "lock"
        self.setIcon(get_app_icon(name, ICON_SIZE_BUTTON))
        self.setIconSize(self.size() * 0.65)

    def _on_clicked(self) -> None:
        if self._syncing:
            return
        if self.isChecked():
            if not prompt_developer_password(self.window()):
                self._syncing = True
                self.setChecked(False)
                self._syncing = False
                self.recargar_textos()
                return
            write_developer_mode(self._get_config, self._set_config, True)
        else:
            write_developer_mode(self._get_config, self._set_config, False)
        self._refresh_icon()
        self.recargar_textos()
        self.unlocked_changed.emit(self.isChecked())
