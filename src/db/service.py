"""Servicio de alto nivel: configuración, conexión y mantenimiento."""
from __future__ import annotations

from utils.logger import get_logger, log_error

from .connection import Database
from .exceptions import DatabaseError
from .maintenance import DatabaseMaintenance
from .migration import ensure_migrations
from core.rf.channelization_seed import ensure_channelization_seed
from .repositories import (
    ItemRepository,
    InventoryChannelRepository,
    InventoryScopeMetadataRepository,
    RfChannelizationPrefsRepository,
    RfStandardRepository,
    SupervisionEventRepository,
)
from .settings import DatabaseSettings


class DatabaseService:
    """Orquesta settings, conexión SQLite y operaciones de mantenimiento."""

    def __init__(self, data_dir: str, store_get_config, store_set_config) -> None:
        self._data_dir = data_dir
        self._get_config = store_get_config
        self._set_config = store_set_config
        self._settings = self._load_settings()
        self._db = Database(self._settings.to_database_config(data_dir))
        self._maintenance = DatabaseMaintenance(self._db)
        self._items = ItemRepository(self._db)
        self._inventory_channels = InventoryChannelRepository(self._db)
        self._inventory_scope_metadata = InventoryScopeMetadataRepository(self._db)
        self._supervision_events = SupervisionEventRepository(self._db)
        self._rf_standards = RfStandardRepository(self._db)
        self._rf_channelization_prefs = RfChannelizationPrefsRepository(self._db)
        self._logger = get_logger(__name__)

    @property
    def settings(self) -> DatabaseSettings:
        return self._settings

    @property
    def database(self) -> Database:
        return self._db

    @property
    def maintenance(self) -> DatabaseMaintenance:
        return self._maintenance

    @property
    def items(self) -> ItemRepository:
        return self._items

    @property
    def inventory_channels(self) -> InventoryChannelRepository:
        return self._inventory_channels

    @property
    def inventory_scope_metadata(self) -> InventoryScopeMetadataRepository:
        return self._inventory_scope_metadata

    @property
    def supervision_events(self) -> SupervisionEventRepository:
        return self._supervision_events

    @property
    def rf_standards(self) -> RfStandardRepository:
        return self._rf_standards

    @property
    def rf_channelization_prefs(self) -> RfChannelizationPrefsRepository:
        return self._rf_channelization_prefs

    @property
    def data_dir(self) -> str:
        return self._data_dir

    def _load_settings(self) -> DatabaseSettings:
        config = self._get_config() or {}
        return DatabaseSettings.from_dict(config.get("database"))

    def startup(self) -> None:
        ensure_migrations(self._db)
        ensure_channelization_seed(self._db)
        if self._settings.auto_backup_on_startup:
            try:
                self._maintenance.backup(backup_dir=self._settings.resolved_backup_dir(self._data_dir))
            except DatabaseError as exc:
                log_error("[DatabaseService] Copia automática al iniciar fallida", exc)

    def save_settings(self, settings: DatabaseSettings) -> None:
        config = dict(self._get_config() or {})
        config["database"] = settings.to_dict()
        self._set_config(config)
        self._settings = settings
        self._logger.info("Configuración de base de datos guardada")

    def reconnect(self) -> None:
        self._db.reconfigure(self._settings.to_database_config(self._data_dir))
        ensure_migrations(self._db)
        ensure_channelization_seed(self._db)
        self._logger.info("Base de datos reconectada con nueva configuración")

    def close(self) -> None:
        self._db.close()
