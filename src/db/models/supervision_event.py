"""Modelo de evento de supervisión persistido en SQLite."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SupervisionEvent:
    id: int
    project_key: str
    timestamp_utc: str
    channel_key: str
    label: str
    frequency_mhz: Optional[float]
    severity: str
    phase: str
    snr_db: Optional[float]
    carrier_dbm: Optional[float]
    noise_dbm: Optional[float]
    threshold_db: Optional[float]
    rule: str
    message: str
    alarm_type: str
    ack_at: str
