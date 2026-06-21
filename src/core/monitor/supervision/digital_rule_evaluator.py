"""Evaluación de salud digital (MER/sync) para supervisión.

Soporta umbrales absolutos (MER mínimo) y modo ``nominal_delta`` (caída MER vs
referencia fijada en el aire). Ver ``docs/monitor_supervision_premisas.md``.
"""
from __future__ import annotations

from typing import Optional

from core.monitor.supervision.alarm_severity import ChannelHealthLevel
from core.monitor.supervision.rule_evaluator import (
    ChannelHealth,
    _health_from_drop_db,
    _health_from_thresholds_lower_worse,
)
from core.monitor.supervision.supervision_models import ChannelReferenceCapture, SupervisionRules
from core.monitor.supervision.threshold_checks import CHECK_DIG_SYNC, CHECK_MER, ThresholdCheckConfig

DigitalHealth = ChannelHealthLevel


def evaluate_digital_mer_health(
    *,
    mer_db: Optional[float],
    sync_ok: bool,
    rules: SupervisionRules,
) -> DigitalHealth:
    """Evaluación legacy vía ``SupervisionRules`` (compatibilidad)."""
    if not rules.digital_metrics_enabled:
        return "unknown"
    if not sync_ok or mer_db is None:
        return "critica" if rules.digital_metrics_enabled else "unknown"
    cfg = ThresholdCheckConfig(
        enabled=True,
        warning_raise=float(rules.mer_warning_db),
        critical_raise=float(rules.mer_critical_db),
    )
    return _health_from_thresholds_lower_worse(mer_db, cfg)


def evaluate_digital_health_from_checks(
    *,
    mer_db: Optional[float],
    sync_ok: bool,
    checks: dict[str, ThresholdCheckConfig],
    rules: SupervisionRules,
    threshold_mode: str = "noise_relative",
    reference: ChannelReferenceCapture | None = None,
    committed: ChannelHealth = "ok",
) -> DigitalHealth:
    """Evalúa MER/sync según checks del preset y modo de umbral."""
    mer_cfg = checks.get(CHECK_MER, ThresholdCheckConfig(enabled=False))
    sync_cfg = checks.get(CHECK_DIG_SYNC, ThresholdCheckConfig(enabled=False))
    if not mer_cfg.enabled and not sync_cfg.enabled:
        return evaluate_digital_mer_health(mer_db=mer_db, sync_ok=sync_ok, rules=rules)

    if sync_cfg.enabled and not sync_ok:
        return "critica"

    if not mer_cfg.enabled:
        return "ok"

    if mer_db is None:
        return "critica"

    if (
        threshold_mode == "nominal_delta"
        and reference is not None
        and reference.mer_db is not None
    ):
        drop_db = float(reference.mer_db) - float(mer_db)
        return _health_from_drop_db(drop_db, mer_cfg, committed=committed)

    return _health_from_thresholds_lower_worse(mer_db, mer_cfg, committed=committed)


def digital_debounce_ms_from_checks(
    checks: dict[str, ThresholdCheckConfig],
    rules: SupervisionRules,
) -> int:
    mer_cfg = checks.get(CHECK_MER, ThresholdCheckConfig())
    sync_cfg = checks.get(CHECK_DIG_SYNC, ThresholdCheckConfig())
    for cfg in (mer_cfg, sync_cfg):
        if cfg.enabled and cfg.debounce_ms is not None:
            return int(cfg.debounce_ms)
    return int(rules.digital_debounce_ms)


def digital_health_to_channel_health(health: DigitalHealth) -> ChannelHealth:
    return health
