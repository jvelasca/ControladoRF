"""
store.py
--------
Clase responsable de la persistencia y acceso a workspaces y configuración global en workspaces.json.

Estructura del archivo:
{
  "config": { ... },           // Parámetros globales de la app (idioma, tema, etc.)
  "workspaces": [ ... ],       // Array de workspaces, cada uno con toda la personalización
  "last_active_workspace": "NombreDelWorkspace" // Nombre del workspace activo al cerrar la app
}

- Permite operaciones CRUD sobre workspaces y configuración global.
- Todos los errores críticos se registran mediante log_error.
- Valida la integridad y unicidad de los datos.
- Realiza backup automático antes de cada escritura.

Uso recomendado:
    store = WorkspaceStore(data_dir)
    workspaces = store.load_all()
    store.save(workspace)
    store.delete('nombre')
    config = store.get_config()
    store.set_config(config_dict)
"""
import os
import json
from typing import List, Optional, Dict, Any
from .model import Workspace
from utils.logger import log_error, get_logger

class WorkspaceStore:
    """
    Clase responsable de la persistencia y acceso a workspaces y configuración global.
    Proporciona operaciones CRUD y validación de integridad.
    """
    def __init__(self, data_dir: str, file_path: Optional[str] = None):
        """
        Inicializa el store con el directorio de datos y el path opcional al archivo JSON.
        Si el archivo no existe, crea uno por defecto.
        Args:
            data_dir (str): Directorio donde se almacenan los datos.
            file_path (Optional[str]): Ruta al archivo JSON de workspaces.
        """
        self._logger = get_logger(__name__)
        self._data_dir: str = data_dir
        self._file_path: str = file_path if file_path else os.path.join(self._data_dir, "workspaces.json")
        os.makedirs(self._data_dir, exist_ok=True)

    @property
    def data_dir(self) -> str:
        """Directorio donde se guardan `workspaces.json` y la base de datos."""
        return self._data_dir
        if not os.path.exists(self._file_path):
            self._init_default()
        self._logger.info(f"WorkspaceStore inicializado en {self._file_path}")

    @property
    def file_path(self) -> str:
        """Ruta al archivo JSON de workspaces."""
        return self._file_path

    def _init_default(self) -> None:
        """Crea un archivo de configuración y workspace por defecto si no existe."""
        default_ws = Workspace(name="Default", description="Configuración por defecto", is_default=True)
        data = {
            "config": {
                "language": "es_ES",
                "backup_path": self._default_backup_path()
            },
            "workspaces": [default_ws.to_dict()]
        }
        self._write_data(data)
        self._logger.info("Archivo de configuración y workspace por defecto creado.")

    def _default_backup_path(self) -> str:
        """Devuelve la ruta multiplataforma a la carpeta de documentos del usuario."""
        from pathlib import Path
        return str(Path.home() / "Documents")

    def _backup_file(self) -> None:
        """Crea una copia de seguridad del archivo de workspaces antes de sobrescribirlo."""
        backup_path = self._file_path + ".bak"
        try:
            if os.path.exists(self._file_path):
                import shutil
                shutil.copy2(self._file_path, backup_path)
        except Exception as e:
            log_error(f"[WorkspaceStore] Error creando backup de {self._file_path}", e)

    def _read_data(self) -> Dict[str, Any]:
        """
        Lee y valida el contenido del archivo JSON de workspaces.
        Devuelve un diccionario con claves 'config', 'workspaces' y 'last_active_workspace'.
        Si el archivo está corrupto, lo repara y registra el error.
        Returns:
            Dict[str, Any]: Datos validados de configuración y workspaces.
        """
        if not os.path.exists(self._file_path):
            self._init_default()
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            self._logger.info(f"Leído workspaces.json correctamente ({len(data.get('workspaces', []))} workspaces)")
        except Exception as e:
            log_error(f"[WorkspaceStore] Error leyendo {self._file_path}", e)
            self._init_default()
            data = {"config": {"language": "es_ES", "backup_path": self._default_backup_path()}, "workspaces": [], "last_active_workspace": "Default"}
        # Migración desde array plano si es necesario
        if isinstance(data, list):
            data = {"config": {"language": "es_ES", "backup_path": self._default_backup_path()}, "workspaces": data, "last_active_workspace": "Default"}
            self._write_data(data)
            self._logger.info("Migración de estructura plana a diccionario realizada.")
        # Validación estricta de integridad
        if "config" not in data or not isinstance(data["config"], dict):
            log_error(f"[WorkspaceStore] workspaces.json corrupto: falta o tipo incorrecto en 'config'")
            data["config"] = {"language": "es_ES", "backup_path": self._default_backup_path()}
        if "workspaces" not in data or not isinstance(data["workspaces"], list):
            log_error(f"[WorkspaceStore] workspaces.json corrupto: falta o tipo incorrecto en 'workspaces'")
            data["workspaces"] = []
        if "last_active_workspace" not in data or not isinstance(data["last_active_workspace"], str):
            data["last_active_workspace"] = "Default"
        # Validar unicidad de nombres y estructura mínima
        names = set()
        valid_workspaces = []
        for ws in data["workspaces"]:
            if not isinstance(ws, dict) or "name" not in ws or ws["name"] in names:
                log_error(f"[WorkspaceStore] workspace inválido o duplicado: {ws}")
                continue
            names.add(ws["name"])
            valid_workspaces.append(ws)
        data["workspaces"] = valid_workspaces
        return data

    def _write_data(self, data: Dict[str, Any]) -> None:
        """
        Escribe los datos validados en el archivo JSON, realizando backup previo.
        Args:
            data (Dict[str, Any]): Datos a guardar.
        """
        self._backup_file()
        try:
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._logger.info(f"Datos guardados correctamente en {self._file_path}")
        except Exception as e:
            log_error(f"[WorkspaceStore] Error escribiendo {self._file_path}", e)

    def load_all(self) -> List[Workspace]:
        """
        Carga y devuelve todos los workspaces almacenados, forzando siempre la lectura desde disco
        para evitar datos cacheados en memoria y garantizar la sincronización inmediata tras operaciones CRUD.
        Returns:
            List[Workspace]: Lista de instancias Workspace.
        """
        # Forzar recarga desde disco
        import importlib
        importlib.reload(json)
        data = self._read_data()
        workspaces = [Workspace.from_dict(ws) for ws in data.get("workspaces", [])]
        self._logger.info(f"Cargados {len(workspaces)} workspaces desde disco.")
        return workspaces

    def save_all(self, workspaces: List[Workspace]) -> None:
        """
        Guarda la lista completa de workspaces en el archivo JSON.
        Args:
            workspaces (List[Workspace]): Lista de workspaces a guardar.
        """
        data = self._read_data()
        data["workspaces"] = [ws.to_dict() for ws in workspaces]
        self._write_data(data)
        self._logger.info(f"Guardada lista completa de workspaces ({len(workspaces)}) en disco.")

    def save(self, ws: Workspace) -> None:
        """
        Guarda o actualiza un workspace individual en el archivo JSON.
        Args:
            ws (Workspace): Workspace a guardar o actualizar.
        Raises:
            ValueError: Si el nombre del workspace es inválido o duplicado.
        """
        try:
            workspaces = self.load_all()
            found = False
            for i, w in enumerate(workspaces):
                if w.name == ws.name:
                    workspaces[i] = ws
                    found = True
                    break
            if not found:
                workspaces.append(ws)
            self.save_all(workspaces)
            self._logger.info(f"Workspace '{ws.name}' guardado/actualizado correctamente.")
        except Exception as e:
            log_error(f"[WorkspaceStore] Error guardando workspace '{ws.name}'", e)

    def delete(self, name: str) -> None:
        """
        Elimina un workspace por nombre.
        Args:
            name (str): Nombre del workspace a eliminar.
        """
        try:
            workspaces = [ws for ws in self.load_all() if ws.name != name]
            self._logger.info(f"[DEBUG] Workspaces tras eliminar '{name}': {[ws.name for ws in workspaces]}")
            self.save_all(workspaces)
            # Validar que el workspace ya no está en el archivo
            data = self._read_data()
            nombres = [ws['name'] for ws in data.get('workspaces', [])]
            self._logger.info(f"[DEBUG] Nombres en JSON tras eliminar: {nombres}")
            self._logger.info(f"Workspace '{name}' eliminado correctamente.")
        except Exception as e:
            log_error(f"[WorkspaceStore] Error eliminando workspace '{name}'", e)

    def get(self, name: str) -> Optional[Workspace]:
        """
        Obtiene un workspace por nombre.
        Args:
            name (str): Nombre del workspace a buscar.
        Returns:
            Optional[Workspace]: Workspace encontrado o None.
        """
        try:
            for ws in self.load_all():
                if ws.name == name:
                    return ws
            return None
        except Exception as e:
            log_error(f"[WorkspaceStore] Error obteniendo workspace '{name}'", e)
            return None

    def exists(self, name: str) -> bool:
        """
        Verifica si existe un workspace con el nombre dado.
        Args:
            name (str): Nombre del workspace.
        Returns:
            bool: True si existe, False en caso contrario.
        """
        return self.get(name) is not None

    def get_last_active_workspace(self) -> str:
        """
        Devuelve el nombre del último workspace activo almacenado en el JSON.
        Returns:
            str: Nombre del workspace activo.
        """
        data = self._read_data()
        return data.get("last_active_workspace", "Default")

    def set_last_active_workspace(self, name: str) -> None:
        """
        Actualiza el nombre del último workspace activo en el JSON.
        Args:
            name (str): Nombre del workspace activo.
        """
        data = self._read_data()
        data["last_active_workspace"] = name
        self._write_data(data)
        self._logger.info(f"last_active_workspace actualizado a '{name}' en el JSON.")

    def get_config(self) -> Dict[str, Any]:
        """
        Devuelve la configuración global almacenada.
        Returns:
            Dict[str, Any]: Diccionario de configuración global.
        """
        data = self._read_data()
        self._logger.info("Configuración global obtenida correctamente.")
        return data.get("config", {})

    def set_config(self, config: Dict[str, Any]) -> None:
        """
        Actualiza la configuración global en el archivo JSON.
        Args:
            config (Dict[str, Any]): Nueva configuración global.
        """
        data = self._read_data()
        data["config"] = config
        self._write_data(data)
        self._logger.info("Configuración global actualizada correctamente.")
