"""Tests de resolución de estilos de paneles CONTROLADORF."""
from gui.panel_styles import get_panel_colors, resolve_panel_palette_key


def test_resolve_module_panel_ids():
    assert resolve_panel_palette_key("inventario_rf_lista") == "panel1"
    assert resolve_panel_palette_key("coordinacion_propiedades") == "panel2"
    assert resolve_panel_palette_key("monitor_acciones") == "panel3"


def test_get_panel_colors_includes_text_muted():
    colors = get_panel_colors("inventario_rf_lista")
    assert "bg" in colors
    assert "fg" in colors
    assert "text_muted" in colors


def test_legacy_panel_ids_still_work():
    colors = get_panel_colors("panel2")
    assert colors["bg"] == get_panel_colors("inventario_rf_propiedades")["bg"]
