"""Repositorio de ejemplo sobre la tabla `items`."""
from __future__ import annotations

from typing import List, Optional

from ..connection import Database
from ..exceptions import DatabaseError
from ..models.item import Item
from .base import BaseRepository


class ItemRepository(BaseRepository[Item]):
    table_name = "items"

    def __init__(self, db: Database) -> None:
        super().__init__(db)

    def _row_to_entity(self, row) -> Item:
        return Item(
            id=int(row["id"]),
            name=str(row["name"]),
            description=str(row["description"] or ""),
            created_at=str(row["created_at"]) if row["created_at"] else None,
            updated_at=str(row["updated_at"]) if row["updated_at"] else None,
        )

    def create(self, name: str, description: str = "") -> Item:
        name = name.strip()
        if not name:
            raise DatabaseError("El nombre del item no puede estar vacío.")
        with self._db.transaction():
            cursor = self._db.execute(
                "INSERT INTO items (name, description) VALUES (?, ?)",
                (name, description.strip()),
            )
            item_id = int(cursor.lastrowid)
        return self.get_by_id_or_raise(item_id)

    def update(self, item: Item) -> Item:
        if item.id is None:
            raise DatabaseError("Se requiere id para actualizar un item.")
        name = item.name.strip()
        if not name:
            raise DatabaseError("El nombre del item no puede estar vacío.")
        with self._db.transaction():
            self._db.execute(
                """
                UPDATE items
                SET name = ?, description = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (name, item.description.strip(), item.id),
            )
        return self.get_by_id_or_raise(item.id)

    def find_by_name(self, name: str) -> Optional[Item]:
        row = self._db.fetchone(
            "SELECT * FROM items WHERE name = ? COLLATE NOCASE",
            (name.strip(),),
        )
        return self._row_to_entity(row) if row else None

    def search_by_name(self, query: str) -> List[Item]:
        pattern = f"%{query.strip()}%"
        rows = self._db.fetchall(
            "SELECT * FROM items WHERE name LIKE ? ORDER BY name COLLATE NOCASE",
            (pattern,),
        )
        return [self._row_to_entity(row) for row in rows]
