"""Excepciones de la capa de datos."""


class DatabaseError(Exception):
    """Error genérico de la capa db."""


class RecordNotFoundError(DatabaseError):
    """Registro solicitado inexistente."""
