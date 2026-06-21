"""Tests del layout de paneles dentro de cada pestaña."""
from __future__ import annotations

from PyQt6.QtWidgets import QDockWidget, QSplitter

from gui.main_window import MainWindow
from tests_gui.conftest import close_window


def _show_window(window: MainWindow, qapp) -> None:
    window.resize(1200, 800)
    window.show()
    qapp.processEvents()


def test_each_tab_has_three_internal_panels(app_context, qapp):
    window = MainWindow(
        workspace_controller=app_context["controller"],
        database_service=app_context["database_service"],
        project_manager=app_context["project_manager"],
    )
    _show_window(window, qapp)

    manager = window._module_tab_manager
    assert manager.module_tabs.count() == 3
    for module_id in ("inventario_rf", "coordinacion", "monitor"):
        panels = manager.get_workspace(module_id).get_panels()
        assert set(panels.keys()) == {"lista", "propiedades", "acciones"}

    close_window(window)


def test_panels_live_inside_tab_not_main_window(app_context, qapp):
    window = MainWindow(
        workspace_controller=app_context["controller"],
        database_service=app_context["database_service"],
        project_manager=app_context["project_manager"],
    )
    _show_window(window, qapp)

    assert window.findChildren(QDockWidget) == []

    workspace = window._module_tab_manager.get_active_workspace()
    splitters = workspace.findChildren(QSplitter)
    assert len(splitters) == 2

    close_window(window)


def test_splitters_are_resizable(app_context, qapp):
    window = MainWindow(
        workspace_controller=app_context["controller"],
        database_service=app_context["database_service"],
        project_manager=app_context["project_manager"],
    )
    _show_window(window, qapp)

    workspace = window._module_tab_manager.get_active_workspace()
    main_splitter = workspace._main_splitter
    left_splitter = workspace._left_splitter
    assert not main_splitter.childrenCollapsible()
    assert not left_splitter.childrenCollapsible()
    assert main_splitter.handle(1) is not None

    close_window(window)


def test_panel_visibility_toggle(app_context, qapp):
    window = MainWindow(
        workspace_controller=app_context["controller"],
        database_service=app_context["database_service"],
        project_manager=app_context["project_manager"],
    )
    _show_window(window, qapp)

    workspace = window._module_tab_manager.get_active_workspace()
    workspace.set_panel_visible("propiedades", False)
    assert workspace.get_panel("propiedades").isVisible() is False
    workspace.set_panel_visible("propiedades", True)
    assert workspace.get_panel("propiedades").isVisible() is True

    close_window(window)


def test_layout_state_roundtrip(app_context, qapp):
    window = MainWindow(
        workspace_controller=app_context["controller"],
        database_service=app_context["database_service"],
        project_manager=app_context["project_manager"],
    )
    _show_window(window, qapp)

    workspace = window._module_tab_manager.get_workspace("inventario_rf")
    workspace._main_splitter.setSizes([800, 200])
    state = workspace.save_state()
    workspace.reset_layout()
    workspace.restore_state(state)
    assert workspace._main_splitter.sizes()[0] >= 700

    close_window(window)


def test_panels_visible_after_tab_roundtrip(app_context, qapp):
    """Al volver a Inventario RF los paneles no deben quedar colapsados."""
    window = MainWindow(
        workspace_controller=app_context["controller"],
        database_service=app_context["database_service"],
        project_manager=app_context["project_manager"],
    )
    _show_window(window, qapp)

    manager = window._module_tab_manager
    inventario = manager.get_workspace("inventario_rf")
    inventario._main_splitter.setSizes([800, 200])
    inventario._left_splitter.setSizes([500, 300])
    qapp.processEvents()

    manager.module_tabs.setCurrentIndex(1)
    qapp.processEvents()
    manager.module_tabs.setCurrentIndex(0)
    qapp.processEvents()

    for panel_id, panel in inventario.get_panels().items():
        assert panel.isVisible(), f"Panel {panel_id} debe seguir visible"

    main_sizes = inventario._main_splitter.sizes()
    left_sizes = inventario._left_splitter.sizes()
    assert sum(main_sizes) >= 120
    assert sum(left_sizes) >= 120
    assert all(size > 0 for size in main_sizes + left_sizes)

    close_window(window)


def test_project_save_and_reopen_restores_panel_layout(app_context, qapp, tmp_path):
    window = MainWindow(
        workspace_controller=app_context["controller"],
        database_service=app_context["database_service"],
        project_manager=app_context["project_manager"],
    )
    _show_window(window, qapp)

    workspace = window._module_tab_manager.get_workspace("inventario_rf")
    workspace.set_panel_visible("propiedades", False)
    workspace._main_splitter.setSizes([900, 100])
    qapp.processEvents()

    path = tmp_path / "layout-test.crf"
    window._project_manager.new_project("Layout Test Show")
    window._flush_all_module_layouts(mark_dirty=False)
    window._project_manager.save_project_as(str(path))
    qapp.processEvents()

    workspace.set_panel_visible("propiedades", True)
    workspace.reset_layout()
    qapp.processEvents()

    window._project_manager.open_project(str(path))
    window._restore_project_ui()
    qapp.processEvents()

    restored = window._module_tab_manager.get_workspace("inventario_rf")
    assert restored.get_panel("propiedades").isHidden()
    assert restored._main_splitter.sizes()[0] >= 800
    assert window._project_manager.is_dirty is False
    assert window._project_manager.get_file_basename() == "layout-test.crf"
    assert window._project_manager.get_project_name() == "Layout Test Show"

    close_window(window)


def test_panel_header_close_hides_panel(app_context, qapp):
    window = MainWindow(
        workspace_controller=app_context["controller"],
        database_service=app_context["database_service"],
        project_manager=app_context["project_manager"],
    )
    _show_window(window, qapp)

    workspace = window._module_tab_manager.get_active_workspace()
    panel = workspace.get_panel("propiedades")
    panel.close_requested.emit()
    qapp.processEvents()

    assert panel.isVisible() is False
    close_window(window)


def test_panel_header_maximize_and_restore(app_context, qapp):
    window = MainWindow(
        workspace_controller=app_context["controller"],
        database_service=app_context["database_service"],
        project_manager=app_context["project_manager"],
    )
    _show_window(window, qapp)

    workspace = window._module_tab_manager.get_active_workspace()
    workspace.maximize_panel("lista")
    qapp.processEvents()

    assert workspace.get_maximized_panel() == "lista"
    assert workspace.get_panel("lista").isVisible()
    assert workspace.get_panel("propiedades").isVisible() is False
    assert workspace.get_panel("acciones").isVisible() is False

    workspace.restore_from_maximize()
    qapp.processEvents()

    assert workspace.get_maximized_panel() is None
    for panel_id in ("lista", "propiedades", "acciones"):
        assert workspace.get_panel(panel_id).isVisible()

    close_window(window)
