"""Visor de ayuda estándar (markdown desde docs/)."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout, QWidget

from gui.dialog_styles import apply_professional_dialog_style, build_dialog_header
from gui.help_content import HelpTopic, load_help_markdown
from i18n.json_translation import tr

_TOPIC_TITLE = {
    "manual": "help_manual_title",
    "supervision": "monitor_supervision_help_title",
}

_TOPIC_INTRO = {
    "manual": "help_manual_intro",
    "supervision": "monitor_supervision_help_intro",
}

_TOPIC_ICON = {
    "manual": "about",
    "supervision": "spectrum",
}


class HelpDialog(QDialog):
    def __init__(
        self,
        topic: HelpTopic,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._topic = topic
        self._browser: QTextBrowser | None = None
        self.setWindowTitle(tr(_TOPIC_TITLE[topic]))
        apply_professional_dialog_style(self)
        self.resize(860, 640)
        self._build_ui()

    def recargar_textos(self) -> None:
        self.setWindowTitle(tr(_TOPIC_TITLE[self._topic]))
        if self._browser is not None:
            self._browser.setMarkdown(load_help_markdown(self._topic))

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(
            build_dialog_header(
                tr(_TOPIC_TITLE[self._topic]),
                tr(_TOPIC_INTRO[self._topic]),
                icon_name=_TOPIC_ICON[self._topic],
            )
        )

        self._browser = QTextBrowser(self)
        self._browser.setOpenExternalLinks(True)
        self._browser.setMarkdown(load_help_markdown(self._topic))
        layout.addWidget(self._browser, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.accept)
        layout.addWidget(buttons)


def show_help_dialog(topic: HelpTopic, *, parent: Optional[QWidget] = None) -> None:
    HelpDialog(topic, parent=parent).exec()
