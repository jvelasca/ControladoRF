"""Repositorio base genérico sobre SQLite."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, List, Optional, TypeVar

from ..connection import Database
from ..exceptions import DatabaseError, RecordNotFoundError

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """Operaciones CRUD comunes parametrizadas por tabla e identificador."""

    table_name: str
    id_column: str = "id"

    def __init__(self, db: Database) -> None:
        self._db = db

    @abstractmethod
    def _row_to_entity(self, row) -> T:
        """Convierte una fila sqlite3.Row en la entidad del repositorio."""

    def count(self) -> int:
        row = self._db.fetchone(f"SELECT COUNT(*) AS n FROM {self.table_name}")
        return int(row["n"]) if row else 0

    def exists(self, entity_id: int) -> bool:
        row = self._db.fetchone(
            f"SELECT 1 FROM {self.table_name} WHERE {self.id_column} = ?",
            (entity_id,),
        )
        return row is not None

    def get_by_id(self, entity_id: int) -> Optional[T]:
        row = self._db.fetchone(
            f"SELECT * FROM {self.table_name} WHERE {self.id_column} = ?",
            (entity_id,),
        )
        if row is None:
            return None
        return self._row_to_entity(row)

    def get_by_id_or_raise(self, entity_id: int) -> T:
        entity = self.get_by_id(entity_id)
        if entity is None:
            raise RecordNotFoundError(
                f"No existe registro en '{self.table_name}' con {self.id_column}={entity_id}"
            )
        return entity

    def list_all(self, order_by: str | None = None) -> List[T]:
        order_clause = order_by or self.id_column
        if not order_clause.replace("_", "").isalnum():
            raise DatabaseError(f"order_by no válido: {order_by}")
        rows = self._db.fetchall(
            f"SELECT * FROM {self.table_name} ORDER BY {order_clause}"
        )
        return [self._row_to_entity(row) for row in rows]

    def delete(self, entity_id: int) -> bool:
        cursor = self._db.execute(
            f"DELETE FROM {self.table_name} WHERE {self.id_column} = ?",
            (entity_id,),
        )
        return cursor.rowcount > 0

    def delete_all(self) -> int:
        cursor = self._db.execute(f"DELETE FROM {self.table_name}")
        return cursor.rowcount
