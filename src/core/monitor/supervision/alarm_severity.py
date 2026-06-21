"""Severidades de alarma RF — nomenclatura canónica en español.

Prioridad (mayor número = más grave en evaluación):
  1 critica · 2 menor · 3 aviso · 4 comentario

Las claves i18n usan el mismo identificador; en inglés se traducen en en.json.
"""
from __future__ import annotations

from typing import Literal, Optional

AlarmSeverityLevel = Literal["critica", "menor", "aviso", "comentario"]

ChannelHealthLevel = Literal["ok", "comentario", "aviso", "menor", "critica", "unknown"]

ALL_ALARM_SEVERITIES: tuple[AlarmSeverityLevel, ...] = (
    "critica",
    "menor",
    "aviso",
    "comentario",
)

# Columnas del editor (orden visual: más grave → informativo)
EDITOR_SEVERITY_COLUMNS: tuple[AlarmSeverityLevel, ...] = (
    "critica",
    "menor",
    "aviso",
    "comentario",
)

SEVERITY_RANK: dict[str, int] = {
    "ok": 0,
    "unknown": 0,
    "comentario": 1,
    "aviso": 2,
    "menor": 3,
    "critica": 4,
}

SEVERITY_I18N_KEY: dict[AlarmSeverityLevel, str] = {
    "critica": "monitor_severity_critica",
    "menor": "monitor_severity_menor",
    "aviso": "monitor_severity_aviso",
    "comentario": "monitor_severity_comentario",
}

# Compatibilidad v2 (warning/critical) → v3
LEGACY_SEVERITY_TO_CANONICAL: dict[str, AlarmSeverityLevel] = {
    "critical": "critica",
    "critica": "critica",
    "warning": "aviso",
    "aviso": "aviso",
    "menor": "menor",
    "comentario": "comentario",
    "info": "comentario",
}

CANONICAL_TO_LEGACY_EVENT: dict[AlarmSeverityLevel, str] = {
    "critica": "critical",
    "menor": "menor",
    "aviso": "warning",
    "comentario": "comentario",
}


def normalize_severity(value: str | None) -> Optional[AlarmSeverityLevel]:
    key = str(value or "").strip().lower()
    if not key:
        return None
    mapped = LEGACY_SEVERITY_TO_CANONICAL.get(key)
    if mapped in ALL_ALARM_SEVERITIES:
        return mapped
    return None


def health_from_severities(*values: ChannelHealthLevel) -> ChannelHealthLevel:
    best: ChannelHealthLevel = "ok"
    for health in values:
        if health == "unknown" and best == "ok":
            best = "unknown"
        elif SEVERITY_RANK.get(health, 0) > SEVERITY_RANK.get(best, 0):
            best = health
    return best


def is_actionable_severity(severity: AlarmSeverityLevel) -> bool:
    """Comentario no entra en latch/ack activo."""
    return severity in ("critica", "menor", "aviso")
