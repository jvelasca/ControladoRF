"""Panel con título y controles IDE dentro del espacio de trabajo de un módulo."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QWidget

from gui.panel_header_bar import PanelHeaderBar
from gui.panel_styles import apply_panel_frame
from i18n.json_translation import tr


class ModulePanelFrame(QFrame):
    """Contenedor visual de un panel: cabecera con cerrar/maximizar + contenido."""

    close_requested = pyqtSignal()
    maximize_toggled = pyqtSignal()

    def __init__(
        self,
        module_id: str,
        panel_id: str,
        *,
        content_widget: Optional[QWidget] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.module_id = module_id
        self.panel_id = panel_id
        self._style_key = f"{module_id}_{panel_id}"

        self.setFrameShape(QFrame.Shape.StyledPanel)

        self._header = PanelHeaderBar(panel_id, style_key=self._style_key, parent=self)
        self._header.close_requested.connect(self.close_requested.emit)
        self._header.maximize_toggled.connect(self.maximize_toggled.emit)

        self._content = content_widget
        if self._content is None:
            from gui.placeholder_panel import PlaceholderPanelWidget

            self._content = PlaceholderPanelWidget(module_id, panel_id)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(self._header)
        layout.addWidget(self._content, stretch=1)

        self.setMinimumWidth(160)
        self.setMinimumHeight(100)
        self.recargar_textos()
        self.apply_visual_theme()

    @property
    def content(self) -> QWidget:
        return self._content

    def set_header_maximized(self, maximized: bool) -> None:
        self._header.set_maximized(maximized)

    def apply_visual_theme(self) -> None:
        apply_panel_frame(self, self._style_key)
        self._header.apply_visual_theme()
        if hasattr(self._content, "apply_visual_theme"):
            self._content.apply_visual_theme(self._style_key)

    def recargar_textos(self) -> None:
        title_key = f"{self.module_id}_panel_{self.panel_id}_title"
        self._header.set_title(tr(title_key))
        self._header.recargar_textos()
        if hasattr(self._content, "recargar_textos"):
            self._content.recargar_textos()
