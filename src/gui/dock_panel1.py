"""Primer panel acoplable: CRUD de items (superior izquierda)."""
from gui.dock_panel_base import BaseDockPanel
from gui.items_panel_widget import ItemsPanelWidget
from i18n.json_translation import tr


class DockPanel1(BaseDockPanel):
    PANEL_ID = "panel1"

    def __init__(self, parent=None, app_services=None) -> None:
        self._items_widget = ItemsPanelWidget(app_services, parent)
        super().__init__(parent, content_widget=self._items_widget)

    def recargar_textos(self) -> None:
        self.setWindowTitle(tr("panel1_title"))
        self._items_widget.recargar_textos()

    def set_app_services(self, app_services) -> None:
        self._items_widget.set_app_services(app_services)
