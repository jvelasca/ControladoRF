"""
app_lifecycle.py
----------------
Orquestador profesional del ciclo de vida de la aplicación.
"""
import shutil
import sys

from PyQt6.QtWidgets import QApplication

from app_paths import bundle_path, configure_qt_runtime, is_frozen, logs_dir, workspace_data_dir
from core import ApplicationServices
from core.project_manager import ProjectManager
from db import DatabaseService
from gui.main_window import MainWindow
from i18n.translation_utils import apply_language
from utils.logger import get_logger, init_logging
from utils.theme_utils import apply_system_appearance, connect_system_appearance_changed
from workspace.controller import WorkspaceController
from workspace.store import WorkspaceStore


class AppLifecycle:
    def __init__(self):
        self.app = None
        self.store = None
        self.controller = None
        self.database_service = None
        self.app_services = None
        self.project_manager = None
        self.main_window = None
        self._logger = get_logger(__name__)

    def start(self):
        self._ensure_workspace_seed()
        configure_qt_runtime()
        init_logging(log_file=str(logs_dir() / "app.log"))
        self.app = QApplication(sys.argv)
        if is_frozen():
            from PyQt6.QtCore import QCoreApplication

            plugins = bundle_path("PyQt6", "Qt6", "plugins")
            if plugins.is_dir():
                QCoreApplication.addLibraryPath(str(plugins))
        self.store = WorkspaceStore(str(workspace_data_dir()))
        self.controller = WorkspaceController(self.store)
        self._init_database()
        self._init_project_manager()

        apply_language(self.controller.get_language())
        apply_system_appearance()

        self.main_window = MainWindow(
            workspace_controller=self.controller,
            database_service=self.database_service,
            app_services=self.app_services,
            project_manager=self.project_manager,
        )
        connect_system_appearance_changed(self._on_system_appearance_changed)
        self.app.aboutToQuit.connect(self.on_shutdown)
        self.main_window.show()
        if is_frozen():
            self.main_window.schedule_startup_update_check()
        return self.app.exec()

    def _init_database(self) -> None:
        """Abre SQLite, aplica migraciones y deja la conexión lista para repositorios futuros."""
        self.database_service = DatabaseService(
            data_dir=self.store.data_dir,
            store_get_config=self.store.get_config,
            store_set_config=self.store.set_config,
        )
        self.database_service.startup()
        self.app_services = ApplicationServices.from_database_service(self.database_service)
        self._logger.info(
            "Base de datos inicializada: %s",
            self.database_service.database.config.path,
        )

    @staticmethod
    def _ensure_workspace_seed() -> None:
        target = workspace_data_dir() / "workspaces.json"
        if target.is_file():
            return
        seed = bundle_path("workspace", "data", "workspaces.json")
        if seed.is_file():
            shutil.copy2(seed, target)

    def _init_project_manager(self) -> None:
        version_path = bundle_path("VERSION")
        app_version = "0.1.0"
        try:
            app_version = version_path.read_text(encoding="utf-8").strip() or app_version
        except OSError:
            pass

        self.project_manager = ProjectManager(
            store_get_config=self.store.get_config,
            store_set_config=self.store.set_config,
            app_version=app_version,
        )

    def _on_system_appearance_changed(self, *_args) -> None:
        """Actualiza la UI cuando Windows/macOS cambia entre modo claro y oscuro."""
        if self.main_window is not None:
            self.main_window.refresh_appearance()

    def on_shutdown(self):
        """Guarda el workspace activo, persiste workspaces y cierra la base de datos."""
        if self.controller and self.main_window:
            if self.controller.active_workspace:
                self.store.set_last_active_workspace(self.controller.active_workspace.name)
            self.controller.save_active_workspace()
            self.store.save_all(self.controller.get_all_workspaces())
        if self.database_service is not None:
            self.database_service.close()
            self.database_service = None
        self.app_services = None
