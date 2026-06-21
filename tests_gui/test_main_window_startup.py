"""Verifica que la ventana principal arranca sin excepciones."""
from __future__ import annotations

from app_lifecycle import AppLifecycle
from gui.main_window import MainWindow
from tests_gui.conftest import close_window
from workspace.controller import WorkspaceController


def _close_window(window) -> None:
    close_window(window)


def test_main_window_constructs(app_context, qapp):
    from i18n.json_translation import tr

    window = MainWindow(
        workspace_controller=app_context["controller"],
        database_service=app_context["database_service"],
        app_services=None,
        project_manager=app_context["project_manager"],
    )
    assert window.windowTitle() == tr("app_title")
    assert window._project_manager.project is None
    assert window._module_tab_manager is not None
    assert window._module_tab_manager.active_module == "inventario_rf"
    window.show()
    qapp.processEvents()
    panels = window._module_tab_manager.get_active_workspace().get_panels()
    assert "lista" in panels
    _close_window(window)


def test_main_window_has_three_module_tabs(app_context, qapp):
    window = MainWindow(
        workspace_controller=app_context["controller"],
        database_service=app_context["database_service"],
        project_manager=app_context["project_manager"],
    )
    tabs = window._module_tab_manager.module_tabs
    assert tabs.count() == 3
    _close_window(window)


def test_project_title_shows_dirty_marker(app_context, qapp):
    from i18n.json_translation import tr

    manager = app_context["project_manager"]
    manager.new_project("Prueba")
    window = MainWindow(
        workspace_controller=app_context["controller"],
        database_service=app_context["database_service"],
        project_manager=manager,
    )
    title = window._project_title
    assert title._show_name.text() == "Prueba"
    assert not title._dirty_dot.isHidden()
    assert window.windowTitle() == tr("app_title")
    _close_window(window)


def test_open_recent_without_save_prompt(app_context, qapp, tmp_path):
    from core.project_io import save_project
    from core.project_model import Project
    from i18n.json_translation import tr

    path = tmp_path / "recent.crf"
    project = Project.create_new(name="Reciente")
    save_project(str(path), project)

    manager = app_context["project_manager"]
    window = MainWindow(
        workspace_controller=app_context["controller"],
        database_service=app_context["database_service"],
        project_manager=manager,
    )
    assert manager.project is None
    window.open_recent_project(str(path))
    qapp.processEvents()
    assert manager.get_project_name() == "Reciente"
    assert window.windowTitle() == tr("app_title")
    _close_window(window)


def test_module_tab_switch_updates_toolbar(app_context, qapp):
    window = MainWindow(
        workspace_controller=app_context["controller"],
        database_service=app_context["database_service"],
        project_manager=app_context["project_manager"],
    )
    tabs = window._module_tab_manager.module_tabs
    tabs.setCurrentIndex(1)
    qapp.processEvents()
    assert window._module_tab_manager.active_module == "coordinacion"
    assert len(window.get_tool_bar().get_toolbar_actions()) == 0
    _close_window(window)


def test_app_lifecycle_builds_main_window(isolated_store, qapp, monkeypatch):
    """Smoke test del ciclo de vida sin ejecutar el bucle de eventos."""
    lifecycle = AppLifecycle()
    monkeypatch.setattr(lifecycle, "store", isolated_store)
    lifecycle.controller = WorkspaceController(isolated_store)
    lifecycle._init_database()
    lifecycle._init_project_manager()

    from i18n.translation_utils import apply_language
    from utils.theme_utils import apply_system_appearance

    apply_language(lifecycle.controller.get_language())
    apply_system_appearance()

    lifecycle.main_window = MainWindow(
        workspace_controller=lifecycle.controller,
        database_service=lifecycle.database_service,
        app_services=lifecycle.app_services,
        project_manager=lifecycle.project_manager,
    )
    assert lifecycle.main_window.isVisible() is False
    lifecycle.main_window.show()
    qapp.processEvents()
    assert lifecycle.main_window.isVisible() is True
    _close_window(lifecycle.main_window)
    lifecycle.on_shutdown()
