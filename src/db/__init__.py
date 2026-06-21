"""
db
--
Capa genérica de acceso a datos (SQLite).
"""
from .config import DatabaseConfig, config_for_data_dir
from .connection import Database
from .exceptions import DatabaseError, RecordNotFoundError
from .maintenance import DatabaseMaintenance, DatabaseStatus, format_file_size
from .migration import MIGRATIONS, apply_migrations, ensure_migrations, get_applied_versions
from .models import Item
from .repositories import BaseRepository, ItemRepository
from .service import DatabaseService
from .settings import JOURNAL_MODES, SYNCHRONOUS_MODES, DatabaseSettings

__all__ = [
    "BaseRepository",
    "Database",
    "DatabaseConfig",
    "DatabaseError",
    "DatabaseMaintenance",
    "DatabaseService",
    "DatabaseSettings",
    "DatabaseStatus",
    "Item",
    "ItemRepository",
    "JOURNAL_MODES",
    "MIGRATIONS",
    "RecordNotFoundError",
    "SYNCHRONOUS_MODES",
    "apply_migrations",
    "config_for_data_dir",
    "ensure_migrations",
    "format_file_size",
    "get_applied_versions",
]
