"""Formulario mínimo para reportar fallos y mejoras al desarrollador."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.app_contact import build_feedback_mailto_url, format_app_support_emails
from gui.app_branding import get_app_version
from i18n.json_translation import tr


class DeveloperFeedbackForm(QWidget):
    """Cuadro de texto + enviar → cliente de correo (mailto)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("DeveloperFeedbackForm")
        self._label = QLabel(self)
        self._label.setObjectName("DeveloperFeedbackLabel")
        self._label.setWordWrap(True)
        self._email_label = QLabel(self)
        self._email_label.setObjectName("DeveloperFeedbackEmailLabel")
        self._email_label.setWordWrap(True)
        self._text = QTextEdit(self)
        self._text.setObjectName("DeveloperFeedbackText")
        self._text.setPlaceholderText(tr("monitor_debug_feedback_placeholder"))
        self._text.setMinimumHeight(72)
        self._text.setMaximumHeight(120)
        self._send_btn = QPushButton(tr("monitor_debug_feedback_send"), self)
        self._send_btn.setObjectName("DeveloperFeedbackSendBtn")
        self._send_btn.clicked.connect(self._on_send)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)
        row.addWidget(self._send_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._label)
        layout.addWidget(self._email_label)
        layout.addWidget(self._text)
        layout.addLayout(row)
        self.recargar_textos()

    def recargar_textos(self) -> None:
        self._label.setText(tr("monitor_debug_feedback_prompt"))
        self._email_label.setText(
            f"{tr('monitor_debug_feedback_to')}: {format_app_support_emails()}"
        )
        self._text.setPlaceholderText(tr("monitor_debug_feedback_placeholder"))
        self._send_btn.setText(tr("monitor_debug_feedback_send"))

    def _on_send(self) -> None:
        message = self._text.toPlainText().strip()
        if not message:
            QMessageBox.information(
                self.window(),
                tr("monitor_debug_feedback_title"),
                tr("monitor_debug_feedback_empty"),
            )
            return
        app = tr("app_title")
        version = get_app_version()
        subject = tr("monitor_debug_feedback_subject").format(app=app)
        body = (
            f"{message}\n\n"
            f"---\n"
            f"{app} {version}\n"
            f"{tr('monitor_debug_feedback_to')}: {format_app_support_emails()}"
        )
        url = QUrl(build_feedback_mailto_url(body=body, subject=subject))
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(
                self.window(),
                tr("monitor_debug_feedback_title"),
                tr("monitor_debug_feedback_mail_failed"),
            )
            return
        QMessageBox.information(
            self.window(),
            tr("monitor_debug_feedback_title"),
            tr("monitor_debug_feedback_mail_opened"),
        )
