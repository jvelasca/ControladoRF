"""Operaciones de mantenimiento y diagnóstico de SQLite."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from utils.logger import get_logger, log_error

from .connection import Database
from .exceptions import DatabaseError
from .migration import apply_migrations, get_applied_versions


@dataclass
class SqlExecutionResult:
    kind: str
    row_count: int
    columns: List[str]
    rows: List[List[str]]


@dataclass
class DatabaseStatus:
    connected: bool
    path: str
    size_bytes: int
    journal_mode: str
    foreign_keys: str
    synchronous: str
    page_count: int
    table_count: int
    schema_versions: List[str]


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    size = float(size_bytes)
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024.0
        if size < 1024.0:
            return f"{size:.1f} {unit}"
    return f"{size:.1f} PB"


class DatabaseMaintenance:
    """Métodos de mantenimiento sobre una conexión SQLite activa."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._logger = get_logger(__name__)

    def get_status(self) -> DatabaseStatus:
        path = self._db.config.path
        size_bytes = path.stat().st_size if path.exists() else 0
        connected = self._db.is_connected

        journal_mode = foreign_keys = synchronous = "—"
        page_count = table_count = 0
        schema_versions: List[str] = []

        if connected:
            journal_mode = self._pragma_value("journal_mode")
            foreign_keys = self._pragma_value("foreign_keys")
            synchronous = self._pragma_value("synchronous")
            page_count = int(self._pragma_value("page_count") or 0)
            table_row = self._db.fetchone(
                "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            table_count = int(table_row["n"]) if table_row else 0
            try:
                schema_versions = get_applied_versions(self._db)
            except DatabaseError:
                schema_versions = []

        return DatabaseStatus(
            connected=connected,
            path=str(path),
            size_bytes=size_bytes,
            journal_mode=journal_mode,
            foreign_keys=foreign_keys,
            synchronous=synchronous,
            page_count=page_count,
            table_count=table_count,
            schema_versions=schema_versions,
        )

    def check_integrity(self) -> Tuple[bool, str]:
        rows = self._db.fetchall("PRAGMA integrity_check")
        if not rows:
            return False, "integrity_check returned no rows"
        message = str(rows[0][0])
        ok = message.lower() == "ok"
        return ok, message

    def vacuum(self) -> None:
        self._db.execute("VACUUM")
        self._logger.info("VACUUM ejecutado en %s", self._db.config.path)

    def analyze(self) -> None:
        self._db.execute("ANALYZE")
        self._logger.info("ANALYZE ejecutado en %s", self._db.config.path)

    def backup(self, destination: Optional[Path] = None, backup_dir: Optional[Path] = None) -> Path:
        target_dir = backup_dir or self._db.config.path.parent / "backups"
        target_dir.mkdir(parents=True, exist_ok=True)

        if destination is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            destination = target_dir / f"{self._db.config.path.stem}_{stamp}.db"

        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            source = self._db._require_connection()
            dest_conn = sqlite3.connect(destination)
            try:
                source.backup(dest_conn)
            finally:
                dest_conn.close()
        except sqlite3.Error as exc:
            log_error("[DatabaseMaintenance] Error en backup", exc)
            raise DatabaseError(str(exc)) from exc

        self._logger.info("Copia de seguridad creada: %s", destination)
        return destination

    def apply_migrations(self) -> List[str]:
        applied = apply_migrations(self._db)
        if applied:
            self._logger.info("Migraciones aplicadas: %s", ", ".join(applied))
        return applied

    def list_user_tables(self) -> List[str]:
        if not self._db.is_connected:
            return []
        rows = self._db.fetchall(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name COLLATE NOCASE
            """
        )
        return [str(row["name"]) for row in rows]

    def table_row_counts(self) -> List[tuple[str, int]]:
        counts: List[tuple[str, int]] = []
        for name in self.list_user_tables():
            counts.append((name, self.count_table_rows(name)))
        return counts

    def count_table_rows(self, table_name: str) -> int:
        safe = self._validate_table_name(table_name)
        row = self._db.fetchone(f"SELECT COUNT(*) AS n FROM {safe}")
        return int(row["n"]) if row else 0

    def fetch_table_preview(
        self,
        table_name: str,
        *,
        limit: int = 50,
    ) -> tuple[list[str], list[list[str]]]:
        safe = self._validate_table_name(table_name)
        limit = max(1, min(int(limit), 500))
        rows = self._db.fetchall(f"SELECT * FROM {safe} LIMIT ?", (limit,))
        if not rows:
            return [], []
        columns = list(rows[0].keys())
        data = [[str(row[col]) if row[col] is not None else "" for col in columns] for row in rows]
        return columns, data

    def execute_sql(self, sql: str) -> SqlExecutionResult:
        statement = sql.strip()
        if not statement:
            raise DatabaseError("Consulta vacía.")
        if statement.endswith(";"):
            statement = statement[:-1].strip()
        upper = statement.upper()
        if upper.startswith("SELECT") or upper.startswith("PRAGMA"):
            rows = self._db.fetchall(statement)
            if not rows:
                return SqlExecutionResult("select", 0, [], [])
            columns = list(rows[0].keys())
            data = [
                [str(row[col]) if row[col] is not None else "" for col in columns]
                for row in rows
            ]
            return SqlExecutionResult("select", len(data), columns, data)
        cursor = self._db.execute(statement)
        return SqlExecutionResult("exec", int(cursor.rowcount), [], [])

    @staticmethod
    def _validate_table_name(table_name: str) -> str:
        name = table_name.strip()
        if not name or not name.replace("_", "").isalnum():
            raise DatabaseError(f"Nombre de tabla no válido: {table_name!r}")
        return name

    def _pragma_value(self, name: str) -> str:
        row = self._db.fetchone(f"PRAGMA {name}")
        if row is None:
            return ""
        return str(row[0])
