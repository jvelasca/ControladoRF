"""Cabecera de panel con controles tipo IDE (cerrar / maximizar)."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QStyle,
    QToolButton,
    QWidget,
)

from gui.panel_styles import apply_panel_header_bar
from i18n.json_translation import tr


class PanelHeaderBar(QWidget):
    """Título a la izquierda; maximizar y cerrar a la derecha (estilo Cursor/VS Code)."""

    close_requested = pyqtSignal()
    maximize_toggled = pyqtSignal()

    _BTN_SIZE = QSize(22, 22)
    _ICON_SIZE = QSize(12, 12)

    def __init__(
        self,
        panel_id: str,
        *,
        style_key: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.panel_id = panel_id
        self._style_key = style_key
        self._maximized = False

        self.setObjectName("PanelHeaderBar")
        self.setFixedHeight(28)

        self._title = QLabel()
        self._title.setObjectName("ModulePanelTitle")

        self._maximize_btn = QToolButton()
        self._maximize_btn.setObjectName("PanelHeaderMaximizeButton")
        self._maximize_btn.setAutoRaise(True)
        self._maximize_btn.setFixedSize(self._BTN_SIZE)
        self._maximize_btn.setIconSize(self._ICON_SIZE)
        self._maximize_btn.clicked.connect(self.maximize_toggled.emit)

        self._close_btn = QToolButton()
        self._close_btn.setObjectName("PanelHeaderCloseButton")
        self._close_btn.setAutoRaise(True)
        self._close_btn.setFixedSize(self._BTN_SIZE)
        self._close_btn.setIconSize(self._ICON_SIZE)
        self._close_btn.clicked.connect(self.close_requested.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 2, 0)
        layout.setSpacing(0)
        layout.addWidget(self._title, stretch=1)
        layout.addWidget(self._maximize_btn)
        layout.addWidget(self._close_btn)

        self._apply_button_icons()
        self.recargar_textos()
        self.apply_visual_theme()

    def set_title(self, text: str) -> None:
        self._title.setText(text)

    def set_maximized(self, maximized: bool) -> None:
        self._maximized = maximized
        self._apply_button_icons()
        self._maximize_btn.setToolTip(
            tr("panel_header_restore") if maximized else tr("panel_header_maximize")
        )

    def apply_visual_theme(self) -> None:
        apply_panel_header_bar(self, self._style_key, self._title)

    def recargar_textos(self) -> None:
        self._close_btn.setToolTip(tr("panel_header_close"))
        self._maximize_btn.setToolTip(
            tr("panel_header_restore") if self._maximized else tr("panel_header_maximize")
        )

    def _apply_button_icons(self) -> None:
        style = self.style()
        max_icon = (
            QStyle.StandardPixmap.SP_TitleBarNormalButton
            if self._maximized
            else QStyle.StandardPixmap.SP_TitleBarMaxButton
        )
        self._maximize_btn.setIcon(style.standardIcon(max_icon))
        self._close_btn.setIcon(
            style.standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton)
        )
