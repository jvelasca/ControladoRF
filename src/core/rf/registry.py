"""Factory de dispositivos RF."""
from __future__ import annotations

from core.rf.devices.hackrf.device import HackRfDevice
from core.rf.devices.mock.device import MockRfDevice
from core.rf.devices.rf_explorer.device import RfExplorerDevice
from core.rf.devices.tinysa.device import TinySaDevice
from core.rf.protocols import RfDevice
from core.rf.source_ids import parse_source_id


def create_device(source_id: str) -> RfDevice:
    parsed = parse_source_id(source_id or "mock")
    base = parsed.device_id
    if base == "hackrf":
        return HackRfDevice()
    if base == "rf_explorer":
        return RfExplorerDevice(port=parsed.serial_port)
    if base == "tinysa":
        return TinySaDevice(port=parsed.serial_port)
    return MockRfDevice()
