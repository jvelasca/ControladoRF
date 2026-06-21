"""Smoke test de arranque sin abrir el bucle Qt indefinidamente."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from PyQt6.QtWidgets import QApplication

from app_lifecycle import AppLifecycle
from utils.logger import init_logging


def main() -> int:
    init_logging(log_file=str(ROOT / "logs" / "app.log"))
    app = QApplication.instance() or QApplication([])

    lifecycle = AppLifecycle()
    lifecycle.store = __import__("workspace.store", fromlist=["WorkspaceStore"]).WorkspaceStore(
        str(ROOT / "src" / "workspace" / "data")
    )
    lifecycle.controller = __import__(
        "workspace.controller", fromlist=["WorkspaceController"]
    ).WorkspaceController(lifecycle.store)
    lifecycle._init_database()
    lifecycle._init_project_manager()

    from i18n.translation_utils import apply_language
    from utils.theme_utils import apply_system_appearance

    apply_language(lifecycle.controller.get_language())
    apply_system_appearance()

    from gui.main_window import MainWindow

    lifecycle.main_window = MainWindow(
        workspace_controller=lifecycle.controller,
        database_service=lifecycle.database_service,
        app_services=lifecycle.app_services,
        project_manager=lifecycle.project_manager,
    )
    lifecycle.main_window.show()
    app.processEvents()
    title = lifecycle.main_window.windowTitle()
    module = lifecycle.main_window._module_tab_manager.active_module
    print(f"OK: ventana='{title}', modulo='{module}'")
    if lifecycle.main_window._project_manager:
        lifecycle.main_window._project_manager.clear_dirty()
    lifecycle.main_window._closing = True
    lifecycle.main_window.close()
    lifecycle.on_shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
