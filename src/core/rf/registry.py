"""Factory de dispositivos RF."""
from __future__ import annotations

from core.rf.devices.hackrf.device import HackRfDevice
from core.rf.devices.mock.device import MockRfDevice
from core.rf.protocols import RfDevice


def create_device(source_id: str) -> RfDevice:
    base = (source_id or "mock").split("_")[0]
    if base == "hackrf":
        return HackRfDevice()
    return MockRfDevice()
