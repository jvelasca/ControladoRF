"""Configuración persistente de la base de datos."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from .config import DatabaseConfig

JOURNAL_MODES = ("WAL", "DELETE", "TRUNCATE", "PERSIST", "MEMORY", "OFF")
SYNCHRONOUS_MODES = ("OFF", "NORMAL", "FULL", "EXTRA")


@dataclass
class DatabaseSettings:
    """Parámetros de SQLite guardados en la configuración global de la app."""

    db_filename: str = "app.db"
    journal_mode: str = "WAL"
    foreign_keys: bool = True
    synchronous: str = "NORMAL"
    timeout_seconds: float = 30.0
    backup_dir: str = ""
    auto_backup_on_startup: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> DatabaseSettings:
        if not data:
            return cls()
        journal_mode = str(data.get("journal_mode", "WAL")).upper()
        synchronous = str(data.get("synchronous", "NORMAL")).upper()
        return cls(
            db_filename=str(data.get("db_filename", "app.db")),
            journal_mode=journal_mode if journal_mode in JOURNAL_MODES else "WAL",
            foreign_keys=bool(data.get("foreign_keys", True)),
            synchronous=synchronous if synchronous in SYNCHRONOUS_MODES else "NORMAL",
            timeout_seconds=float(data.get("timeout_seconds", 30.0)),
            backup_dir=str(data.get("backup_dir", "")),
            auto_backup_on_startup=bool(data.get("auto_backup_on_startup", False)),
        )

    def resolved_path(self, data_dir: str | Path) -> Path:
        name = self.db_filename.strip() or "app.db"
        if any(sep in name for sep in ("/", "\\", "..")):
            name = "app.db"
        return Path(data_dir) / name

    def resolved_backup_dir(self, data_dir: str | Path) -> Path:
        if self.backup_dir.strip():
            return Path(self.backup_dir.strip())
        return Path(data_dir) / "backups"

    def to_database_config(self, data_dir: str | Path) -> DatabaseConfig:
        pragmas: Dict[str, str] = {
            "journal_mode": self.journal_mode,
            "foreign_keys": "ON" if self.foreign_keys else "OFF",
            "synchronous": self.synchronous,
        }
        return DatabaseConfig(
            path=self.resolved_path(data_dir),
            pragmas=pragmas,
            timeout_seconds=self.timeout_seconds,
        )
