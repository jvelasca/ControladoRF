"""Modelos intermedios al importar un show de Shure Wireless Workbench (.shw)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class WorkbenchContact:
    name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""


@dataclass
class WorkbenchShowInfo:
    name: str = ""
    customer: str = ""
    contact: WorkbenchContact = field(default_factory=WorkbenchContact)
    notes: str = ""


@dataclass
class WorkbenchChannel:
    number: int
    name: str = ""
    frequency_khz: Optional[int] = None
    frequency_mhz: Optional[float] = None
    color: Optional[int] = None
    audio_gain: Optional[float] = None
    audio_mute: bool = False


@dataclass
class WorkbenchDevice:
    id: str
    dcid: str = ""
    device_name: str = ""
    series: str = ""
    model: str = ""
    manufacturer: str = ""
    band: str = ""
    zone: str = ""
    channels: List[WorkbenchChannel] = field(default_factory=list)


@dataclass
class WorkbenchShow:
    """Show completo extraído de un fichero `.shw` (XML)."""

    source_path: str
    workbench_version: str = ""
    show_date: str = ""
    show_time: str = ""
    info: WorkbenchShowInfo = field(default_factory=WorkbenchShowInfo)
    devices: List[WorkbenchDevice] = field(default_factory=list)
    has_coordination: bool = False
    has_monitoring: bool = False
    coordination: Optional["WorkbenchCoordination"] = None
    channel_dev_types: Dict[str, List[str]] = field(default_factory=dict)

    @property
    def channel_count(self) -> int:
        return sum(len(device.channels) for device in self.devices)

    def to_inventory_dicts(self) -> List[Dict[str, Any]]:
        """Convierte inventario a listas dict para `project.modules.inventario_rf.equipos`."""
        from core.inventory_catalog import enrich_equipo_metadata

        equipos: List[Dict[str, Any]] = []
        for device in self.devices:
            for ch_index, channel in enumerate(device.channels):
                channel_id = _workbench_channel_id(
                    device.id, ch_index, len(device.channels)
                )
                payload: Dict[str, Any] = {
                    "source": "workbench",
                    "workbench_device_id": device.id,
                    "workbench_channel_id": channel_id,
                    "workbench_dcid": device.dcid,
                    "device_name": device.device_name,
                    "series": device.series,
                    "model": device.model,
                    "manufacturer": device.manufacturer,
                    "band": device.band,
                    "zone": device.zone,
                    "channel_number": channel.number,
                    "channel_name": channel.name,
                    "frequency_khz": channel.frequency_khz,
                    "frequency_mhz": channel.frequency_mhz,
                }
                dev_types = self.channel_dev_types.get(channel_id)
                if dev_types:
                    payload["workbench_dev_types"] = list(dev_types)
                equipos.append(enrich_equipo_metadata(payload))
        return equipos


def _workbench_channel_id(device_id: str, channel_index: int, total_channels: int) -> str:
    if not device_id:
        return ""
    if total_channels <= 1:
        return device_id
    return f"{device_id}-{channel_index}"


@dataclass
class WorkbenchCoordinationChannel:
    workbench_id: str
    coordination_include: bool = True
    active_channel: bool = False


@dataclass
class WorkbenchCoordinationAssignment:
    workbench_id: str
    frequency_khz: Optional[int] = None
    frequency_mhz: Optional[float] = None
    series: str = ""
    model: str = ""
    band: str = ""
    zone: str = ""
    channel_name: str = ""
    channel_number: int = -1


@dataclass
class WorkbenchCoordination:
    channels: List[WorkbenchCoordinationChannel] = field(default_factory=list)
    assignments: List[WorkbenchCoordinationAssignment] = field(default_factory=list)
    scan_threshold_db: Optional[float] = None
    scan_higher_threshold_db: Optional[float] = None
    scan_file_name: str = ""
    exclusion_range_count: int = 0
    band_plan_country: str = ""

    @property
    def included_channel_count(self) -> int:
        return sum(1 for ch in self.channels if ch.coordination_include)

    @property
    def active_channel_count(self) -> int:
        return sum(1 for ch in self.channels if ch.active_channel)

    @property
    def assigned_frequency_count(self) -> int:
        return sum(1 for item in self.assignments if item.frequency_khz)
