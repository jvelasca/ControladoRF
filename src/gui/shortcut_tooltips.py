"""Utilidades para tooltips con atajos de teclado."""
from __future__ import annotations

from i18n.json_translation import tr


def tooltip_with_shortcut(description: str, shortcut: str) -> str:
    """Añade línea «Atajo: Fx» bajo la descripción."""
    text = str(description or "").strip()
    key = str(shortcut or "").strip()
    if not key:
        return text
    suffix = tr("tooltip_shortcut_suffix").format(shortcut=key)
    return f"{text}\n{suffix}" if text else suffix
