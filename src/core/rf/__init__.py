"""Motor RF greenfield — equipos, captura y análisis (sin PyQt).

Schema: RF_ENGINE_SCHEMA_VERSION
"""
from __future__ import annotations

RF_ENGINE_SCHEMA_VERSION = "1.0"

from core.rf.session import RfSession
from core.rf.types import OperatorIntent, SpectrumDisplayFrame, SpectrumFrame

__all__ = [
    "RF_ENGINE_SCHEMA_VERSION",
    "RfSession",
    "OperatorIntent",
    "SpectrumFrame",
    "SpectrumDisplayFrame",
]
