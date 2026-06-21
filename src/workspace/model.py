from dataclasses import dataclass, field
import copy
from typing import Dict, Any
from utils.logger import log_error

@dataclass
class Workspace:
    """
    Modelo de datos para un workspace de la aplicación.

    Atributos:
        name (str): Nombre único del workspace.
        description (str): Descripción opcional del workspace.
        config (Dict[str, Any]): Diccionario de configuración serializable asociada al workspace.
        is_default (bool): Indica si es el workspace por defecto.

    Métodos:
        to_dict(): Serializa el workspace a un diccionario.
        from_dict(data): Crea una instancia Workspace desde un diccionario validando los campos.

    Notas:
        - El nombre debe ser único y no vacío.
        - El método from_dict valida tipos y estructura, y registra errores si los datos son inválidos.
    """
    name: str
    description: str = ""
    config: Dict[str, Any] = field(default_factory=lambda: {
        "language": "es",
        # Layout: dock_state, main_window_geometry, dock_sizes se rellenan en el primer arranque
    })
    is_default: bool = False

    def to_dict(self) -> dict:
        """
        Serializa el workspace a un diccionario para persistencia o exportación.
        Returns:
            dict: Representación serializable del workspace.
        """
        return {
            "name": self.name,
            "description": self.description,
            "config": copy.deepcopy(self.config),
            "is_default": self.is_default
        }

    @staticmethod
    def from_dict(data: dict) -> 'Workspace':
        """
        Crea una instancia Workspace desde un diccionario validando los campos.
        Args:
            data (dict): Diccionario con los datos del workspace.
        Returns:
            Workspace: Instancia creada o un workspace inválido si hay error.
        """
        try:
            if not isinstance(data, dict):
                raise ValueError("El dato para Workspace debe ser un diccionario.")
            name = data.get("name", "")
            if not isinstance(name, str) or not name:
                raise ValueError(f"Campo 'name' inválido en Workspace: {name}")
            description = data.get("description", "")
            if not isinstance(description, str):
                description = str(description)
            config = data.get("config", {})
            if not isinstance(config, dict):
                config = {}
            is_default = data.get("is_default", False)
            is_default = bool(is_default)
            return Workspace(
                name=name,
                description=description,
                config=copy.deepcopy(config),
                is_default=is_default
            )
        except Exception as e:
            log_error(f"[Workspace] Error al crear Workspace desde dict: {data}", exc=e)
            return Workspace(name="Invalid", description="Error de datos", config={}, is_default=False)
