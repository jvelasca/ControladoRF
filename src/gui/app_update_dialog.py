"""Diálogo de actualización disponible (GitHub Releases)."""
from __future__ import annotations

import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)

from core.app_update import UpdateInfo
from i18n.json_translation import tr


class AppUpdateDialog(QDialog):
    def __init__(self, info: UpdateInfo, parent=None) -> None:
        super().__init__(parent)
        self._info = info
        self.setWindowTitle(tr("app_update_title"))
        self.setModal(True)
        self.resize(520, 360)

        layout = QVBoxLayout(self)
        headline = QLabel(
            tr("app_update_headline").format(
                current=info.current_version,
                latest=info.latest_version,
            )
        )
        headline.setWordWrap(True)
        layout.addWidget(headline)

        if info.release_name:
            layout.addWidget(QLabel(info.release_name))

        notes = QPlainTextEdit()
        notes.setReadOnly(True)
        notes.setPlainText(info.release_notes or tr("app_update_no_notes"))
        layout.addWidget(notes, stretch=1)

        buttons = QDialogButtonBox()
        download_btn = buttons.addButton(tr("app_update_download"), QDialogButtonBox.ButtonRole.AcceptRole)
        later_btn = buttons.addButton(tr("app_update_later"), QDialogButtonBox.ButtonRole.RejectRole)
        download_btn.clicked.connect(self._open_download)
        later_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _open_download(self) -> None:
        url = self._info.download_url or self._info.html_url
        if url:
            webbrowser.open(url)
        self.accept()
