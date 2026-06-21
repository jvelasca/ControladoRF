"""Tests de sincronización inventario ↔ SQLite."""
from __future__ import annotations

from core.project_model import Project
from core.services.inventory_service import InventoryService
from db.config import DatabaseConfig
from db.connection import Database
from db.migration import ensure_migrations
from db.repositories.inventory_channel_repository import InventoryChannelRepository
from db.repositories.inventory_scope_metadata_repository import InventoryScopeMetadataRepository


def _service(tmp_path):
    db_path = tmp_path / "test.db"
    database = Database(DatabaseConfig(path=db_path))
    database.connect()
    ensure_migrations(database)
    repo = InventoryChannelRepository(database)
    scope = InventoryScopeMetadataRepository(database)
    return InventoryService(repo, scope), database


def test_sync_project_persists_channels(tmp_path):
    service, database = _service(tmp_path)
    project = Project.create_new("Show test")
    project.modules["inventario_rf"]["equipos"] = [
        {
            "workbench_channel_id": "ch-1",
            "channel_name": "Vocal",
            "channel_number": 1,
            "model": "ULXD1",
        }
    ]

    count = service.sync_project(project, str(tmp_path / "show.crf"))
    assert count == 1

    channels = service.list_channels(project, str(tmp_path / "show.crf"))
    assert len(channels) == 1
    assert channels[0].channel_name == "Vocal"

    resolved = service.resolve_equipo(
        project,
        {"workbench_channel_id": "ch-1"},
        file_path=str(tmp_path / "show.crf"),
    )
    assert resolved["channel_name"] == "Vocal"
    assert resolved["db_id"] == channels[0].id

    database.close()


def test_sync_replaces_previous_snapshot(tmp_path):
    service, database = _service(tmp_path)
    project = Project.create_new("Show")
    path = str(tmp_path / "show.crf")
    project.modules["inventario_rf"]["equipos"] = [
        {"workbench_channel_id": "a", "channel_name": "A"},
    ]
    service.sync_project(project, path)

    project.modules["inventario_rf"]["equipos"] = [
        {"workbench_channel_id": "b", "channel_name": "B"},
    ]
    service.sync_project(project, path)

    channels = service.list_channels(project, path)
    assert len(channels) == 1
    assert channels[0].channel_key == "b"

    database.close()
