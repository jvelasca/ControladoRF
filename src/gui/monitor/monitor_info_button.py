"""Botón ℹ compacto para textos de ayuda en paneles Monitor."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QToolButton, QWidget

from i18n.json_translation import tr


class MonitorInfoButton(QToolButton):
    """Muestra un diálogo con información complementaria al pulsar."""

    def __init__(
        self,
        *,
        title_key: str,
        body_key: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._title_key = title_key
        self._body_key = body_key
        self.setText("i")
        self.setToolTip(tr("monitor_info_button_tip"))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.setFixedSize(22, 22)
        self.setObjectName("MonitorInfoButton")
        from gui.app_chrome_styles import apply_monitor_info_button_styles

        apply_monitor_info_button_styles(self)
        self.clicked.connect(self._show_info)

    def _show_info(self) -> None:
        QMessageBox.information(
            self.window(),
            tr(self._title_key),
            tr(self._body_key),
        )

    def recargar_textos(self) -> None:
        self.setToolTip(tr("monitor_info_button_tip"))
