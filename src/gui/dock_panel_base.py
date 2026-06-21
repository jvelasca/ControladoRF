"""
Clase base para paneles acoplables (QDockWidget) con estilo adaptativo e i18n.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDockWidget, QWidget

from gui.panel_styles import apply_dock_chrome, apply_panel_style, build_panel_content, refresh_panel_appearance


class BaseDockPanel(QDockWidget):
    """Panel dock reutilizable con apariencia profesional adaptada al tema Qt activo."""

    PANEL_ID: str = ""
    MIN_DOCK_WIDTH = 180
    MIN_DOCK_HEIGHT = 120

    def __init__(self, parent=None, *, content_widget: QWidget | None = None) -> None:
        super().__init__(parent)
        self._configure_dock_behavior()
        self._label = None
        if content_widget is not None:
            self._container = content_widget
        else:
            self._container, self._label = build_panel_content(self.PANEL_ID, "")
        self.setWidget(self._container)
        self.apply_visual_theme()
        self.recargar_textos()

    def _configure_dock_behavior(self) -> None:
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.setMinimumWidth(self.MIN_DOCK_WIDTH)
        self.setMinimumHeight(self.MIN_DOCK_HEIGHT)

    def apply_visual_theme(self) -> None:
        if self._label is not None:
            refresh_panel_appearance(
                self._container, self._label, self.PANEL_ID, dock=self
            )
        elif hasattr(self._container, "apply_visual_theme"):
            self._container.apply_visual_theme(self.PANEL_ID)
            apply_dock_chrome(self, self.PANEL_ID)
        else:
            apply_panel_style(self._container, self.PANEL_ID)
            apply_dock_chrome(self, self.PANEL_ID)

    def recargar_textos(self) -> None:
        raise NotImplementedError
