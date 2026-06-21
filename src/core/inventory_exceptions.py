"""Excepciones de edición del inventario RF."""


class InventoryLockedError(Exception):
    """Operación bloqueada por metadatos de bloqueo."""
