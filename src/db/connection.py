"""Conexión SQLite genérica con transacciones."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator, List, Optional, Sequence, Tuple

from utils.logger import get_logger, log_error

from .config import DatabaseConfig
from .exceptions import DatabaseError

Row = sqlite3.Row


class Database:
    """Gestor de conexión SQLite. Una conexión por instancia."""

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config
        self._connection: Optional[sqlite3.Connection] = None
        self._logger = get_logger(__name__)

    @property
    def config(self) -> DatabaseConfig:
        return self._config

    @property
    def is_connected(self) -> bool:
        return self._connection is not None

    def connect(self) -> sqlite3.Connection:
        if self._connection is not None:
            return self._connection
        try:
            self._config.ensure_parent_dir()
            conn = sqlite3.connect(
                self._config.path,
                timeout=self._config.timeout_seconds,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            for key, value in self._config.pragmas.items():
                conn.execute(f"PRAGMA {key} = {value}")
            self._connection = conn
            self._logger.info("Base de datos conectada: %s", self._config.path)
            return conn
        except sqlite3.Error as exc:
            log_error("[Database] Error al conectar", exc)
            raise DatabaseError(str(exc)) from exc

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            self._logger.info("Base de datos cerrada: %s", self._config.path)

    def reconfigure(self, config: DatabaseConfig) -> None:
        """Cierra y vuelve a abrir con una nueva configuración."""
        self.close()
        self._config = config
        self.connect()

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise DatabaseError("La base de datos no está conectada.")
        return self._connection

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        try:
            return self._require_connection().execute(sql, params)
        except sqlite3.Error as exc:
            log_error(f"[Database] Error ejecutando SQL: {sql}", exc)
            raise DatabaseError(str(exc)) from exc

    def executemany(self, sql: str, params_seq: Sequence[Sequence[Any]]) -> sqlite3.Cursor:
        try:
            return self._require_connection().executemany(sql, params_seq)
        except sqlite3.Error as exc:
            log_error(f"[Database] Error ejecutando SQL batch: {sql}", exc)
            raise DatabaseError(str(exc)) from exc

    def fetchone(self, sql: str, params: Sequence[Any] = ()) -> Optional[Row]:
        return self.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: Sequence[Any] = ()) -> List[Row]:
        return self.execute(sql, params).fetchall()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._require_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
