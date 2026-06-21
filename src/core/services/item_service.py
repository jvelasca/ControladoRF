"""Reglas de dominio y operaciones sobre items."""
from __future__ import annotations

from typing import List, Optional

from db.exceptions import RecordNotFoundError
from db.models.item import Item
from db.repositories.item_repository import ItemRepository

from ..exceptions import DuplicateNameError, ValidationError

NAME_MAX_LENGTH = 100
DESCRIPTION_MAX_LENGTH = 500


class ItemService:
    """
    Servicio de negocio para items.

    Encapsula validaciones de dominio y reglas (p. ej. nombres únicos).
    La persistencia delega en ItemRepository.
    """

    def __init__(self, repository: ItemRepository) -> None:
        self._repo = repository

    def list_items(self) -> List[Item]:
        return self._repo.list_all(order_by="name")

    def get_item(self, item_id: int) -> Item:
        return self._repo.get_by_id_or_raise(item_id)

    def find_item_by_name(self, name: str) -> Optional[Item]:
        normalized = self._normalize_name(name)
        if not normalized:
            return None
        return self._repo.find_by_name(normalized)

    def search_items(self, query: str) -> List[Item]:
        query = query.strip()
        if not query:
            return self.list_items()
        return self._repo.search_by_name(query)

    def create_item(self, name: str, description: str = "") -> Item:
        normalized_name = self._validate_name(name)
        normalized_desc = self._validate_description(description)
        self._ensure_unique_name(normalized_name)
        return self._repo.create(normalized_name, normalized_desc)

    def update_item(self, item_id: int, name: str, description: str) -> Item:
        existing = self._repo.get_by_id_or_raise(item_id)
        normalized_name = self._validate_name(name)
        normalized_desc = self._validate_description(description)
        if normalized_name.lower() != existing.name.lower():
            self._ensure_unique_name(normalized_name, exclude_id=item_id)
        return self._repo.update(
            Item(
                id=item_id,
                name=normalized_name,
                description=normalized_desc,
                created_at=existing.created_at,
                updated_at=existing.updated_at,
            )
        )

    def delete_item(self, item_id: int) -> bool:
        if not self._repo.exists(item_id):
            raise RecordNotFoundError(f"No existe item con id={item_id}")
        return self._repo.delete(item_id)

    def count_items(self) -> int:
        return self._repo.count()

    def _normalize_name(self, name: str) -> str:
        return " ".join(name.strip().split())

    def _validate_name(self, name: str) -> str:
        normalized = self._normalize_name(name)
        if not normalized:
            raise ValidationError("El nombre no puede estar vacío.")
        if len(normalized) > NAME_MAX_LENGTH:
            raise ValidationError(
                f"El nombre no puede superar {NAME_MAX_LENGTH} caracteres."
            )
        return normalized

    def _validate_description(self, description: str) -> str:
        value = description.strip()
        if len(value) > DESCRIPTION_MAX_LENGTH:
            raise ValidationError(
                f"La descripción no puede superar {DESCRIPTION_MAX_LENGTH} caracteres."
            )
        return value

    def _ensure_unique_name(self, name: str, exclude_id: int | None = None) -> None:
        existing = self._repo.find_by_name(name)
        if existing is None:
            return
        if exclude_id is not None and existing.id == exclude_id:
            return
        raise DuplicateNameError(f"Ya existe un item con el nombre '{name}'.")
