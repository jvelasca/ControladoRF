"""Configuración de la base de datos."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass
class DatabaseConfig:
    """Parámetros de conexión SQLite."""

    path: Path
    pragmas: Dict[str, str] = field(
        default_factory=lambda: {
            "journal_mode": "WAL",
            "foreign_keys": "ON",
            "synchronous": "NORMAL",
        }
    )
    timeout_seconds: float = 30.0

    def ensure_parent_dir(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)


def config_for_data_dir(data_dir: str | Path) -> DatabaseConfig:
    """Crea la configuración por defecto (`app.db`) junto a `workspaces.json`."""
    return DatabaseConfig(path=Path(data_dir) / "app.db")
