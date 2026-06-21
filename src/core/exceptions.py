"""Excepciones de la capa de negocio."""
from __future__ import annotations


class CoreError(Exception):
    """Error genérico de la capa core."""


class ValidationError(CoreError):
    """Datos de entrada o regla de dominio incumplida."""


class DuplicateNameError(ValidationError):
    """Nombre duplicado en el dominio."""
