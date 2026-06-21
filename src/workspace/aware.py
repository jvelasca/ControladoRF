from typing import Dict, Any
from abc import abstractmethod

class WorkspaceAware:
    """
    Interfaz para componentes que deben guardar/restaurar estado por workspace.

    Contrato:
        - save_state(self) -> dict: Devuelve un diccionario serializable con el estado a guardar.
        - restore_state(self, config: dict) -> None: Restaura el estado desde el diccionario de configuración.

    Ejemplo de uso:
        class MiComponente(QWidget, WorkspaceAware):
            def save_state(self) -> dict:
                return {"valor": self.valor}
            def restore_state(self, config: dict) -> None:
                self.valor = config.get("valor", 0)

    Notas:
        - Los métodos deben ser implementados por las subclases.
        - Si el componente no necesita guardar nada, save_state debe devolver un dict vacío y restore_state aceptar el argumento pero no hacer nada.
    """
    @abstractmethod
    def save_state(self) -> Dict[str, Any]:
        """
        Devuelve el estado serializable del componente para persistencia por workspace.
        Returns:
            dict: Estado serializable.
        """
        raise NotImplementedError

    @abstractmethod
    def restore_state(self, config: Dict[str, Any]) -> None:
        """
        Restaura el estado del componente desde el diccionario de configuración del workspace.
        Args:
            config (dict): Diccionario de configuración del workspace activo.
        """
        raise NotImplementedError
