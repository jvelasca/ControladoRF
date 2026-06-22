"""Migraciones de esquema versionadas."""
from __future__ import annotations

from typing import List, Sequence, Tuple

from utils.logger import get_logger

from .connection import Database
from .exceptions import DatabaseError

Migration = Tuple[str, str]


def _execute_migration_sql(db: Database, sql: str) -> None:
    """Ejecuta una o varias sentencias SQL separadas por ';'."""
    for statement in (part.strip() for part in sql.split(";")):
        if statement:
            db.execute(statement)


MIGRATIONS: List[Migration] = [
    (
        "001_schema_version",
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version TEXT PRIMARY KEY NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """,
    ),
    (
        "002_app_metadata",
        """
        CREATE TABLE IF NOT EXISTS app_metadata (
            key TEXT PRIMARY KEY NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """,
    ),
    (
        "003_items",
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
        """,
    ),
    (
        "004_inventory_channels",
        """
        CREATE TABLE IF NOT EXISTS inventory_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_key TEXT NOT NULL,
            channel_key TEXT NOT NULL,
            channel_number INTEGER,
            channel_name TEXT NOT NULL DEFAULT '',
            device_name TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            series TEXT NOT NULL DEFAULT '',
            manufacturer TEXT NOT NULL DEFAULT '',
            band TEXT NOT NULL DEFAULT '',
            zone TEXT NOT NULL DEFAULT '',
            network TEXT NOT NULL DEFAULT '',
            device_type TEXT NOT NULL DEFAULT '',
            frequency_mhz REAL,
            frequency_khz INTEGER,
            source TEXT NOT NULL DEFAULT '',
            workbench_device_id TEXT NOT NULL DEFAULT '',
            workbench_channel_id TEXT NOT NULL DEFAULT '',
            coordination_include INTEGER,
            coordination_active INTEGER,
            payload_json TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(project_key, channel_key)
        );
        CREATE INDEX IF NOT EXISTS idx_inventory_channels_project
            ON inventory_channels(project_key);
        CREATE INDEX IF NOT EXISTS idx_inventory_channels_type
            ON inventory_channels(project_key, device_type);
        """,
    ),
    (
        "005_inventory_metadata",
        """
        ALTER TABLE inventory_channels ADD COLUMN notes TEXT NOT NULL DEFAULT '';
        ALTER TABLE inventory_channels ADD COLUMN color TEXT NOT NULL DEFAULT '';
        ALTER TABLE inventory_channels ADD COLUMN locked INTEGER NOT NULL DEFAULT 0;
        CREATE TABLE IF NOT EXISTS inventory_scope_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_key TEXT NOT NULL,
            scope_type TEXT NOT NULL,
            group_mode TEXT NOT NULL DEFAULT '',
            group_key TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            color TEXT NOT NULL DEFAULT '',
            locked INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(project_key, scope_type, group_mode, group_key)
        );
        CREATE INDEX IF NOT EXISTS idx_inventory_scope_project
            ON inventory_scope_metadata(project_key);
        """,
    ),
    (
        "006_supervision_events",
        """
        CREATE TABLE IF NOT EXISTS supervision_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_key TEXT NOT NULL,
            timestamp_utc TEXT NOT NULL,
            channel_key TEXT NOT NULL DEFAULT '',
            label TEXT NOT NULL DEFAULT '',
            frequency_mhz REAL,
            severity TEXT NOT NULL DEFAULT '',
            phase TEXT NOT NULL DEFAULT '',
            snr_db REAL,
            carrier_dbm REAL,
            noise_dbm REAL,
            threshold_db REAL,
            rule TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            ack_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_supervision_events_project_ts
            ON supervision_events(project_key, timestamp_utc DESC);
        CREATE INDEX IF NOT EXISTS idx_supervision_events_channel
            ON supervision_events(project_key, channel_key);
        """,
    ),
    (
        "007_supervision_event_alarm_type",
        """
        ALTER TABLE supervision_events ADD COLUMN alarm_type TEXT NOT NULL DEFAULT '';
        CREATE INDEX IF NOT EXISTS idx_supervision_events_type
            ON supervision_events(project_key, alarm_type);
        """,
    ),
    (
        "008_rf_channelization",
        """
        CREATE TABLE IF NOT EXISTS rf_standards (
            id TEXT PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            region_code TEXT NOT NULL,
            service_type TEXT NOT NULL,
            freq_min_hz REAL,
            freq_max_hz REAL,
            channel_spacing_hz REAL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            enabled INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS rf_standard_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_id TEXT NOT NULL,
            channel_number INTEGER,
            channel_label TEXT NOT NULL,
            center_freq_hz REAL NOT NULL,
            bandwidth_hz REAL NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (standard_id) REFERENCES rf_standards(id)
        );
        CREATE INDEX IF NOT EXISTS idx_rf_std_channels_standard
            ON rf_standard_channels(standard_id);
        CREATE TABLE IF NOT EXISTS rf_standard_regions (
            region_code TEXT NOT NULL,
            standard_id TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (region_code, standard_id),
            FOREIGN KEY (standard_id) REFERENCES rf_standards(id)
        );
        CREATE TABLE IF NOT EXISTS rf_channel_restrictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_id TEXT NOT NULL,
            label TEXT NOT NULL,
            freq_min_hz REAL NOT NULL,
            freq_max_hz REAL NOT NULL,
            severity TEXT NOT NULL DEFAULT 'warning',
            color_hex TEXT NOT NULL DEFAULT '#c0404088',
            message_key TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (standard_id) REFERENCES rf_standards(id)
        );
        CREATE INDEX IF NOT EXISTS idx_rf_restrictions_standard
            ON rf_channel_restrictions(standard_id);
        CREATE TABLE IF NOT EXISTS rf_app_channelization (
            key TEXT PRIMARY KEY NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """,
    ),
]


def get_applied_versions(db: Database) -> List[str]:
    try:
        rows = db.fetchall("SELECT version FROM schema_version ORDER BY version")
        return [row["version"] for row in rows]
    except DatabaseError:
        return []


def apply_migrations(db: Database, migrations: Sequence[Migration] | None = None) -> List[str]:
    """
    Aplica migraciones pendientes en orden.

    Returns:
        Lista de versiones aplicadas en esta ejecución.
    """
    logger = get_logger(__name__)
    pending_source = list(migrations or MIGRATIONS)
    applied = set(get_applied_versions(db))
    newly_applied: List[str] = []

    for version, sql in pending_source:
        if version in applied:
            continue
        with db.transaction():
            _execute_migration_sql(db, sql)
            db.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (version,),
            )
        newly_applied.append(version)
        logger.info("Migración aplicada: %s", version)

    return newly_applied


def ensure_migrations(db: Database) -> None:
    """Conecta si hace falta y aplica migraciones."""
    if not db.is_connected:
        db.connect()
    try:
        apply_migrations(db)
    except Exception as exc:
        raise DatabaseError(f"Error aplicando migraciones: {exc}") from exc
