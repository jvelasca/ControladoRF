"""Tercer panel acoplable: zona inferior izquierda."""
from gui.dock_panel_base import BaseDockPanel
from i18n.json_translation import tr


class DockPanel3(BaseDockPanel):
    PANEL_ID = "panel3"

    def recargar_textos(self) -> None:
        self.setWindowTitle(tr("panel3_title"))
        self._label.setText(tr("panel3_content"))
