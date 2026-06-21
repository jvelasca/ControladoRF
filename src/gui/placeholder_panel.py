"""Panel placeholder reutilizable para módulos en desarrollo."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.panel_styles import apply_panel_style, get_panel_colors
from i18n.json_translation import tr


class PlaceholderPanelWidget(QWidget):
    """Contenido provisional hasta implementar la funcionalidad del módulo."""

    def __init__(
        self,
        module_id: str,
        panel_id: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._module_id = module_id
        self._panel_id = panel_id
        self._style_key = f"{module_id}_{panel_id}"
        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addStretch(1)
        layout.addWidget(self._label)
        layout.addStretch(1)
        self.recargar_textos()
        self.apply_visual_theme()

    def apply_visual_theme(self, panel_id: str | None = None) -> None:
        key = panel_id or self._style_key
        apply_panel_style(self, key)
        colors = get_panel_colors(key)
        self._label.setStyleSheet(f"color: {colors['text_muted']};")

    def recargar_textos(self) -> None:
        key = f"{self._module_id}_panel_{self._panel_id}_placeholder"
        self._label.setText(tr(key))
