"""Repositorio SQLite de canales RF por proyecto."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..connection import Database
from ..models.inventory_channel import InventoryChannel
from .base import BaseRepository


class InventoryChannelRepository(BaseRepository[InventoryChannel]):
    table_name = "inventory_channels"

    def _row_to_entity(self, row) -> InventoryChannel:
        return InventoryChannel(
            id=int(row["id"]),
            project_key=str(row["project_key"]),
            channel_key=str(row["channel_key"]),
            channel_number=_optional_int(row["channel_number"]),
            channel_name=str(row["channel_name"] or ""),
            device_name=str(row["device_name"] or ""),
            model=str(row["model"] or ""),
            series=str(row["series"] or ""),
            manufacturer=str(row["manufacturer"] or ""),
            band=str(row["band"] or ""),
            zone=str(row["zone"] or ""),
            network=str(row["network"] or ""),
            device_type=str(row["device_type"] or ""),
            frequency_mhz=_optional_float(row["frequency_mhz"]),
            frequency_khz=_optional_int(row["frequency_khz"]),
            source=str(row["source"] or ""),
            workbench_device_id=str(row["workbench_device_id"] or ""),
            workbench_channel_id=str(row["workbench_channel_id"] or ""),
            coordination_include=_optional_bool(row["coordination_include"]),
            coordination_active=_optional_bool(row["coordination_active"]),
            notes=str(row["notes"] or "") if "notes" in row.keys() else "",
            color=str(row["color"] or "") if "color" in row.keys() else "",
            locked=bool(_optional_bool(row["locked"])) if "locked" in row.keys() else False,
            payload_json=str(row["payload_json"] or ""),
            updated_at=str(row["updated_at"]) if row["updated_at"] else None,
        )

    def list_by_project(self, project_key: str) -> List[InventoryChannel]:
        rows = self._db.fetchall(
            """
            SELECT * FROM inventory_channels
            WHERE project_key = ?
            ORDER BY device_type, channel_number, channel_name
            """,
            (project_key,),
        )
        return [self._row_to_entity(row) for row in rows]

    def get_by_project_and_key(
        self, project_key: str, channel_key: str
    ) -> Optional[InventoryChannel]:
        row = self._db.fetchone(
            """
            SELECT * FROM inventory_channels
            WHERE project_key = ? AND channel_key = ?
            """,
            (project_key, channel_key),
        )
        return self._row_to_entity(row) if row else None

    def replace_project_channels(
        self, project_key: str, equipos: List[Dict[str, Any]]
    ) -> int:
        with self._db.transaction():
            self._db.execute(
                "DELETE FROM inventory_channels WHERE project_key = ?",
                (project_key,),
            )
            count = 0
            for item in equipos:
                self._insert_channel(project_key, item)
                count += 1
        return count

    def _insert_channel(self, project_key: str, item: Dict[str, Any]) -> None:
        payload = {
            key: value
            for key, value in item.items()
            if key not in _PERSISTED_COLUMNS
        }
        self._db.execute(
            """
            INSERT INTO inventory_channels (
                project_key, channel_key, channel_number, channel_name,
                device_name, model, series, manufacturer, band, zone, network,
                device_type, frequency_mhz, frequency_khz, source,
                workbench_device_id, workbench_channel_id,
                coordination_include, coordination_active,
                notes, color, locked, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_key,
                str(item.get("channel_key") or ""),
                item.get("channel_number"),
                str(item.get("channel_name") or ""),
                str(item.get("device_name") or ""),
                str(item.get("model") or ""),
                str(item.get("series") or ""),
                str(item.get("manufacturer") or ""),
                str(item.get("band") or ""),
                str(item.get("zone") or ""),
                str(item.get("network") or ""),
                str(item.get("device_type") or ""),
                item.get("frequency_mhz"),
                item.get("frequency_khz"),
                str(item.get("source") or ""),
                str(item.get("workbench_device_id") or ""),
                str(item.get("workbench_channel_id") or ""),
                _bool_to_int(item.get("coordination_include")),
                _bool_to_int(item.get("coordination_active")),
                str(item.get("notes") or ""),
                str(item.get("color") or ""),
                1 if bool(item.get("locked")) else 0,
                json.dumps(payload, ensure_ascii=False) if payload else "",
            ),
        )


_PERSISTED_COLUMNS = {
    "channel_key",
    "channel_number",
    "channel_name",
    "device_name",
    "model",
    "series",
    "manufacturer",
    "band",
    "zone",
    "network",
    "device_type",
    "frequency_mhz",
    "frequency_khz",
    "source",
    "workbench_device_id",
    "workbench_channel_id",
    "coordination_include",
    "coordination_active",
    "notes",
    "color",
    "locked",
    "db_id",
}


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def _optional_bool(value: Any) -> Optional[bool]:
    if value is None or value == "":
        return None
    return bool(int(value))


def _bool_to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    return 1 if bool(value) else 0
