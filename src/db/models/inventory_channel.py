"""Modelo de canal RF persistido en SQLite."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class InventoryChannel:
    """Canal RF de un proyecto almacenado en `inventory_channels`."""

    id: Optional[int]
    project_key: str
    channel_key: str
    channel_number: Optional[int] = None
    channel_name: str = ""
    device_name: str = ""
    model: str = ""
    series: str = ""
    manufacturer: str = ""
    band: str = ""
    zone: str = ""
    network: str = ""
    device_type: str = ""
    frequency_mhz: Optional[float] = None
    frequency_khz: Optional[int] = None
    source: str = ""
    workbench_device_id: str = ""
    workbench_channel_id: str = ""
    coordination_include: Optional[bool] = None
    coordination_active: Optional[bool] = None
    notes: str = ""
    color: str = ""
    locked: bool = False
    payload_json: str = ""
    updated_at: Optional[str] = None

    def to_equipo_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "channel_key": self.channel_key,
            "channel_number": self.channel_number,
            "channel_name": self.channel_name,
            "device_name": self.device_name,
            "model": self.model,
            "series": self.series,
            "manufacturer": self.manufacturer,
            "band": self.band,
            "zone": self.zone,
            "network": self.network,
            "device_type": self.device_type,
            "frequency_mhz": self.frequency_mhz,
            "frequency_khz": self.frequency_khz,
            "source": self.source,
            "workbench_device_id": self.workbench_device_id,
            "workbench_channel_id": self.workbench_channel_id,
            "db_id": self.id,
        }
        if self.coordination_include is not None:
            data["coordination_include"] = self.coordination_include
        if self.coordination_active is not None:
            data["coordination_active"] = self.coordination_active
        data["notes"] = self.notes
        if self.color:
            data["color"] = self.color
        if self.locked:
            data["locked"] = self.locked
        return data
