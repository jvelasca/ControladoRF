"""
controller.py
-------------
Orquestador de la lógica de workspaces y persistencia de componentes aware.

INTERFAZ PARA COMPONENTES AWARE:
- Todo componente que quiera persistir/restaurar su estado por workspace debe:
  * Implementar save_state(self) -> dict (devuelve un dict serializable)
  * Implementar restore_state(self, config: dict)
- Registrar el componente en el controlador con register_component(self).
- El controlador llamará automáticamente a save_state/restore_state al cambiar de workspace o guardar.
- Si el componente no necesita guardar nada, save_state debe devolver {} y restore_state aceptar el argumento pero no hacer nada.

El controlador orquesta la lógica, notificaciones y persistencia de workspaces y sus componentes aware.

Uso recomendado:
    controller = WorkspaceController(store)
    controller.register_component(mi_ventana)
    controller.create_workspace('nuevo')
    controller.set_active_workspace('nuevo')
    controller.save_active_workspace()
"""
import copy
from typing import List, Callable, Optional, Any, Tuple
from .store import WorkspaceStore
from .model import Workspace
from .validators import validate_name, is_unique
from .workspace_io import (
    WorkspaceIOError,
    export_workspace_to_file,
    load_workspace_from_file,
    merge_workspace_into_default,
)
from utils.logger import log_error, get_logger


