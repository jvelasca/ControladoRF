"""Repositorio SQLite de metadatos de lista/grupo del inventario."""
from __future__ import annotations

from typing import Any, Dict, List

from ..models.inventory_scope_metadata import InventoryScopeMetadata
from .base import BaseRepository
from .inventory_channel_repository import _bool_to_int, _optional_bool


class InventoryScopeMetadataRepository(BaseRepository[InventoryScopeMetadata]):
    table_name = "inventory_scope_metadata"

    def _row_to_entity(self, row) -> InventoryScopeMetadata:
        return InventoryScopeMetadata(
            id=int(row["id"]),
            project_key=str(row["project_key"]),
            scope_type=str(row["scope_type"]),
            group_mode=str(row["group_mode"] or ""),
            group_key=str(row["group_key"] or ""),
            notes=str(row["notes"] or ""),
            color=str(row["color"] or ""),
            locked=bool(_optional_bool(row["locked"])),
            updated_at=str(row["updated_at"]) if row["updated_at"] else None,
        )

    def replace_project_metadata(
        self,
        project_key: str,
        *,
        list_metadata: Dict[str, Any],
        group_entries: List[tuple[str, str, Dict[str, Any]]],
    ) -> int:
        with self._db.transaction():
            self._db.execute(
                "DELETE FROM inventory_scope_metadata WHERE project_key = ?",
                (project_key,),
            )
            count = 0
            self._insert_row(project_key, "list", "", "", list_metadata)
            count += 1
            for group_mode, group_key, meta in group_entries:
                self._insert_row(project_key, "group", group_mode, group_key, meta)
                count += 1
        return count

    def _insert_row(
        self,
        project_key: str,
        scope_type: str,
        group_mode: str,
        group_key: str,
        meta: Dict[str, Any],
    ) -> None:
        self._db.execute(
            """
            INSERT INTO inventory_scope_metadata (
                project_key, scope_type, group_mode, group_key,
                notes, color, locked
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_key,
                scope_type,
                group_mode,
                group_key,
                str(meta.get("notes") or ""),
                str(meta.get("color") or ""),
                1 if bool(meta.get("locked")) else 0,
            ),
        )
