"""Modelo de datos de un proyecto CONTROLADORF (.crf)."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

FORMAT_VERSION = "1.0"
DEFAULT_PROJECT_NAME = "Proyecto"

MODULE_IDS = ("inventario_rf", "coordinacion", "monitor")
PANEL_IDS = ("lista", "propiedades", "acciones")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _empty_modules() -> Dict[str, Dict[str, Any]]:
    return {
        "inventario_rf": {"equipos": []},
        "coordinacion": {},
        "monitor": {},
    }


def _empty_ui_modules() -> Dict[str, Dict[str, Any]]:
    return {module_id: {} for module_id in MODULE_IDS}


@dataclass
class Project:
    """Proyecto RF serializable a fichero `.crf`."""

    name: str = DEFAULT_PROJECT_NAME
    format_version: str = FORMAT_VERSION
    created_at: str = field(default_factory=_utc_now_iso)
    modified_at: str = field(default_factory=_utc_now_iso)
    app_version: str = "0.1.0"
    active_module: str = "inventario_rf"
    modules: Dict[str, Dict[str, Any]] = field(default_factory=_empty_modules)
    ui: Dict[str, Any] = field(default_factory=lambda: {
        "active_module": "inventario_rf",
        "modules": _empty_ui_modules(),
    })

    def touch_modified(self) -> None:
        self.modified_at = _utc_now_iso()

    def get_module_ui(self, module_id: str) -> Dict[str, Any]:
        modules_ui = self.ui.setdefault("modules", _empty_ui_modules())
        if module_id not in modules_ui:
            modules_ui[module_id] = {}
        return modules_ui[module_id]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format_version": self.format_version,
            "metadata": {
                "name": self.name,
                "created_at": self.created_at,
                "modified_at": self.modified_at,
                "app_version": self.app_version,
            },
            "modules": copy.deepcopy(self.modules),
            "ui": copy.deepcopy(self.ui),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Project:
        metadata = data.get("metadata") or {}
        ui = data.get("ui") or {}
        if "active_module" not in ui and "active_module" in data:
            ui["active_module"] = data["active_module"]
        ui.setdefault("active_module", "inventario_rf")
        ui.setdefault("modules", _empty_ui_modules())

        return cls(
            name=str(metadata.get("name") or DEFAULT_PROJECT_NAME),
            format_version=str(data.get("format_version") or FORMAT_VERSION),
            created_at=str(metadata.get("created_at") or _utc_now_iso()),
            modified_at=str(metadata.get("modified_at") or _utc_now_iso()),
            app_version=str(metadata.get("app_version") or "0.1.0"),
            active_module=str(ui.get("active_module") or "inventario_rf"),
            modules=copy.deepcopy(data.get("modules") or _empty_modules()),
            ui=copy.deepcopy(ui),
        )

    @classmethod
    def create_new(cls, name: str = DEFAULT_PROJECT_NAME, app_version: str = "0.1.0") -> Project:
        now = _utc_now_iso()
        return cls(
            name=name,
            created_at=now,
            modified_at=now,
            app_version=app_version,
        )
