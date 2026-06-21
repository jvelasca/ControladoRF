"""Segundo panel acoplable: lateral derecho."""
from gui.dock_panel_base import BaseDockPanel
from i18n.json_translation import tr


class DockPanel2(BaseDockPanel):
    PANEL_ID = "panel2"

    def recargar_textos(self) -> None:
        self.setWindowTitle(tr("panel2_title"))
        self._label.setText(tr("panel2_content"))
