"""Preferencias globales de canalización RF (tabla rf_app_channelization)."""
from __future__ import annotations

from typing import Dict

from ..connection import Database


class RfChannelizationPrefsRepository:
    """Clave-valor para el modo canal en toda la APP."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def get_all(self) -> Dict[str, str]:
        rows = self._db.fetchall("SELECT key, value FROM rf_app_channelization")
        return {str(row["key"]): str(row["value"]) for row in rows}

    def get(self, key: str, default: str = "") -> str:
        row = self._db.fetchone(
            "SELECT value FROM rf_app_channelization WHERE key = ?",
            (key,),
        )
        return str(row["value"]) if row else default

    def set(self, key: str, value: str) -> None:
        self._db.execute(
            """
            INSERT INTO rf_app_channelization (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = datetime('now')
            """,
            (key, value),
        )

    def set_many(self, values: Dict[str, str]) -> None:
        with self._db.transaction():
            for key, value in values.items():
                self.set(key, value)
