"""Perfil de fuente — restricciones UI/captura para analizadores sweep-only."""
from __future__ import annotations

from core.monitor.monitor_operating_mode import MonitorOperatingMode
from core.monitor.monitor_mode_profile import refresh_capture_and_span_limits
from core.monitor.spectrum_params import SpectrumParams
from core.rf.source_ids import is_analyzer_only_source


def apply_analyzer_source_restrictions(params: SpectrumParams) -> list[str]:
    """Fuerza modo analizador y desactiva IQ/demod/audio en fuentes sweep-only.

    Returns:
        Claves i18n de avisos emitidos al usuario (puede estar vacío).
    """
    if not is_analyzer_only_source(params.source_id):
        return []

    notices: list[str] = []
    if params.operating_mode_enum() is not MonitorOperatingMode.SPECTRUM:
        params.operating_mode = MonitorOperatingMode.SPECTRUM.value
        notices.append("monitor_source_forced_analyzer_mode")

    params.capture_mode = "sweep"
    params.audio_enabled = False
    params.digital_analysis_enabled = False
    params.supervision_dwell_active = False
    return notices


def analyzer_source_status_hint(source_id: str) -> str:
    """Clave i18n para tooltip de fuente analizador-only."""
    if not is_analyzer_only_source(source_id):
        return ""
    family = source_id.split("@")[0].split("_")[0]
    if family == "rf_explorer":
        return "monitor_source_hint_rf_explorer"
    if family == "tinysa":
        return "monitor_source_hint_tinysa"
    return "monitor_source_hint_analyzer_only"
