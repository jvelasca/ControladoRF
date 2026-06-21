"""Formateo de reglas de alarma para la matriz de presets.

Traduce ``ThresholdCheckConfig`` a texto operativo («Caída SNR ≥ 3 dB → Aviso»)
según el modo de umbral activo.
"""
from __future__ import annotations

from typing import Callable, Optional

from core.monitor.supervision.threshold_checks import (
    CHECK_CARRIER,
    CHECK_DIG_SYNC,
    CHECK_MER,
    CHECK_SNR,
    ThresholdCheckConfig,
)


def format_check_alarm_rule(
    check_id: str,
    cfg: ThresholdCheckConfig,
    *,
    threshold_mode: str,
    tr: Callable[[str], str],
) -> str:
    if not cfg.enabled:
        return "—"
    if check_id == CHECK_DIG_SYNC:
        return tr("monitor_alarm_rule_sync_lost_critical")
    w = cfg.warning_raise
    c = cfg.critical_raise
    if w is None and c is None:
        return "—"
    if threshold_mode == "nominal_delta":
        return _format_delta_rule(check_id, w, c, tr)
    return _format_noise_relative_rule(check_id, w, c, tr)


def format_preset_alarm_summary(
    checks: dict[str, ThresholdCheckConfig],
    *,
    threshold_mode: str,
    tr: Callable[[str], str],
) -> str:
    parts: list[str] = []
    for check_id in (CHECK_SNR, CHECK_CARRIER, CHECK_MER, CHECK_DIG_SYNC):
        cfg = checks.get(check_id, ThresholdCheckConfig(enabled=False))
        rule = format_check_alarm_rule(check_id, cfg, threshold_mode=threshold_mode, tr=tr)
        if rule and rule != "—":
            parts.append(rule)
    return tr("monitor_alarm_rule_sep").join(parts) if parts else "—"


def _format_noise_relative_rule(
    check_id: str,
    warning: Optional[float],
    critical: Optional[float],
    tr: Callable[[str], str],
) -> str:
    prefix = _check_label(check_id, tr)
    chunks: list[str] = []
    if warning is not None:
        chunks.append(tr("monitor_alarm_rule_warn_below").format(prefix=prefix, value=f"{warning:.1f}"))
    if critical is not None:
        chunks.append(tr("monitor_alarm_rule_crit_below").format(prefix=prefix, value=f"{critical:.1f}"))
    return tr("monitor_alarm_rule_sep").join(chunks) if chunks else "—"


def _format_delta_rule(
    check_id: str,
    warning: Optional[float],
    critical: Optional[float],
    tr: Callable[[str], str],
) -> str:
    prefix = _check_label(check_id, tr)
    chunks: list[str] = []
    if warning is not None:
        chunks.append(tr("monitor_alarm_rule_warn_drop").format(prefix=prefix, value=f"{warning:.1f}"))
    if critical is not None:
        chunks.append(tr("monitor_alarm_rule_crit_drop").format(prefix=prefix, value=f"{critical:.1f}"))
    return tr("monitor_alarm_rule_sep").join(chunks) if chunks else "—"


def _check_label(check_id: str, tr: Callable[[str], str]) -> str:
    keys = {
        CHECK_SNR: "monitor_check_snr_short",
        CHECK_CARRIER: "monitor_check_carrier_short",
        CHECK_MER: "monitor_check_mer_short",
        CHECK_DIG_SYNC: "monitor_check_dig_sync_short",
    }
    return tr(keys.get(check_id, check_id))
