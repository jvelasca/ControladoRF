"""Gestión del ciclo de vida de proyectos CONTROLADORF."""
from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.project_io import (
    PROJECT_EXTENSION,
    ProjectIOError,
    load_project,
    normalize_project_path,
    save_project,
)
from core.project_model import DEFAULT_PROJECT_NAME, MODULE_IDS, Project
from core.project_ui_state import validate_module_ui_state
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_RECENT_PROJECTS = 10


class ProjectManager:
    """
    Orquesta el documento `.crf` separado del workspace local.

    - **Nombre del show** (`project.name`): título editable del evento (metadata).
    - **Fichero** (`file_path`): ruta del documento `.crf` en disco.
    """

    def __init__(
        self,
        *,
        store_get_config: Callable[[], Dict[str, Any]],
        store_set_config: Callable[[Dict[str, Any]], None],
        app_version: str = "0.1.0",
    ) -> None:
        self._store_get_config = store_get_config
        self._store_set_config = store_set_config
        self._app_version = app_version
        self._logger = get_logger(__name__)

        self._project: Optional[Project] = None
        self._file_path: Optional[str] = None
        self._dirty = False
        self._subscribers: List[Callable[[], None]] = []

    @property
    def project(self) -> Optional[Project]:
        return self._project

    @property
    def file_path(self) -> Optional[str]:
        return self._file_path

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    @property
    def has_saved_file(self) -> bool:
        return bool(self._file_path)

    @property
    def has_open_project(self) -> bool:
        return self._project is not None

    def subscribe(self, callback: Callable[[], None]) -> None:
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def _notify(self) -> None:
        for callback in list(self._subscribers):
            try:
                callback()
            except Exception as exc:
                self._logger.error("Error notificando cambio de proyecto: %s", exc)

    def mark_dirty(self) -> None:
        if not self._dirty:
            self._dirty = True
            self._notify()

    def clear_dirty(self) -> None:
        if self._dirty:
            self._dirty = False
            self._notify()

    def get_project_name(self) -> str:
        if self._project is None:
            return DEFAULT_PROJECT_NAME
        return self._project.name

    def get_file_basename(self) -> Optional[str]:
        if not self._file_path:
            return None
        return os.path.basename(self._file_path)

    def get_file_path(self) -> str:
        if not self._file_path:
            return ""
        return os.path.abspath(self._file_path)

    def get_show_label(self) -> str:
        """Nombre del show con asterisco si hay cambios sin guardar."""
        name = self.get_project_name()
        return f"{name}*" if self._dirty else name

    def new_project(self, name: str = DEFAULT_PROJECT_NAME) -> Project:
        self._project = Project.create_new(name=name, app_version=self._app_version)
        self._file_path = None
        self._dirty = True
        self._notify()
        return self._project

    def open_project(self, path: str) -> Project:
        resolved = os.path.abspath(path.strip())
        project = load_project(resolved)
        self._normalize_loaded_ui(project)
        self._project = project
        self._file_path = resolved
        self._dirty = False
        self._register_recent(resolved, project.name)
        self._persist_last_opened_project(resolved)
        self._notify()
        return project

    def save_project(self) -> bool:
        if self._project is None:
            return False
        if not self._file_path:
            return False
        path = normalize_project_path(self._file_path)
        save_project(path, self._project)
        self._file_path = path
        self._register_recent(path, self._project.name)
        self._persist_last_opened_project(path)
        self._dirty = False
        self._notify()
        return True

    def save_project_as(self, path: str) -> bool:
        if self._project is None:
            return False
        normalized = normalize_project_path(path)
        save_project(normalized, self._project)
        self._file_path = normalized
        self._register_recent(normalized, self._project.name)
        self._persist_last_opened_project(normalized)
        self._dirty = False
        self._notify()
        return True

    def export_project(self, path: str) -> bool:
        if self._project is None:
            return False
        normalized = normalize_project_path(path)
        save_project(normalized, self._project)
        return True

    def update_project_name(self, name: str) -> None:
        if self._project is None:
            return
        cleaned = name.strip() or DEFAULT_PROJECT_NAME
        if cleaned == self._project.name:
            return
        self._project.name = cleaned
        self.mark_dirty()

    def set_active_module(self, module_id: str, *, mark_dirty: bool = True) -> None:
        if self._project is None:
            return
        self._project.active_module = module_id
        self._project.ui["active_module"] = module_id
        if mark_dirty:
            self.mark_dirty()

    def get_active_module(self) -> str:
        if self._project is None:
            return MODULE_IDS[0]
        return self._project.ui.get("active_module") or self._project.active_module

    def get_module_ui_state(self, module_id: str) -> Dict[str, Any]:
        if self._project is None:
            return {}
        raw = copy.deepcopy(self._project.get_module_ui(module_id))
        return validate_module_ui_state(raw)

    def set_module_ui_state(
        self,
        module_id: str,
        state: Dict[str, Any],
        *,
        mark_dirty: bool = True,
    ) -> None:
        if self._project is None:
            return
        cleaned = validate_module_ui_state(state)
        self._project.get_module_ui(module_id).clear()
        self._project.get_module_ui(module_id).update(cleaned)
        if mark_dirty:
            self.mark_dirty()

    def replace_all_module_ui(
        self,
        modules_ui: Dict[str, Dict[str, Any]],
        *,
        active_module: Optional[str] = None,
    ) -> None:
        if self._project is None:
            return
        cleaned_modules = {
            module_id: validate_module_ui_state(modules_ui.get(module_id, {}))
            for module_id in MODULE_IDS
        }
        self._project.ui["modules"] = cleaned_modules
        if active_module in MODULE_IDS:
            self._project.active_module = active_module
            self._project.ui["active_module"] = active_module

    def get_last_opened_project_path(self) -> Optional[str]:
        """Ruta del último `.crf` abierto o guardado en la sesión anterior."""
        config = self._store_get_config()
        path = config.get("last_opened_project_path")
        if not isinstance(path, str):
            return None
        resolved = os.path.abspath(path.strip())
        if resolved.lower().endswith(PROJECT_EXTENSION) and os.path.isfile(resolved):
            return resolved
        return None

    def get_recent_projects(self) -> List[Dict[str, str]]:
        config = self._store_get_config()
        recent = config.get("recent_projects", [])
        if not isinstance(recent, list):
            return []
        valid: List[Dict[str, str]] = []
        for entry in recent:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            name = entry.get("name")
            if isinstance(path, str) and path.lower().endswith(".crf") and os.path.isfile(path):
                stem = Path(path).stem
                valid.append({
                    "path": path,
                    "name": stem or str(name or stem),
                })
        return valid[:MAX_RECENT_PROJECTS]

    def _register_recent(self, path: str, name: str) -> None:
        config = copy.deepcopy(self._store_get_config())
        recent = config.get("recent_projects", [])
        if not isinstance(recent, list):
            recent = []

        normalized = os.path.abspath(path)
        display_name = Path(normalized).stem or name
        recent = [r for r in recent if isinstance(r, dict) and r.get("path") != normalized]
        recent.insert(0, {"path": normalized, "name": display_name})
        config["recent_projects"] = recent[:MAX_RECENT_PROJECTS]
        self._store_set_config(config)

    def _persist_last_opened_project(self, path: str) -> None:
        config = copy.deepcopy(self._store_get_config())
        config["last_opened_project_path"] = os.path.abspath(path.strip())
        self._store_set_config(config)

    def _normalize_loaded_ui(self, project: Project) -> None:
        modules_ui = project.ui.setdefault("modules", {})
        for module_id in MODULE_IDS:
            raw = modules_ui.get(module_id, {})
            modules_ui[module_id] = validate_module_ui_state(raw)

    def close_project(self) -> None:
        self._project = None
        self._file_path = None
        self._dirty = False
        self._notify()

    def clear_last_opened_project(self) -> None:
        config = copy.deepcopy(self._store_get_config())
        if "last_opened_project_path" in config:
            del config["last_opened_project_path"]
            self._store_set_config(config)

    def try_save_on_exit(self) -> bool:
        if not self._dirty or self._project is None:
            return True
        if self._file_path:
            return self.save_project()
        return False
