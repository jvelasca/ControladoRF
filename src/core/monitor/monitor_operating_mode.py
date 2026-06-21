"""Modos de operación del módulo Monitor (analizador, SDR, supervisión)."""
from __future__ import annotations

from enum import Enum


class MonitorOperatingMode(str, Enum):
    """Perfil de operación sobre un único motor IQ + FFT."""

    SPECTRUM = "spectrum"
    SDR = "sdr"
    SUPERVISION = "supervision"

    @classmethod
    def normalize(cls, value: str | "MonitorOperatingMode") -> "MonitorOperatingMode":
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).lower())
        except ValueError:
            return cls.SPECTRUM

    def demod_enabled(self) -> bool:
        return self is MonitorOperatingMode.SDR

    def supervision_enabled(self) -> bool:
        return self is MonitorOperatingMode.SUPERVISION

    def label_key(self) -> str:
        if self is MonitorOperatingMode.SPECTRUM:
            return "monitor_mode_analyzer"
        if self is MonitorOperatingMode.SDR:
            return "monitor_mode_sdr"
        return f"monitor_mode_{self.value}"


MODE_CHOICES: tuple[MonitorOperatingMode, ...] = (
    MonitorOperatingMode.SPECTRUM,
    MonitorOperatingMode.SDR,
)


def normalize_operating_mode(value: str | MonitorOperatingMode) -> MonitorOperatingMode:
    """Normaliza modo; supervisión queda integrada en analizador."""
    mode = MonitorOperatingMode.normalize(value)
    if mode is MonitorOperatingMode.SUPERVISION:
        return MonitorOperatingMode.SPECTRUM
    return mode
