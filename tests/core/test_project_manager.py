"""Tests del gestor de proyectos."""
from core.project_manager import ProjectManager


def test_new_project_is_dirty():
    config = {"language": "es_ES"}
    manager = ProjectManager(
        store_get_config=lambda: config,
        store_set_config=lambda c: config.update(c),
    )
    manager.new_project("Nuevo")
    assert manager.is_dirty is True
    assert manager.get_show_label().endswith("*")


def test_save_and_open_project(tmp_path):
    config: dict = {"language": "es_ES", "recent_projects": []}

    def set_config(value):
        config.clear()
        config.update(value)

    manager = ProjectManager(
        store_get_config=lambda: config,
        store_set_config=set_config,
    )
    path = tmp_path / "show.crf"
    manager.new_project("Show A")
    manager.project.modules["inventario_rf"]["equipos"] = [{"name": "RX1"}]
    manager.save_project_as(str(path))

    assert manager.is_dirty is False
    assert manager.file_path == str(path.resolve())
    assert len(manager.get_recent_projects()) == 1

    manager.new_project("Otro")
    manager.open_project(str(path))
    assert manager.project.modules["inventario_rf"]["equipos"][0]["name"] == "RX1"
    assert manager.is_dirty is False


def test_show_name_independent_of_filename(tmp_path):
    config: dict = {"recent_projects": []}
    manager = ProjectManager(
        store_get_config=lambda: config,
        store_set_config=lambda c: config.update(c),
    )
    path = tmp_path / "backup_v1.crf"
    manager.new_project("Final Madrid")
    manager.save_project_as(str(path))

    assert manager.get_project_name() == "Final Madrid"
    assert manager.get_file_basename() == "backup_v1.crf"
    assert manager.get_show_label() == "Final Madrid"
    recents = manager.get_recent_projects()
    assert recents[0]["name"] == "backup_v1"
    assert manager.get_last_opened_project_path() == str(path.resolve())


def test_last_opened_project_path(tmp_path):
    config: dict = {}
    manager = ProjectManager(
        store_get_config=lambda: config,
        store_set_config=lambda c: config.update(c),
    )
    path = tmp_path / "session.crf"
    manager.new_project("Sesión")
    manager.save_project_as(str(path))
    assert manager.get_last_opened_project_path() == str(path.resolve())

    manager.new_project("Otro")
    assert manager.get_last_opened_project_path() == str(path.resolve())

    manager.open_project(str(path))
    assert manager.get_last_opened_project_path() == str(path.resolve())


def test_update_project_name_marks_dirty():
    manager = ProjectManager(
        store_get_config=lambda: {},
        store_set_config=lambda c: None,
    )
    manager.new_project("Show")
    manager.clear_dirty()
    manager.update_project_name("Show renombrado")
    assert manager.get_project_name() == "Show renombrado"
    assert manager.is_dirty is True


def test_module_ui_state_persisted_in_memory():
    config = {}
    manager = ProjectManager(
        store_get_config=lambda: config,
        store_set_config=lambda c: config.update(c),
    )
    manager.new_project()
    manager.set_module_ui_state("inventario_rf", {"splitter_main": [800, 200]})
    assert manager.get_module_ui_state("inventario_rf")["splitter_main"] == [800, 200]
