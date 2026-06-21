"""Fixtures para tests GUI con pytest-qt."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from workspace.store import WorkspaceStore

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from db import DatabaseService
from core.project_manager import ProjectManager
from workspace.controller import WorkspaceController


@pytest.fixture
def app_context(isolated_store, qapp):
    controller = WorkspaceController(isolated_store)
    config: dict = {"language": "es_ES", "recent_projects": []}

    database_service = DatabaseService(
        data_dir=isolated_store.data_dir,
        store_get_config=isolated_store.get_config,
        store_set_config=isolated_store.set_config,
    )
    database_service.startup()

    project_manager = ProjectManager(
        store_get_config=lambda: config,
        store_set_config=lambda value: config.update(value),
        app_version="0.1.0-test",
    )

    yield {
        "controller": controller,
        "database_service": database_service,
        "project_manager": project_manager,
    }

    database_service.close()


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def isolated_store(tmp_path):
    data_dir = tmp_path / "workspace_data"
    data_dir.mkdir()
    return WorkspaceStore(str(data_dir))


def close_window(window) -> None:
    """Cierra la ventana evitando diálogos modales de cambios sin guardar."""
    if window._project_manager:
        window._project_manager.clear_dirty()
    window._closing = True
    window.close()
