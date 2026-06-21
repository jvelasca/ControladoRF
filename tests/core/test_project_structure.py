"""Tests del árbol de estructura del proyecto."""
from pathlib import Path

import pytest

from core.project_model import Project
from core.project_structure import build_project_structure_tree
from i18n.json_translation import tr
from importers.workbench_parser import apply_workbench_inventory_to_project, parse_workbench_show

EXAMPLE_SHW = (
    Path(__file__).resolve().parents[2] / "auxiliares" / "ejempo impor workbench.shw"
)


@pytest.fixture
def example_path() -> Path:
    if not EXAMPLE_SHW.is_file():
        pytest.skip(f"Fichero de ejemplo no encontrado: {EXAMPLE_SHW}")
    return EXAMPLE_SHW


def test_structure_tree_empty_project():
    project = Project.create_new()
    root = build_project_structure_tree(project)

    assert project.name in root.label
    assert len(root.children) == 3
    assert root.children[0].label == tr("structure_metadata")
    assert root.children[1].label == tr("structure_modules")
    assert root.children[2].label == tr("structure_ui")

    inv_node = root.children[1].children[0]
    assert inv_node.detail == tr("structure_channel_count", count=0)


def test_structure_tree_after_workbench_import(example_path: Path):
    show = parse_workbench_show(str(example_path))
    project = Project.create_new()
    apply_workbench_inventory_to_project(project, show)

    root = build_project_structure_tree(
        project,
        file_path="/tmp/show.crf",
        is_dirty=True,
        active_module="inventario_rf",
    )

    assert "●" in root.label
    assert root.detail == "/tmp/show.crf"

    meta = root.children[0]
    labels = [node.label for node in meta.children]
    assert tr("structure_show_name") in labels
    assert tr("structure_customer") in labels
    assert tr("structure_import_source") in labels

    inv_node = root.children[1].children[0]
    equipos = project.modules["inventario_rf"]["equipos"]
    assert len(equipos) == 24
    assert inv_node.detail == tr("structure_channel_count", count=24)

    device_nodes = inv_node.children
    assert len(device_nodes) == 14
    total_channels = sum(len(device.children) for device in device_nodes)
    assert total_channels == 24
