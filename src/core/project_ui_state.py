"""Validación del estado de UI persistido en el .crf."""

from __future__ import annotations



from typing import Any, Dict, List


from core.project_model import PANEL_IDS



ALLOWED_UI_KEYS = frozenset({

    "splitter_main",

    "splitter_left",

    "panel_visibility",

    "maximized_panel",

    "pre_maximize",

    "left_column_visible",

    "panel_content",

})



def _clean_monitor_persisted(monitor: Dict[str, Any]) -> Dict[str, Any]:
    """Conserva escalares y el banco de marcadores M1–M10."""
    cleaned: Dict[str, Any] = {
        str(key): value
        for key, value in monitor.items()
        if isinstance(key, str) and isinstance(value, (int, float, str, bool))
    }
    markers = monitor.get("markers")
    if not isinstance(markers, list):
        return cleaned
    cleaned_markers: List[Dict[str, Any]] = []
    for item in markers:
        if not isinstance(item, dict):
            continue
        marker_row = {
            str(key): value
            for key, value in item.items()
            if isinstance(key, str) and isinstance(value, (int, float, str, bool))
        }
        if marker_row:
            cleaned_markers.append(marker_row)
    if cleaned_markers:
        cleaned["markers"] = cleaned_markers
    return cleaned





def validate_module_ui_state(config: Dict[str, Any] | None) -> Dict[str, Any]:

    """Normaliza el bloque ui de un módulo; descarta claves desconocidas."""

    if not isinstance(config, dict):

        return {}



    state: Dict[str, Any] = {

        key: value for key, value in config.items() if key in ALLOWED_UI_KEYS

    }



    visibility = state.get("panel_visibility")

    if isinstance(visibility, dict):

        cleaned = {

            panel_id: bool(visibility.get(panel_id, True)) for panel_id in PANEL_IDS

        }

        if not any(cleaned.values()):

            cleaned = {panel_id: True for panel_id in PANEL_IDS}

        state["panel_visibility"] = cleaned



    maximized = state.get("maximized_panel")

    if maximized is not None and maximized not in PANEL_IDS:

        state.pop("maximized_panel", None)

        state.pop("pre_maximize", None)



    for splitter_key in ("splitter_main", "splitter_left"):
        sizes = state.get(splitter_key)
        if sizes is None:
            continue
        if (
            isinstance(sizes, list)
            and len(sizes) == 2
            and all(isinstance(value, int) for value in sizes)
        ):
            state[splitter_key] = [int(value) for value in sizes]
        else:
            state.pop(splitter_key, None)



    panel_content = state.get("panel_content")

    if isinstance(panel_content, dict):
        lista = panel_content.get("lista")
        monitor = panel_content.get("monitor")
        if isinstance(lista, dict):
            header = lista.get("table_header")
            if isinstance(header, str):
                cleaned_lista: Dict[str, Any] = {"table_header": header}
                alignment = lista.get("table_text_alignment")
                if isinstance(alignment, str):
                    cleaned_lista["table_text_alignment"] = alignment
                state["panel_content"] = {"lista": cleaned_lista}
            else:
                state.pop("panel_content", None)
        elif isinstance(monitor, dict):
            cleaned_monitor = _clean_monitor_persisted(monitor)
            if cleaned_monitor:
                state["panel_content"] = {"monitor": cleaned_monitor}
            else:
                state.pop("panel_content", None)
        else:
            state.pop("panel_content", None)



    return state

