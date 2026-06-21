"""Tests de identidad de canales RF."""
from core.inventory_catalog import DEVICE_TYPE_MICROPHONE
from core.inventory_channel import (
    channel_key,
    find_equipo_in_list,
    normalize_equipo,
    project_storage_key,
)
from core.project_model import Project


def test_channel_key_prefers_workbench_id():
    item = {"workbench_channel_id": "dev-1-0", "channel_name": "Vocal"}
    assert channel_key(item) == "dev-1-0"


def test_find_equipo_in_list():
    equipos = [
        {"workbench_channel_id": "a", "channel_name": "A"},
        {"workbench_channel_id": "b", "channel_name": "B"},
    ]
    found = find_equipo_in_list(equipos, "b")
    assert found is not None
    assert found["channel_name"] == "B"


def test_normalize_equipo_sets_channel_key():
    item = normalize_equipo({"model": "ULXD1", "channel_number": 3})
    assert item["channel_key"]
    assert item["device_type"] == DEVICE_TYPE_MICROPHONE


def test_project_storage_key_uses_path():
    assert project_storage_key("C:/Shows/demo.crf") == "c:/shows/demo.crf"


def test_project_storage_key_unsaved():
    assert project_storage_key(None, "Concierto").startswith("unsaved:")
