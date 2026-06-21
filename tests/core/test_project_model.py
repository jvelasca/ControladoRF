"""Tests del modelo de proyecto CONTROLADORF."""
from core.project_model import DEFAULT_PROJECT_NAME, Project


def test_create_new_project_has_skeleton():
    project = Project.create_new("Show RF")
    assert project.name == "Show RF"
    assert project.format_version == "1.0"
    assert "inventario_rf" in project.modules
    assert project.modules["inventario_rf"]["equipos"] == []
    assert project.ui["active_module"] == "inventario_rf"


def test_to_dict_and_from_dict_roundtrip():
    project = Project.create_new("Roundtrip")
    project.get_module_ui("inventario_rf")["dock_state"] = "abc"
    data = project.to_dict()
    restored = Project.from_dict(data)
    assert restored.name == "Roundtrip"
    assert restored.get_module_ui("inventario_rf")["dock_state"] == "abc"


def test_from_dict_uses_default_name_when_missing():
    project = Project.from_dict({"format_version": "1.0", "modules": {}, "ui": {}})
    assert project.name == DEFAULT_PROJECT_NAME
