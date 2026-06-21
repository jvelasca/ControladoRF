"""Recuperación de stream IQ — patrón SDR++/SoapySDR (reintentar, no cerrar la app)."""
from __future__ import annotations

import re

# Errores que requieren intervención del usuario (USB desenchufado, driver, etc.).
_FATAL_USB_RE = re.compile(
    r"(no hackrf detectado|hackrf no detectado|hackrf_open.*not found|"
    r"could not open device|failed to open device|device not found)",
    re.IGNORECASE,
)


def is_transient_iq_error(message: str) -> bool:
    """Fallo recuperable: reinicio de hackrf_transfer, underrun, espera de datos."""
    lower = (message or "").strip().lower()
    if not lower:
        return True
    tokens = (
        "sin muestras",
        "iniciando captura",
        "esperando datos",
        "reiniciando",
        "recuperando",
        "stream iq detenido",
        "hackrf_transfer termin",
        "transfer termin",
        "sin cambios",
    )
    return any(t in lower for t in tokens)


def is_fatal_iq_error(message: str) -> bool:
    """Solo detiene la app si el equipo no está disponible (no por un corte de stream)."""
    text = (message or "").strip()
    if not text:
        return False
    if is_transient_iq_error(text):
        return False
    lower = text.lower()
    if "captura interrumpida" in lower:
        return True
    if _FATAL_USB_RE.search(text):
        return True
    return False
