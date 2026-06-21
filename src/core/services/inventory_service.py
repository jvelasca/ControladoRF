"""Reglas de negocio del inventario RF persistido."""
from __future__ import annotations

from typing import Dict, List, Optional

from core.inventory_channel import (
    channel_key,
    equipos_from_project,
    find_equipo_in_list,
    normalize_equipo,
    project_storage_key,
)
from core.inventory_metadata import get_list_metadata, iter_group_metadata_entries
from db.models.inventory_channel import InventoryChannel
from db.repositories.inventory_channel_repository import InventoryChannelRepository
from db.repositories.inventory_scope_metadata_repository import InventoryScopeMetadataRepository


class InventoryService:
    """Sincroniza inventario del proyecto `.crf` con SQLite."""

    def __init__(
        self,
        repository: InventoryChannelRepository,
        scope_repository: InventoryScopeMetadataRepository | None = None,
    ) -> None:
        self._repo = repository
        self._scope_repo = scope_repository

    def sync_project(self, project, file_path: Optional[str] = None) -> int:
        """Reemplaza en BD los canales y metadatos del proyecto abierto."""
        pkey = project_storage_key(file_path, project.name)
        equipos = equipos_from_project(project)
        count = self._repo.replace_project_channels(pkey, equipos)
        if self._scope_repo:
            self._scope_repo.replace_project_metadata(
                pkey,
                list_metadata=get_list_metadata(project),
                group_entries=iter_group_metadata_entries(project),
            )
        return count

    def list_channels(self, project, file_path: Optional[str] = None) -> List[InventoryChannel]:
        pkey = project_storage_key(file_path, project.name)
        return self._repo.list_by_project(pkey)

    def get_channel(
        self,
        project,
        channel_key_value: str,
        *,
        file_path: Optional[str] = None,
    ) -> Optional[InventoryChannel]:
        pkey = project_storage_key(file_path, project.name)
        return self._repo.get_by_project_and_key(pkey, channel_key_value)

    def resolve_equipo(
        self,
        project,
        item: Dict,
        *,
        file_path: Optional[str] = None,
    ) -> Dict:
        """Resuelve el dict completo del canal desde proyecto (+ metadatos BD)."""
        key = channel_key(item)
        found = find_equipo_in_list(equipos_from_project(project), key)
        merged = normalize_equipo(found or dict(item))
        record = self.get_channel(project, key, file_path=file_path)
        if record:
            merged["db_id"] = record.id
            if record.notes:
                merged.setdefault("notes", record.notes)
            if record.color:
                merged.setdefault("color", record.color)
            if record.locked:
                merged.setdefault("locked", record.locked)
        return merged