class WorkspaceController:
    """
    Orquestador de la lógica de workspaces y sus componentes aware.
    Permite crear, eliminar, activar y guardar workspaces, y gestiona la persistencia/restauración de estado de componentes aware.
    """
    def __init__(self, store: WorkspaceStore):
        """
        Inicializa el controlador con un store de workspaces.
        Args:
            store (WorkspaceStore): Instancia de almacenamiento de workspaces.
        """
        self._logger = get_logger(__name__)
        self._store: WorkspaceStore = store
        self._aware_components: List[Any] = []
        self._subscribers: List[Callable] = []
        self._active_workspace: Optional[Workspace] = self._load_last_active() or self._get_default()
        self._logger.info("WorkspaceController inicializado.")

    def get_workspace(self, name: str) -> Optional[Workspace]:
        """
        Devuelve el workspace con el nombre dado, o None si no existe.
        """
        return self._store.get(name)

    @property
    def active_workspace(self) -> Optional[Workspace]:
        """Workspace actualmente activo."""
        return self._active_workspace

    @property
    def store(self) -> WorkspaceStore:
        """
        Devuelve el store de workspaces asociado al controlador.
        Returns:
            WorkspaceStore: Instancia de almacenamiento de workspaces.
        """
        return self._store

    def _get_default(self) -> Workspace:
        """Devuelve el workspace 'Default', creándolo si no existe."""
        ws = self._store.get("Default")
        if ws is None:
            ws = Workspace(name="Default", description="Configuración por defecto", is_default=True)
            self._store.save(ws)
            self._logger.info("Workspace 'Default' creado automáticamente.")
        return ws

    def _load_last_active(self) -> Optional[Workspace]:
        """Carga el último workspace activo desde el JSON de configuración."""
        name = self._store.get_last_active_workspace()
        ws = self._store.get(name)
        if ws:
            return ws
        return None

    def _save_last_active(self) -> None:
        """Guarda el nombre del workspace activo en el JSON de configuración."""
        if self._active_workspace:
            self._store.set_last_active_workspace(self._active_workspace.name)

    def register_component(self, comp: Any) -> None:
        """
        Registra un componente aware para persistencia/restauración de estado.
        Args:
            comp: Componente que implementa save_state y restore_state.
        Raises:
            TypeError: Si el componente no implementa la interfaz requerida.
        """
        if comp not in self._aware_components:
            if not (hasattr(comp, 'save_state') and callable(comp.save_state)):
                raise TypeError(f"El componente {comp} no implementa save_state().")
            if not (hasattr(comp, 'restore_state') and callable(comp.restore_state)):
                raise TypeError(f"El componente {comp} no implementa restore_state().")
            self._aware_components.append(comp)
            self._logger.info(f"Componente aware registrado: {comp}")

    def unregister_component(self, comp: Any) -> None:
        """
        Desregistra un componente aware.
        Args:
            comp: Componente previamente registrado.
        """
        if comp in self._aware_components:
            self._aware_components.remove(comp)
            self._logger.info(f"Componente aware desregistrado: {comp}")

    def subscribe(self, callback: Callable) -> None:
        """
        Suscribe un callback para ser notificado al cambiar el workspace activo.
        Args:
            callback (Callable): Función a llamar con el workspace activo.
        """
        if callback not in self._subscribers:
            self._subscribers.append(callback)
            self._logger.info(f"Callback suscrito: {callback}")

    def unsubscribe(self, callback: Callable) -> None:
        """
        Elimina la suscripción de un callback.
        Args:
            callback (Callable): Callback previamente suscrito.
        """
        if callback in self._subscribers:
            self._subscribers.remove(callback)
            self._logger.info(f"Callback desuscrito: {callback}")

    def notify(self) -> None:
        """
        Notifica a todos los callbacks suscritos del cambio de workspace activo.
        """
        self._logger.info(f"Notificando a {len(self._subscribers)} callbacks por cambio de workspace.")
        for cb in self._subscribers:
            cb(self._active_workspace)

    def create_workspace(self, name: str, description: str = "") -> bool:
        """
        Crea un nuevo workspace y lo activa si es válido y único.
        Args:
            name (str): Nombre del nuevo workspace.
            description (str, opcional): Descripción del workspace.
        Returns:
            bool: True si se creó correctamente, False si no.
        """
        try:
            names = [ws.name for ws in self._store.load_all()]
            if not validate_name(name) or not is_unique(name, names):
                return False
            ws = Workspace(name=name, description=description)
            self._store.save(ws)
            self.set_active_workspace(name)
            self._logger.info(f"Workspace '{name}' creado correctamente.")
            return True
        except Exception as e:
            log_error(f"[WorkspaceController] Error creando workspace '{name}'", e)
            return False

    def delete_workspace(self, name: str) -> bool:
        """
        Elimina un workspace por nombre (no permite eliminar 'Default').
        Args:
            name (str): Nombre del workspace a eliminar.
        Returns:
            bool: True si se eliminó, False si no.
        """
        try:
            if name == "Default":
                return False
            # Si el workspace a eliminar es el activo, cambiar antes a Default
            if self._active_workspace and self._active_workspace.name == name:
                self.set_active_workspace("Default")
            self._store.delete(name)
            # Forzar recarga tras eliminar
            self._store.load_all()
            self._logger.info(f"Workspace '{name}' eliminado correctamente.")
            return True
        except Exception as e:
            log_error(f"[WorkspaceController] Error eliminando workspace '{name}'", e)
            return False

    def set_active_workspace(self, name: str) -> bool:
        """
        Activa un workspace por nombre y restaura el estado de los componentes aware.
        Args:
            name (str): Nombre del workspace a activar.
        Returns:
            bool: True si se activó correctamente, False si no.
        """
        try:
            prev_ws = self._active_workspace.name if self._active_workspace else None
            self._logger.info("Cambio de workspace: '%s' -> '%s'", prev_ws, name)
            if self._active_workspace and self._active_workspace.name != name:
                self.save_active_workspace()
            ws = self._store.get(name)
            if not ws:
                self._logger.warning("Workspace '%s' no encontrado", name)
                return False
            self._active_workspace = ws
            self._save_last_active()
            self._logger.info(f"Workspace activo cambiado a '{name}'.")
            # Aplicar idioma del nuevo workspace
            from i18n.translation_utils import apply_language
            lang = self.get_language()
            apply_language(lang)
            # Restaurar estado de componentes aware
            for comp in self._aware_components:
                try:
                    comp.restore_state(ws.config)
                    # Forzar visibilidad de paneles tras restaurar (si es main_window)
                    if hasattr(comp, '_dock_panels'):
                        for dock in comp._dock_panels.values():
                            dock.setVisible(True)
                except Exception as e:
                    log_error(f"[WorkspaceController] Error restaurando estado en componente {comp}", e)
            self.notify()
            return True
        except Exception as e:
            log_error(f"[WorkspaceController] Error activando workspace '{name}'", e)
            return False

    def save_active_workspace(self) -> None:
        """
        Guarda el estado actual de los componentes aware en el workspace activo, incluyendo idioma.
        """
        if not self._active_workspace:
            return
        try:
            from utils.theme_utils import strip_legacy_theme_keys

            config = dict(self._active_workspace.config) if self._active_workspace.config else {}
            config = strip_legacy_theme_keys(config)
            if 'language' not in config and hasattr(self, 'get_language'):
                config['language'] = self.get_language()
            for comp in self._aware_components:
                try:
                    state = comp.save_state()
                    if isinstance(state, dict):
                        config.update(state)
                except Exception as e:
                    log_error(f"[WorkspaceController] Error guardando estado en componente {comp}", e)
            ws = Workspace(
                name=self._active_workspace.name,
                description=self._active_workspace.description,
                config=config,
                is_default=self._active_workspace.is_default
            )
            self._active_workspace = ws
            self._store.save(ws)
        except Exception as e:
            log_error(f"[WorkspaceController] Error guardando estado de workspace activo", e)

    def get_all_workspaces(self) -> List[Workspace]:
        """
        Devuelve la lista de todos los workspaces gestionados por el controlador.
        Returns:
            List[Workspace]: Lista de workspaces.
        """
        return self._store.load_all()

    def rename_workspace(self, old_name: str, new_name: str, description: Optional[str] = None) -> bool:
        """Renombra un workspace conservando su configuración."""
        try:
            if old_name == "Default" and new_name != "Default":
                return False
            ws = self._store.get(old_name)
            if not ws:
                return False
            new_name = new_name.strip()
            desc = description if description is not None else ws.description
            names = [name for name in (w.name for w in self._store.load_all()) if name != old_name]
            if not validate_name(new_name) or not is_unique(new_name, names):
                return False
            was_active = self._active_workspace and self._active_workspace.name == old_name
            new_ws = Workspace(
                name=new_name,
                description=desc,
                config=copy.deepcopy(ws.config),
                is_default=ws.is_default,
            )
            self._store.save(new_ws)
            if old_name != new_name:
                self._store.delete(old_name)
            if was_active:
                self._active_workspace = self._store.get(new_name)
                self._save_last_active()
            return True
        except Exception as e:
            log_error(f"[WorkspaceController] Error renombrando workspace '{old_name}'", e)
            return False

    def update_workspace_description(self, name: str, description: str) -> bool:
        ws = self._store.get(name)
        if not ws:
            return False
        ws.description = description
        self._store.save(ws)
        if self._active_workspace and self._active_workspace.name == name:
            self._active_workspace = self._store.get(name)
        return True

    def duplicate_workspace(self, source_name: str, new_name: str) -> bool:
        """Duplica un workspace existente con un nombre nuevo."""
        try:
            source = self._store.get(source_name)
            if not source:
                return False
            new_name = new_name.strip()
            names = [ws.name for ws in self._store.load_all()]
            if not validate_name(new_name) or not is_unique(new_name, names):
                return False
            clone = Workspace(
                name=new_name,
                description=source.description,
                config=copy.deepcopy(source.config),
                is_default=False,
            )
            self._store.save(clone)
            self._logger.info("Workspace '%s' duplicado como '%s'.", source_name, new_name)
            return True
        except Exception as e:
            log_error(f"[WorkspaceController] Error duplicando workspace '{source_name}'", e)
            return False

    def export_workspace(self, name: str, path: str) -> bool:
        ws = self._store.get(name)
        if not ws:
            return False
        try:
            export_workspace_to_file(ws, path)
            return True
        except Exception as e:
            log_error(f"[WorkspaceController] Error exportando workspace '{name}'", e)
            return False

    def import_workspace(self, path: str, *, merge_default: bool = False) -> Tuple[bool, str]:
        """
        Importa un workspace desde JSON.
        Si merge_default es True, fusiona la config en Default.
        """
        try:
            imported = load_workspace_from_file(path)
            if merge_default:
                default = self._store.get("Default") or self._get_default()
                merged = merge_workspace_into_default(imported, default)
                self._store.save(merged)
                self.set_active_workspace("Default")
                return True, "Default"
            names = [ws.name for ws in self._store.load_all()]
            target_name = imported.name
            if not validate_name(target_name) or target_name in names:
                return False, ""
            imported.is_default = False
            self._store.save(imported)
            return True, target_name
        except WorkspaceIOError as e:
            log_error(f"[WorkspaceController] Error importando workspace desde '{path}'", e)
            return False, ""
        except Exception as e:
            log_error(f"[WorkspaceController] Error importando workspace desde '{path}'", e)
            return False, ""

    # --- Preferencias de idioma ---
    def get_language(self) -> str:
        """
        Devuelve el idioma activo del workspace.

        Returns:
            str: Código de idioma ('es', 'en', etc).
        """
        ws = self._active_workspace
        if ws and 'language' in ws.config:
            return ws.config['language']
        return 'es'

    def set_language(self, lang: str) -> None:
        """
        Cambia el idioma del workspace activo y lo persiste.

        Args:
            lang (str): Código de idioma ('es', 'en', etc).
        """
        ws = self._active_workspace
        if ws:
            ws.config['language'] = lang
            self._store.save(ws)
            self.notify()
