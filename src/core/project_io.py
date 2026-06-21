"""Lectura y escritura de ficheros de proyecto CONTROLADORF (.crf)."""
from __future__ import annotations

import json
import os
from typing import Tuple

from core.project_model import DEFAULT_PROJECT_NAME, Project
from utils.logger import get_logger

logger = get_logger(__name__)

PROJECT_EXTENSION = ".crf"
PROJECT_FILE_FILTER = f"Proyecto CONTROLADORF (*{PROJECT_EXTENSION})"


class ProjectIOError(Exception):
    """Error al leer o escribir un proyecto."""


def normalize_project_path(path: str) -> str:
    """Asegura extensión `.crf` en rutas de guardado."""
    normalized = os.path.abspath(path.strip())
    if normalized.lower().endswith(PROJECT_EXTENSION):
        return normalized
    return normalized + PROJECT_EXTENSION


def default_project_filename(name: str, *, export: bool = False) -> str:
    stem = (name or DEFAULT_PROJECT_NAME).rstrip("*").strip() or DEFAULT_PROJECT_NAME
    if export:
        stem = f"{stem}_export"
    return f"{stem}{PROJECT_EXTENSION}"


def load_project(path: str) -> Project:
    """Carga un proyecto `.crf` desde disco."""
    resolved = os.path.abspath(path.strip())
    if not resolved.lower().endswith(PROJECT_EXTENSION):
        raise ProjectIOError("El fichero debe tener extensión .crf")
    try:
        with open(resolved, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ProjectIOError("El fichero no contiene un objeto JSON válido.")
        return Project.from_dict(data)
    except ProjectIOError:
        raise
    except FileNotFoundError as exc:
        raise ProjectIOError(f"No se encontró el fichero: {resolved}") from exc
    except Exception as exc:
        logger.error("Error cargando proyecto %s: %s", resolved, exc)
        raise ProjectIOError(str(exc)) from exc


def save_project(path: str, project: Project) -> None:
    """Guarda un proyecto en disco de forma atómica."""
    path = normalize_project_path(path)
    project.touch_modified()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    temp_path = f"{path}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(project.to_dict(), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_path, path)
    except Exception as exc:
        logger.error("Error guardando proyecto %s: %s", path, exc)
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise ProjectIOError(str(exc)) from exc


def validate_project_file(path: str) -> Tuple[bool, str]:
    """Comprueba si un fichero parece un proyecto CONTROLADORF válido."""
    try:
        load_project(path)
        return True, ""
    except ProjectIOError as exc:
        return False, str(exc)
