"""Contenedor de servicios de negocio de la aplicación."""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.rf.channelization_service import ChannelizationService
from .services import InventoryService, ItemService

if TYPE_CHECKING:
    from db import DatabaseService


class ApplicationServices:
    """
    Punto de acceso único a servicios de negocio.

    Se construye tras inicializar DatabaseService y se inyecta en la GUI.
    """

    def __init__(
        self,
        item_service: ItemService,
        inventory_service: InventoryService,
        channelization_service: ChannelizationService,
    ) -> None:
        self.items = item_service
        self.inventory = inventory_service
        self.channelization = channelization_service

    @classmethod
    def from_database_service(cls, database_service: DatabaseService) -> ApplicationServices:
        return cls(
            item_service=ItemService(database_service.items),
            inventory_service=InventoryService(
                database_service.inventory_channels,
                database_service.inventory_scope_metadata,
            ),
            channelization_service=ChannelizationService(
                database_service.rf_standards,
                database_service.rf_channelization_prefs,
            ),
        )
