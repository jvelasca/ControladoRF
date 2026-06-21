"""
workspace_io.py
---------------
Importación y exportación de workspaces en formato JSON.
"""
import json
from typing import Any, Dict

from workspace.model import Workspace


class WorkspaceIOError(Exception):
    """Error de validación o lectura/escritura de ficheros de workspace."""


def export_workspace_to_file(workspace: Workspace, path: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(workspace.to_dict(), handle, indent=2, ensure_ascii=False)


def load_workspace_from_file(path: str) -> Workspace:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkspaceIOError(str(exc)) from exc

    if not isinstance(data, dict) or "name" not in data:
        raise WorkspaceIOError("El fichero no contiene un workspace válido.")

    workspace = Workspace.from_dict(data)
    if workspace.name == "Invalid":
        raise WorkspaceIOError("Los datos del workspace no son válidos.")
    return workspace


def merge_workspace_into_default(source: Workspace, default: Workspace) -> Workspace:
    """Fusiona la configuración importada en el workspace Default."""
    merged_config: Dict[str, Any] = dict(default.config)
    merged_config.update(source.config)
    return Workspace(
        name=default.name,
        description=default.description or source.description,
        config=merged_config,
        is_default=True,
    )
