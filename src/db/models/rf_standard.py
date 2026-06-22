"""Modelos del catálogo global de canalizaciones RF."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RfStandard:
    id: str
    name: str
    region_code: str
    service_type: str
    freq_min_hz: Optional[float]
    freq_max_hz: Optional[float]
    channel_spacing_hz: Optional[float]
    metadata_json: str
    enabled: bool = True


@dataclass(frozen=True)
class RfStandardChannel:
    id: int
    standard_id: str
    channel_number: Optional[int]
    channel_label: str
    center_freq_hz: float
    bandwidth_hz: float
    sort_order: int
    metadata_json: str


@dataclass(frozen=True)
class RfChannelRestriction:
    id: int
    standard_id: str
    label: str
    freq_min_hz: float
    freq_max_hz: float
    severity: str
    color_hex: str
    message_key: str
    metadata_json: str
