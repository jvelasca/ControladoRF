"""Rutas de recursos empaquetados y datos de usuario (desarrollo vs PyInstaller)."""
from __future__ import annotations

import sys
from pathlib import Path

_APP_FOLDER_NAME = "ControladoRF"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def bundle_path(*parts: str) -> Path:
    return bundle_root().joinpath(*parts)


def install_dir() -> Path:
    """Carpeta del .exe empaquetado o raíz del repo en desarrollo."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def project_root() -> Path:
    if is_frozen():
        return bundle_root()
    return Path(__file__).resolve().parent.parent


def docs_dir() -> Path:
    if is_frozen():
        return bundle_path("docs")
    return project_root() / "docs"


def user_data_root() -> Path:
    root = Path.home() / "Documents" / _APP_FOLDER_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def workspace_data_dir() -> Path:
    if is_frozen():
        path = user_data_root() / "workspace" / "data"
    else:
        path = bundle_root() / "workspace" / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    if is_frozen():
        path = user_data_root() / "logs"
    else:
        path = project_root() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
