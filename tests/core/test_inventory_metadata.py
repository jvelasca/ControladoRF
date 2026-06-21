"""Tests de metadatos del inventario RF."""
from core.inventory_editor import create_equipo, delete_equipo, update_equipo
from core.inventory_exceptions import InventoryLockedError
from core.inventory_metadata import (
    get_group_metadata,
    get_list_metadata,
    is_equipo_locked,
    update_group_metadata,
    update_list_metadata,
)
from core.project_model import Project


def test_update_list_metadata():
    project = Project()
    meta = update_list_metadata(project, {"notes": "Show notes", "color": "#FF0000", "locked": True})
    assert meta["notes"] == "Show notes"
    assert meta["color"] == "#FF0000"
    assert meta["locked"] is True
    assert get_list_metadata(project)["notes"] == "Show notes"


def test_group_metadata_and_lock_inheritance():
    project = Project()
    project.modules["inventario_rf"]["equipos"] = [
        {"channel_key": "manual:1", "channel_name": "A", "zone": "Main", "locked": False}
    ]
    update_group_metadata(project, "zone", "Main", {"locked": True})
    item = project.modules["inventario_rf"]["equipos"][0]
    assert is_equipo_locked(project, item)


def test_locked_channel_rejects_update():
    project = Project()
    item = create_equipo(project)
    key = item["channel_key"]
    update_equipo(project, key, {"locked": True})
    try:
        update_equipo(project, key, {"channel_name": "X"})
        raised = False
    except InventoryLockedError:
        raised = True
    assert raised


def test_unlock_direct_channel_lock():
    project = Project()
    item = create_equipo(project)
    key = item["channel_key"]
    update_equipo(project, key, {"locked": True})
    updated = update_equipo(project, key, {"locked": False, "channel_name": "Libre"})
    assert updated["locked"] is False
    assert updated["channel_name"] == "Libre"


def test_list_lock_blocks_create():
    project = Project()
    update_list_metadata(project, {"locked": True})
    try:
        create_equipo(project)
        raised = False
    except InventoryLockedError:
        raised = True
    assert raised
