"""Tests del parser Shure Wireless Workbench (.shw)."""
from pathlib import Path

import pytest

from core.project_model import Project
from importers.workbench_parser import (
    WorkbenchImportError,
    apply_workbench_coordination_to_project,
    apply_workbench_inventory_to_project,
    frequency_khz_to_mhz,
    parse_workbench_show,
)

EXAMPLE_SHW = (
    Path(__file__).resolve().parents[1] / "auxiliares" / "ejempo impor workbench.shw"
)


@pytest.fixture
def example_path() -> Path:
    if not EXAMPLE_SHW.is_file():
        pytest.skip(f"Fichero de ejemplo no encontrado: {EXAMPLE_SHW}")
    return EXAMPLE_SHW


def test_frequency_khz_to_mhz():
    assert frequency_khz_to_mhz(472825) == 472.825
    assert frequency_khz_to_mhz(658175) == 658.175
    assert frequency_khz_to_mhz(None) is None


def test_parse_example_show_metadata(example_path):
    show = parse_workbench_show(example_path)
    assert show.info.name == "Concierto Madrid"
    assert show.info.customer == "GAIN Audio"
    assert show.info.contact.name == "J. Alberto Velasco"
    assert show.workbench_version == "7.8.1.56"
    assert show.has_coordination is True
    assert show.has_monitoring is True


def test_parse_example_inventory(example_path):
    show = parse_workbench_show(example_path)
    assert len(show.devices) == 14
    assert show.channel_count == 24

    models = {device.model for device in show.devices}
    assert "ULXD4D" in models
    assert "SR 2050" in models

    first_channel = show.devices[0].channels[0]
    assert first_channel.name == "Voz GTR"
    assert first_channel.frequency_mhz == pytest.approx(658.175)


def test_apply_to_project(example_path):
    show = parse_workbench_show(example_path)
    project = Project.create_new("Proyecto")
    apply_workbench_inventory_to_project(project, show)

    assert project.name == "Concierto Madrid"
    equipos = project.modules["inventario_rf"]["equipos"]
    assert len(equipos) == 24
    assert equipos[0]["source"] == "workbench"
    assert equipos[0]["frequency_mhz"] == pytest.approx(658.175)

    from collections import Counter

    types = Counter(item["device_type"] for item in equipos)
    assert types["microphone"] == 12
    assert types["iem"] == 12
    assert set(types.keys()) == {"microphone", "iem"}


def test_rejects_non_shw_extension(tmp_path):
    path = tmp_path / "bad.xml"
    path.write_text("<show></show>", encoding="utf-8")
    with pytest.raises(WorkbenchImportError):
        parse_workbench_show(path)


def test_parse_coordination_summary(example_path):
    show = parse_workbench_show(example_path)
    assert show.coordination is not None
    coord = show.coordination
    assert len(coord.channels) >= 20
    assert coord.included_channel_count >= 20
    assert coord.assigned_frequency_count >= 20
    assert coord.scan_file_name == "Traza 03.csv"
    assert coord.exclusion_range_count > 0


def test_apply_coordination_to_project(example_path):
    show = parse_workbench_show(example_path)
    project = Project.create_new("Proyecto")
    apply_workbench_inventory_to_project(project, show)
    apply_workbench_coordination_to_project(project, show)

    coord = project.modules["coordinacion"]
    assert len(coord["channel_flags"]) >= 20
    assert len(coord["assignments"]) >= 20
    assert coord["scan"]["file_name"] == "Traza 03.csv"

    flagged = [
        item for item in project.modules["inventario_rf"]["equipos"]
        if "coordination_include" in item
    ]
    assert flagged
