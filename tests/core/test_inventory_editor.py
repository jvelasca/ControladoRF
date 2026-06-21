"""Tests de edición CRUD del inventario RF."""
from core.inventory_channel import channel_key, find_equipo_in_list
from core.inventory_editor import (
    create_equipo,
    delete_equipo,
    duplicate_equipo,
    get_equipos,
    update_equipo,
)
from core.project_model import Project


def _sample_project() -> Project:
    project = Project(name="Test")
    project.modules["inventario_rf"]["equipos"] = [
        {
            "source": "workbench",
            "workbench_channel_id": "dev-1",
            "channel_name": "Vocal",
            "channel_number": 1,
            "model": "ULXD1",
        }
    ]
    return project


def test_create_equipo_adds_manual_channel():
    project = Project()
    item = create_equipo(project)
    assert len(get_equipos(project)) == 1
    assert item["source"] == "manual"
    assert item["channel_key"].startswith("manual:")


def test_update_equipo_changes_fields():
    project = _sample_project()
    key = channel_key(project.modules["inventario_rf"]["equipos"][0])
    updated = update_equipo(
        project,
        key,
        {"channel_name": "Guitar", "channel_number": 5, "device_type": "iem"},
    )
    assert updated["channel_name"] == "Guitar"
    assert updated["channel_number"] == 5
    assert updated["device_type"] == "iem"
    assert channel_key(updated) == key


def test_duplicate_equipo_creates_new_key():
    project = _sample_project()
    key = channel_key(project.modules["inventario_rf"]["equipos"][0])
    copy_item = duplicate_equipo(project, key)
    assert copy_item is not None
    assert len(get_equipos(project)) == 2
    assert copy_item["channel_key"] != key
    assert "(copia)" in copy_item["channel_name"]
    assert "workbench_channel_id" not in copy_item


def test_delete_equipo_removes_item():
    project = _sample_project()
    key = channel_key(project.modules["inventario_rf"]["equipos"][0])
    assert delete_equipo(project, key) is True
    assert get_equipos(project) == []
    assert find_equipo_in_list(get_equipos(project), key) is None
