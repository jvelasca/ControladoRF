"""
StatusBar
=========
Barra de estado principal de la aplicación.

Responsabilidad:
- Muestra mensajes de estado, información contextual y notificaciones al usuario.
- Permite actualizar el mensaje de estado desde otros módulos.
- No contiene lógica de negocio, solo UI y presentación.

Premisas:
- Modularidad y desacoplamiento.
- Uso de getters/setters y tipado fuerte.
- Documentación exhaustiva.
"""
from typing import Optional
from PyQt6.QtWidgets import QStatusBar
from i18n.json_translation import tr

class StatusBar(QStatusBar):
    """
    Barra de estado principal de la aplicación.
    Soporta recarga dinámica de textos para internacionalización.
    """
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_message: Optional[str] = None

    def show_status_message(self, message: str, timeout: int = 0) -> None:
        self._current_message = message
        self.showMessage(tr(message), timeout)

    def get_current_message(self) -> Optional[str]:
        return self._current_message

    def clear_status_message(self) -> None:
        self._current_message = None
        self.clearMessage()

    def recargar_textos(self) -> None:
        """
        Recarga el mensaje de estado actual (si lo hay) tras cambiar el idioma.
        """
        if self._current_message:
            self.showMessage(tr(self._current_message))
