"""
core
----
Lógica de negocio reutilizable, desacoplada de PyQt6.
"""
from .app_services import ApplicationServices
from .exceptions import CoreError, DuplicateNameError, ValidationError
from .services import ItemService

__all__ = [
    "ApplicationServices",
    "CoreError",
    "DuplicateNameError",
    "ItemService",
    "ValidationError",
]
