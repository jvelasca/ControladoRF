"""Rutas de guardado recordadas para exportación Monitor (por tipo de fichero)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

EXPORT_TRACE_CSV = "monitor_trace_csv"
EXPORT_TRACE_CSV_WORKBENCH = "monitor_trace_csv_workbench"
EXPORT_TRACE_CSV_SOUNDBASE = "monitor_trace_csv_soundbase"
EXPORT_ALARM_CSV = "monitor_alarm_csv"
EXPORT_ALARM_TXT = "monitor_alarm_txt"
EXPORT_PNG_SPECTRUM = "monitor_png_spectrum"
EXPORT_PNG_WATERFALL = "monitor_png_waterfall"

_CONFIG_KEY = "monitor_export_dirs"

_get_config: Optional[Callable[[], Dict[str, Any]]] = None
_set_config: Optional[Callable[[Dict[str, Any]], None]] = None
_default_dir_fn: Optional[Callable[[], str]] = None


def configure_monitor_export_paths(
    store_get_config: Callable[[], Dict[str, Any]],
    store_set_config: Callable[[Dict[str, Any]], None],
    *,
    default_dir: Callable[[], str],
) -> None:
    global _get_config, _set_config, _default_dir_fn
    _get_config = store_get_config
    _set_config = store_set_config
    _default_dir_fn = default_dir


def _fallback_dir() -> Path:
    if _default_dir_fn is not None:
        try:
            return Path(_default_dir_fn()).expanduser()
        except OSError:
            pass
    return Path.home() / "Documents"


def export_directory(export_type: str) -> Path:
    """Directorio inicial para un tipo de exportación."""
    if _get_config is not None:
        config = _get_config() or {}
        dirs = config.get(_CONFIG_KEY) or {}
        if isinstance(dirs, dict):
            raw = dirs.get(export_type, "")
            if raw:
                path = Path(str(raw)).expanduser()
                if path.is_dir():
                    return path
                parent = path.parent
                if parent.is_dir():
                    return parent
    return _fallback_dir()


def resolve_save_path(export_type: str, filename: str) -> str:
    """Ruta completa sugerida al abrir el diálogo de guardado."""
    safe_name = Path(filename).name or "export.dat"
    return str(export_directory(export_type) / safe_name)


def remember_save_path(export_type: str, saved_path: str) -> None:
    """Persiste la carpeta tras una exportación correcta."""
    if _get_config is None or _set_config is None or not saved_path:
        return
    folder = Path(saved_path).expanduser().parent
    if not folder.is_dir():
        return
    config = dict(_get_config() or {})
    dirs = dict(config.get(_CONFIG_KEY) or {})
    dirs[export_type] = str(folder)
    config[_CONFIG_KEY] = dirs
    _set_config(config)
