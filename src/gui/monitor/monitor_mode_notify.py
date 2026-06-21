"""Formatea avisos de restricción por modo Analizador/SDR."""
from __future__ import annotations

from core.monitor.monitor_mode_guard import ModeRestriction
from i18n.json_translation import tr


def format_mode_restriction(restriction: ModeRestriction) -> str:
    fmt: dict[str, float] = {}
    if restriction.max_mhz is not None:
        fmt["max_mhz"] = restriction.max_mhz
    return tr(restriction.i18n_key).format(**fmt)
