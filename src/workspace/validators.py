"""
validators.py
-------------
Validadores y reglas de negocio para workspaces.

Funciones:
    validate_name(name): Valida que el nombre de workspace sea válido (sin caracteres prohibidos ni reservados).
    is_unique(name, existing): Valida que el nombre no exista en la lista de workspaces.

Constantes:
    INVALID_CHARS: Expresión regular para caracteres no permitidos.
    RESERVED_NAMES: Conjunto de nombres reservados no permitidos.

Notas:
    - Los validadores pueden ampliarse para comprobar longitud, formato, etc.
    - Se recomienda mostrar mensajes de error descriptivos al usuario en la UI.
"""
import re
from typing import List

INVALID_CHARS = r'[^\w\- ]'
RESERVED_NAMES = {"Default", "last_workspace"}

def validate_name(name: str) -> bool:
    """
    Valida que el nombre de workspace sea válido.
    Reglas:
        - No puede estar vacío.
        - No puede contener caracteres prohibidos (ver INVALID_CHARS).
        - No puede ser un nombre reservado (ver RESERVED_NAMES).
    Args:
        name (str): Nombre a validar.
    Returns:
        bool: True si es válido, False si no.
    """
    if not name or re.search(INVALID_CHARS, name):
        return False
    if name in RESERVED_NAMES:
        return False
    return True

def is_unique(name: str, existing: List[str]) -> bool:
    """
    Valida que el nombre no exista en la lista de workspaces.
    Args:
        name (str): Nombre a comprobar.
        existing (List[str]): Lista de nombres existentes.
    Returns:
        bool: True si el nombre es único, False si ya existe.
    """
    return name not in existing
