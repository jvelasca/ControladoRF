"""Rutas de logs de supervisión — carpeta de sesiones y exportación.

Resolución de rutas (prioridad):

1. Carpeta personalizada en ``SupervisionSettings.log_directory`` / ``log_export_directory``.
2. ``{proyecto}/logs/supervision/`` junto al fichero ``.crf``.
3. Fallback en Documents vía ``export_directory(EXPORT_ALARM_CSV)``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.monitor.monitor_export_paths import EXPORT_ALARM_CSV, export_directory
from core.monitor.supervision.alarm_log_repository import _safe_filename
from core.monitor.supervision.supervision_models import SupervisionState


def resolve_supervision_log_directory(
    state: SupervisionState,
    *,
    project_file_path: Optional[str] = None,
    project_name: str = "",
) -> Path:
    """Carpeta base donde se crean subcarpetas por sesión REC."""
    custom = str(state.settings.log_directory or "").strip()
    if custom:
        path = Path(custom).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path
    if project_file_path:
        base = Path(project_file_path).expanduser().parent / "logs" / "supervision"
        base.mkdir(parents=True, exist_ok=True)
        return base
    safe = _safe_filename(project_name or "session")
    fallback = export_directory(EXPORT_ALARM_CSV) / "supervision" / safe
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def resolve_supervision_log_export_directory(
    state: SupervisionState,
    *,
    project_file_path: Optional[str] = None,
    project_name: str = "",
) -> Path:
    """Destino por defecto al exportar logs desde menú contextual."""
    custom = str(state.settings.log_export_directory or "").strip()
    if custom:
        path = Path(custom).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path
    return resolve_supervision_log_directory(
        state,
        project_file_path=project_file_path,
        project_name=project_name,
    )
