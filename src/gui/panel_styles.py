"""
Estilos visuales de paneles acoplables, adaptados al modo claro/oscuro del sistema operativo.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDockWidget, QLabel, QVBoxLayout, QWidget

from utils.theme_utils import is_dark_mode

# Paletas inspiradas en Visual Studio: tonos neutros diferenciados por zona.
_PANEL_PALETTES = {
    "light": {
        "panel1": {
            "bg": "#FFFFFF",
            "fg": "#1E1E1E",
            "text_muted": "#5A5A5A",
            "border": "#CCCEDB",
        },
        "panel2": {
            "bg": "#F3F3F3",
            "fg": "#1E1E1E",
            "text_muted": "#5A5A5A",
            "border": "#CCCEDB",
        },
        "panel3": {
            "bg": "#ECECEC",
            "fg": "#1E1E1E",
            "text_muted": "#5A5A5A",
            "border": "#CCCEDB",
        },
    },
    "dark": {
        "panel1": {
            "bg": "#1E1E1E",
            "fg": "#D4D4D4",
            "text_muted": "#9DA0A6",
            "border": "#3F3F46",
        },
        "panel2": {
            "bg": "#252526",
            "fg": "#CCCCCC",
            "text_muted": "#9DA0A6",
            "border": "#3F3F46",
        },
        "panel3": {
            "bg": "#2D2D30",
            "fg": "#CCCCCC",
            "text_muted": "#9DA0A6",
            "border": "#3F3F46",
        },
    },
}

# Roles de panel CONTROLADORF → paleta legacy panel1/2/3
_PANEL_ROLE_ALIASES = {
    "lista": "panel1",
    "propiedades": "panel2",
    "acciones": "panel3",
    "panel1": "panel1",
    "panel2": "panel2",
    "panel3": "panel3",
}


def current_theme_mode() -> str:
    return "dark" if is_dark_mode() else "light"


def resolve_panel_palette_key(panel_id: str) -> str:
    """
    Resuelve ids como ``inventario_rf_lista`` al tono panel1/2/3.
    """
    mode = current_theme_mode()
    palettes = _PANEL_PALETTES[mode]
    if panel_id in palettes:
        return panel_id

    if panel_id in _PANEL_ROLE_ALIASES:
        return _PANEL_ROLE_ALIASES[panel_id]

    if "_" in panel_id:
        role = panel_id.rsplit("_", 1)[-1]
        if role in _PANEL_ROLE_ALIASES:
            return _PANEL_ROLE_ALIASES[role]

    return "panel1"


def get_panel_colors(panel_id: str) -> dict:
    mode = current_theme_mode()
    palette_key = resolve_panel_palette_key(panel_id)
    return dict(_PANEL_PALETTES[mode][palette_key])


def apply_panel_style(container: QWidget, panel_id: str) -> None:
    colors = get_panel_colors(panel_id)
    container.setStyleSheet(
        f"background-color: {colors['bg']};"
        f"border-top: 1px solid {colors['border']};"
    )


def apply_panel_frame(frame: QWidget, panel_id: str) -> None:
    colors = get_panel_colors(panel_id)
    frame.setStyleSheet(
        f"ModulePanelFrame {{ background-color: {colors['bg']}; border: 1px solid {colors['border']}; }}"
    )


def apply_panel_title(label: QLabel, panel_id: str) -> None:
    colors = get_panel_colors(panel_id)
    label.setStyleSheet(
        f"color: {colors['fg']};"
        "font-size: 12px;"
        "font-weight: 600;"
        "padding: 0;"
        "background: transparent;"
    )


def apply_panel_header_bar(header: QWidget, panel_id: str, title: QLabel) -> None:
    colors = get_panel_colors(panel_id)
    apply_panel_title(title, panel_id)
    header.setStyleSheet(
        f"PanelHeaderBar {{ background-color: {colors['bg']}; border-bottom: 1px solid {colors['border']}; }}"
        f"QToolButton#PanelHeaderCloseButton, QToolButton#PanelHeaderMaximizeButton {{"
        f"  background: transparent; border: none; border-radius: 3px; color: {colors['text_muted']};"
        f"}}"
        f"QToolButton#PanelHeaderCloseButton:hover, QToolButton#PanelHeaderMaximizeButton:hover {{"
        f"  background-color: {colors['border']}; color: {colors['fg']};"
        f"}}"
        f"QToolButton#PanelHeaderCloseButton:pressed, QToolButton#PanelHeaderMaximizeButton:pressed {{"
        f"  background-color: {colors['text_muted']};"
        f"}}"
    )


def apply_panel_label_style(label: QLabel, panel_id: str) -> None:
    colors = get_panel_colors(panel_id)
    label.setStyleSheet(
        f"color: {colors['fg']};"
        "font-size: 14px;"
        "font-weight: 400;"
        "padding: 20px;"
        "background: transparent;"
    )
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)


def apply_dock_chrome(dock: QDockWidget, panel_id: str) -> None:
    colors = get_panel_colors(panel_id)
    # Título del dock lo estiliza app_chrome_styles; aquí solo el contenido
    dock.setStyleSheet(
        "QDockWidget::widget {"
        f"  background-color: {colors['bg']};"
        "  border: none;"
        "}"
    )


def refresh_panel_appearance(
    container: QWidget,
    label: QLabel,
    panel_id: str,
    dock: QDockWidget | None = None,
) -> None:
    apply_panel_style(container, panel_id)
    apply_panel_label_style(label, panel_id)
    if dock is not None:
        apply_dock_chrome(dock, panel_id)


def build_panel_content(panel_id: str, text: str) -> tuple[QWidget, QLabel]:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    label = QLabel(text)
    layout.addWidget(label, stretch=1)
    apply_panel_style(container, panel_id)
    apply_panel_label_style(label, panel_id)
    return container, label
