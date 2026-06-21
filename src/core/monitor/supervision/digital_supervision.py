"""Emparejamiento VFO ↔ canal inventario para métricas digitales."""
from __future__ import annotations

from typing import Any, Literal, Optional

from core.monitor.supervision.supervision_models import ResolvedSupervisionTarget

DigitalSupervisionMode = Literal["snr_only", "snr_and_mer"]

MODULATION_ANALOG = "analog_fm"
MODULATION_DIGITAL_QPSK = "digital_qpsk"
MODULATION_DIGITAL_QAM = "digital_qam"
MODULATION_DIGITAL_DAB = "digital_dab"
MODULATION_AUTO = "auto"


def infer_modulation_class(item: dict[str, Any]) -> str:
    """Clasifica modulación esperada del canal (heurística por modelo/serie)."""
    explicit = str(item.get("modulation_class") or "").strip().lower()
    if explicit and explicit != MODULATION_AUTO:
        return explicit
    text = f"{item.get('series', '')} {item.get('model', '')}".upper()
    if any(token in text for token in ("DAB", "BAND III", "ENSEMBLE")):
        return MODULATION_DIGITAL_DAB
    if any(token in text for token in ("QAM", "DM 1000", "DM1000", "LECTROSONICS")):
        return MODULATION_DIGITAL_QAM
    if any(
        token in text
        for token in ("AXIENT", "AD4", "AD2", "AD1", "ULXD", "QLX", "DIGITAL", "SHURE")
    ):
        return MODULATION_DIGITAL_QPSK
    return MODULATION_ANALOG


def is_digital_modulation_class(modulation_class: str) -> bool:
    return str(modulation_class or "").startswith("digital_")


def digital_supervision_mode_from_rules(digital_metrics_enabled: bool) -> DigitalSupervisionMode:
    return "snr_and_mer" if digital_metrics_enabled else "snr_only"


def digital_metrics_enabled_for_mode(mode: DigitalSupervisionMode) -> bool:
    return mode == "snr_and_mer"


def effective_digital_mode_for_equipo(
    *,
    modulation_class: str,
    digital_metrics_enabled: bool,
) -> str:
    """Modo efectivo para UI: none (analógico), snr_only o snr_and_mer."""
    if not is_digital_modulation_class(modulation_class):
        return "none"
    return digital_supervision_mode_from_rules(digital_metrics_enabled)


def match_supervision_target_for_vfo(
    targets: list[ResolvedSupervisionTarget],
    vfo_hz: float,
    *,
    tolerance_hz: float = 35_000.0,
) -> Optional[ResolvedSupervisionTarget]:
    best: ResolvedSupervisionTarget | None = None
    best_delta = float("inf")
    for target in targets:
        if not target.enabled:
            continue
        delta = abs(float(target.frequency_hz) - float(vfo_hz))
        limit = max(tolerance_hz, target.half_bandwidth_hz * 1.5)
        if delta <= limit and delta < best_delta:
            best = target
            best_delta = delta
    return best


def resolve_supervision_target(
    targets: list[ResolvedSupervisionTarget],
    channel_key: str,
) -> Optional[ResolvedSupervisionTarget]:
    key = str(channel_key or "")
    if not key:
        return None
    for target in targets:
        if target.channel_key == key and target.enabled:
            return target
    return None


def digital_profile_for_modulation_class(modulation_class: str) -> str:
    mod = str(modulation_class or "").lower()
    if mod == MODULATION_DIGITAL_DAB:
        return "dab_iii"
    if mod == MODULATION_DIGITAL_QAM:
        return "iem_qam16"
    return "shure_digital"


def build_dwell_spectrum_params(
    base: "SpectrumParams",
    target: ResolvedSupervisionTarget,
    equipo: dict[str, Any],
) -> "SpectrumParams":
    from core.monitor.digital_signal_profiles import apply_digital_profile_defaults

    params = base.copy()
    freq = float(target.frequency_hz)
    profile_id = digital_profile_for_modulation_class(str(equipo.get("modulation_class") or ""))
    params.supervision_dwell_active = True
    params.center_freq_hz = freq
    params.vfo_freq_hz = freq
    params.selected_freq_hz = freq
    params.capture_mode = "iq"
    params.digital_analysis_enabled = True
    params.span_mode = "manual"
    params.manual_span_hz = 2_000_000.0
    params = apply_digital_profile_defaults(params, profile_id)
    params.apply_span_as_sample_rate()
    params.marker_auto_pan = False
    params.clear_freq_window()
    return params
