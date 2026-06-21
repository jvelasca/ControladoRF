"""Tests de lectura/escritura de proyectos."""
import json

import pytest

from core.project_io import (
    PROJECT_EXTENSION,
    ProjectIOError,
    default_project_filename,
    load_project,
    normalize_project_path,
    save_project,
    validate_project_file,
)
from core.project_model import Project


def test_save_and_load_project(tmp_path):
    path = tmp_path / "show.crf"
    project = Project.create_new("Test Show")
    save_project(str(path), project)

    assert path.is_file()
    loaded = load_project(str(path))
    assert loaded.name == "Test Show"
    assert loaded.format_version == "1.0"


def test_validate_project_file(tmp_path):
    path = tmp_path / "bad.crf"
    path.write_text("{not-json", encoding="utf-8")
    ok, message = validate_project_file(str(path))
    assert ok is False
    assert message


def test_saved_json_has_expected_sections(tmp_path):
    path = tmp_path / "show.crf"
    save_project(str(path), Project.create_new())
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data.keys()) >= {"format_version", "metadata", "modules", "ui"}


def test_normalize_project_path_adds_crf_extension():
    assert normalize_project_path("Show").endswith(PROJECT_EXTENSION)
    assert normalize_project_path("Show.crf").endswith(PROJECT_EXTENSION)


def test_load_rejects_non_crf_extension(tmp_path):
    path = tmp_path / "show.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ProjectIOError):
        load_project(str(path))


def test_default_project_filename():
    assert default_project_filename("Proyecto") == "Proyecto.crf"
    assert default_project_filename("Proyecto*") == "Proyecto.crf"
