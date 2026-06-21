"""Catálogo genérico de tipos de alarma de supervisión RF."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Literal, Optional

AlarmPhase = Literal["raised", "latched", "cleared", "acked"]
AlarmSeverity = Literal["warning", "critical", "info", ""]

# Identificadores estables (persistencia / exportación)
RF_SNR_WARNING = "RF_SNR_WARNING"
RF_SNR_CRITICAL = "RF_SNR_CRITICAL"
RF_SNR_WARNING_LATCH = "RF_SNR_WARNING_LATCH"
RF_SNR_CRITICAL_LATCH = "RF_SNR_CRITICAL_LATCH"
RF_SNR_WARNING_CLEAR = "RF_SNR_WARNING_CLEAR"
RF_SNR_CRITICAL_CLEAR = "RF_SNR_CRITICAL_CLEAR"
RF_ACK_MANUAL = "RF_ACK_MANUAL"
RF_ACK_AUTO = "RF_ACK_AUTO"
RF_ACK_MANUAL_ACTIVE = "RF_ACK_MANUAL_ACTIVE"
RF_MER_WARNING = "RF_MER_WARNING"
RF_MER_CRITICAL = "RF_MER_CRITICAL"
RF_MER_WARNING_LATCH = "RF_MER_WARNING_LATCH"
RF_MER_CRITICAL_LATCH = "RF_MER_CRITICAL_LATCH"
RF_DIG_SYNC_LOST = "RF_DIG_SYNC_LOST"
RF_DIG_SYNC_LOST_LATCH = "RF_DIG_SYNC_LOST_LATCH"

ALL_ALARM_TYPE_IDS = (
    RF_SNR_WARNING,
    RF_SNR_CRITICAL,
    RF_SNR_WARNING_LATCH,
    RF_SNR_CRITICAL_LATCH,
    RF_SNR_WARNING_CLEAR,
    RF_SNR_CRITICAL_CLEAR,
    RF_ACK_MANUAL,
    RF_ACK_AUTO,
    RF_ACK_MANUAL_ACTIVE,
    RF_MER_WARNING,
    RF_MER_CRITICAL,
    RF_MER_WARNING_LATCH,
    RF_MER_CRITICAL_LATCH,
    RF_DIG_SYNC_LOST,
    RF_DIG_SYNC_LOST_LATCH,
)


@dataclass(frozen=True)
class AlarmTypeDefinition:
    type_id: str
    severity: AlarmSeverity
    phase: AlarmPhase | Literal[""]
    i18n_name_key: str
    i18n_cause_key: str
    i18n_resolution_key: str = ""


ALARM_TYPE_CATALOG: Dict[str, AlarmTypeDefinition] = {
    RF_SNR_WARNING: AlarmTypeDefinition(
        type_id=RF_SNR_WARNING,
        severity="warning",
        phase="raised",
        i18n_name_key="monitor_alarm_type_snr_warning",
        i18n_cause_key="monitor_alarm_cause_snr_warning",
    ),
    RF_SNR_CRITICAL: AlarmTypeDefinition(
        type_id=RF_SNR_CRITICAL,
        severity="critical",
        phase="raised",
        i18n_name_key="monitor_alarm_type_snr_critical",
        i18n_cause_key="monitor_alarm_cause_snr_critical",
    ),
    RF_SNR_WARNING_LATCH: AlarmTypeDefinition(
        type_id=RF_SNR_WARNING_LATCH,
        severity="warning",
        phase="latched",
        i18n_name_key="monitor_alarm_type_snr_warning_latch",
        i18n_cause_key="monitor_alarm_cause_snr_recovered",
        i18n_resolution_key="monitor_alarm_resolution_latched",
    ),
    RF_SNR_CRITICAL_LATCH: AlarmTypeDefinition(
        type_id=RF_SNR_CRITICAL_LATCH,
        severity="critical",
        phase="latched",
        i18n_name_key="monitor_alarm_type_snr_critical_latch",
        i18n_cause_key="monitor_alarm_cause_snr_recovered",
        i18n_resolution_key="monitor_alarm_resolution_latched",
    ),
    RF_SNR_WARNING_CLEAR: AlarmTypeDefinition(
        type_id=RF_SNR_WARNING_CLEAR,
        severity="warning",
        phase="cleared",
        i18n_name_key="monitor_alarm_type_snr_warning_clear",
        i18n_cause_key="monitor_alarm_cause_auto_clear",
        i18n_resolution_key="monitor_alarm_resolution_auto",
    ),
    RF_SNR_CRITICAL_CLEAR: AlarmTypeDefinition(
        type_id=RF_SNR_CRITICAL_CLEAR,
        severity="critical",
        phase="cleared",
        i18n_name_key="monitor_alarm_type_snr_critical_clear",
        i18n_cause_key="monitor_alarm_cause_auto_clear",
        i18n_resolution_key="monitor_alarm_resolution_auto",
    ),
    RF_ACK_MANUAL: AlarmTypeDefinition(
        type_id=RF_ACK_MANUAL,
        severity="info",
        phase="acked",
        i18n_name_key="monitor_alarm_type_ack_manual",
        i18n_cause_key="monitor_alarm_cause_ack_manual",
        i18n_resolution_key="monitor_alarm_resolution_manual",
    ),
    RF_ACK_MANUAL_ACTIVE: AlarmTypeDefinition(
        type_id=RF_ACK_MANUAL_ACTIVE,
        severity="info",
        phase="acked",
        i18n_name_key="monitor_alarm_type_ack_manual_active",
        i18n_cause_key="monitor_alarm_cause_ack_manual_active",
        i18n_resolution_key="monitor_alarm_resolution_manual",
    ),
    RF_ACK_AUTO: AlarmTypeDefinition(
        type_id=RF_ACK_AUTO,
        severity="info",
        phase="cleared",
        i18n_name_key="monitor_alarm_type_ack_auto",
        i18n_cause_key="monitor_alarm_cause_ack_auto",
        i18n_resolution_key="monitor_alarm_resolution_auto",
    ),
    RF_MER_WARNING: AlarmTypeDefinition(
        type_id=RF_MER_WARNING,
        severity="warning",
        phase="raised",
        i18n_name_key="monitor_alarm_type_mer_warning",
        i18n_cause_key="monitor_alarm_cause_mer_warning",
    ),
    RF_MER_CRITICAL: AlarmTypeDefinition(
        type_id=RF_MER_CRITICAL,
        severity="critical",
        phase="raised",
        i18n_name_key="monitor_alarm_type_mer_critical",
        i18n_cause_key="monitor_alarm_cause_mer_critical",
    ),
    RF_MER_WARNING_LATCH: AlarmTypeDefinition(
        type_id=RF_MER_WARNING_LATCH,
        severity="warning",
        phase="latched",
        i18n_name_key="monitor_alarm_type_mer_warning_latch",
        i18n_cause_key="monitor_alarm_cause_mer_recovered",
        i18n_resolution_key="monitor_alarm_resolution_latched",
    ),
    RF_MER_CRITICAL_LATCH: AlarmTypeDefinition(
        type_id=RF_MER_CRITICAL_LATCH,
        severity="critical",
        phase="latched",
        i18n_name_key="monitor_alarm_type_mer_critical_latch",
        i18n_cause_key="monitor_alarm_cause_mer_recovered",
        i18n_resolution_key="monitor_alarm_resolution_latched",
    ),
    RF_DIG_SYNC_LOST: AlarmTypeDefinition(
        type_id=RF_DIG_SYNC_LOST,
        severity="critical",
        phase="raised",
        i18n_name_key="monitor_alarm_type_dig_sync_lost",
        i18n_cause_key="monitor_alarm_cause_dig_sync_lost",
    ),
    RF_DIG_SYNC_LOST_LATCH: AlarmTypeDefinition(
        type_id=RF_DIG_SYNC_LOST_LATCH,
        severity="critical",
        phase="latched",
        i18n_name_key="monitor_alarm_type_dig_sync_lost_latch",
        i18n_cause_key="monitor_alarm_cause_dig_sync_recovered",
        i18n_resolution_key="monitor_alarm_resolution_latched",
    ),
}


def resolve_alarm_type(
    *,
    rule: str,
    phase: str,
    severity: str = "",
) -> str:
    """Resuelve el tipo canónico a partir de regla/fase/severidad."""
    rule = str(rule or "")
    phase = str(phase or "")
    severity = str(severity or "")

    if rule == "manual_ack_active":
        return RF_ACK_MANUAL_ACTIVE
    if rule == "manual_ack":
        return RF_ACK_MANUAL
    if rule == "auto_reset":
        if phase == "cleared":
            return RF_SNR_CRITICAL_CLEAR if severity == "critical" else RF_SNR_WARNING_CLEAR
        return RF_ACK_AUTO

    if phase == "raised":
        return RF_SNR_CRITICAL if severity == "critical" else RF_SNR_WARNING
    if phase == "latched":
        return RF_SNR_CRITICAL_LATCH if severity == "critical" else RF_SNR_WARNING_LATCH
    if phase == "cleared":
        return RF_SNR_CRITICAL_CLEAR if severity == "critical" else RF_SNR_WARNING_CLEAR
    if phase == "acked":
        return RF_ACK_MANUAL

    if rule.startswith("snr_below_critical"):
        return RF_SNR_CRITICAL
    if rule.startswith("snr_below_warning"):
        return RF_SNR_WARNING
    if rule.startswith("snr_recovered_critical"):
        return RF_SNR_CRITICAL_LATCH
    if rule.startswith("snr_recovered_warning"):
        return RF_SNR_WARNING_LATCH

    if rule == "dig_sync_lost":
        return RF_DIG_SYNC_LOST if phase == "raised" else RF_DIG_SYNC_LOST_LATCH
    if rule.startswith("mer_below_critical"):
        return RF_MER_CRITICAL if phase == "raised" else RF_MER_CRITICAL_LATCH
    if rule.startswith("mer_below_warning"):
        return RF_MER_WARNING if phase == "raised" else RF_MER_WARNING_LATCH
    if rule.startswith("mer_drop_critical"):
        return RF_MER_CRITICAL if phase == "raised" else RF_MER_CRITICAL_LATCH
    if rule.startswith("mer_drop_warning"):
        return RF_MER_WARNING if phase == "raised" else RF_MER_WARNING_LATCH
    if rule.startswith("mer_drop_recovered_critical"):
        return RF_MER_CRITICAL_LATCH
    if rule.startswith("mer_drop_recovered_warning"):
        return RF_MER_WARNING_LATCH
    if rule.startswith("mer_recovered_critical"):
        return RF_MER_CRITICAL_LATCH
    if rule.startswith("mer_recovered_warning"):
        return RF_MER_WARNING_LATCH
    if rule.startswith("dig_sync_recovered"):
        return RF_DIG_SYNC_LOST_LATCH

    return RF_ACK_MANUAL if phase == "acked" else RF_SNR_WARNING


def get_alarm_type(type_id: str) -> Optional[AlarmTypeDefinition]:
    return ALARM_TYPE_CATALOG.get(str(type_id or ""))


def iter_alarm_types() -> Iterable[AlarmTypeDefinition]:
    for type_id in ALL_ALARM_TYPE_IDS:
        definition = ALARM_TYPE_CATALOG.get(type_id)
        if definition is not None:
            yield definition


def alarm_type_label(type_id: str, tr: Callable[[str], str]) -> str:
    definition = get_alarm_type(type_id)
    if definition is None:
        return str(type_id or "—")
    return tr(definition.i18n_name_key)


def format_alarm_cause(
    type_id: str,
    tr: Callable[[str], str],
    *,
    snr_db: Optional[float] = None,
    threshold_db: Optional[float] = None,
    label: str = "",
    frequency_mhz: Optional[float] = None,
) -> str:
    definition = get_alarm_type(type_id)
    if definition is None:
        return label or str(type_id)
    snr_text = f"{snr_db:.1f}" if snr_db is not None else "—"
    threshold_text = f"{threshold_db:.1f}" if threshold_db is not None else "—"
    freq_text = f"{frequency_mhz:.3f}" if frequency_mhz is not None else "—"
    return tr(definition.i18n_cause_key).format(
        label=label,
        freq=freq_text,
        snr=snr_text,
        threshold=threshold_text,
    )
