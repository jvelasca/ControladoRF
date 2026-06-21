"""Tests de exportación de la lista de inventario RF."""
import json
from pathlib import Path

import pytest

from core.inventory_export import (
    EXPORT_FORMAT_JSON,
    EXPORT_FORMAT_PDF,
    InventoryExportError,
    build_inventory_list_export,
    default_export_filename,
    export_inventory_csv,
    export_inventory_json,
)
from core.project_model import Project


def _sample_project() -> Project:
    project = Project(name="Show Demo")
    project.modules["inventario_rf"]["equipos"] = [
        {
            "source": "manual",
            "channel_key": "manual:abc",
            "channel_number": 1,
            "channel_name": "Vocal",
            "frequency_mhz": 470.125,
            "band": "UHF",
            "zone": "Escenario",
            "network": "A",
            "model": "ULXD1",
            "series": "G50",
            "manufacturer": "Shure",
            "device_name": "HH-1",
            "device_type": "microphone",
            "coordination_include": True,
            "coordination_active": False,
            "notes": "Principal",
            "color": "#FFAA00",
            "locked": True,
        }
    ]
    project.modules["inventario_rf"]["list_metadata"] = {
        "notes": "Lista del show",
        "color": "#112233",
        "locked": False,
    }
    return project


def test_build_inventory_list_export_contains_list_metadata_and_channels():
    document = build_inventory_list_export(_sample_project(), project_name="Show Demo")
    assert document["project_name"] == "Show Demo"
    assert document["list"]["channel_count"] == 1
    assert document["list"]["metadata"]["notes"] == "Lista del show"
    channel = document["list"]["channels"][0]
    assert channel["channel_name"] == "Vocal"
    assert channel["locked"] is True
    assert channel["channel_key"] == "manual:abc"


def test_export_inventory_json_writes_utf8_file(tmp_path: Path):
    document = build_inventory_list_export(_sample_project())
    target = tmp_path / "lista.json"
    export_inventory_json(document, target)
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded["list"]["channel_count"] == 1


def test_export_inventory_csv_uses_semicolon_and_bom(tmp_path: Path):
    document = build_inventory_list_export(_sample_project())
    target = tmp_path / "lista.csv"
    export_inventory_csv(document, target, field_labels={"channel_name": "Nombre"})
    raw = target.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert "Nombre" in text.splitlines()[0]
    assert "Vocal" in text


def test_default_export_filename_sanitizes_project_name():
    assert default_export_filename("Show / Demo", EXPORT_FORMAT_PDF).endswith(".pdf")
    assert default_export_filename("", EXPORT_FORMAT_JSON) == "inventario.json"


def test_export_inventory_json_raises_on_invalid_path(tmp_path: Path):
    document = build_inventory_list_export(_sample_project())
    target = tmp_path / "folder"
    target.mkdir()
    with pytest.raises(InventoryExportError):
        export_inventory_json(document, target)
