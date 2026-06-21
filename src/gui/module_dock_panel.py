"""Panel dock genérico para un módulo CONTROLADORF."""
from gui.dock_panel_base import BaseDockPanel
from i18n.json_translation import tr


class ModuleDockPanel(BaseDockPanel):
    """QDockWidget asociado a un módulo y rol de panel (lista, propiedades, acciones)."""

    def __init__(
        self,
        module_id: str,
        panel_id: str,
        *,
        content_widget=None,
        parent=None,
    ) -> None:
        self.module_id = module_id
        self.panel_id = panel_id
        self.PANEL_ID = f"{module_id}_{panel_id}"
        super().__init__(parent, content_widget=content_widget)

    def recargar_textos(self) -> None:
        title_key = f"{self.module_id}_panel_{self.panel_id}_title"
        self.setWindowTitle(tr(title_key))
        if hasattr(self._container, "recargar_textos"):
            self._container.recargar_textos()
