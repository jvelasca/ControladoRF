"""Evaluación de umbrales relativos al ruido o caída vs referencia nominal.

En modo ``nominal_delta`` compara la medición actual con ``ChannelReferenceCapture``
fijada en el aire; en ``noise_relative`` evalúa SNR/portadora vs piso local.
"""
from __future__ import annotations

from typing import Literal, Optional

from core.monitor.supervision.alarm_severity import ChannelHealthLevel, SEVERITY_RANK, health_from_severities
from core.monitor.supervision.measurement_engine import ChannelMeasurement
from core.monitor.supervision.supervision_models import ChannelReferenceCapture, SupervisionRules
from core.monitor.supervision.threshold_checks import (
    CHECK_CARRIER,
    CHECK_SNR,
    ThresholdCheckConfig,
)

ChannelHealth = ChannelHealthLevel


def _worst_health(*values: ChannelHealth) -> ChannelHealth:
    return health_from_severities(*values)


def _health_from_thresholds_lower_worse(
    value: Optional[float],
    config: ThresholdCheckConfig,
    *,
    committed: ChannelHealth = "ok",
) -> ChannelHealth:
    """SNR/MER absoluto: menor valor = peor."""
    if not config.enabled:
        return "ok"
    if value is None:
        return "unknown"

    levels: list[tuple[str, Optional[float], Optional[float]]] = [
        ("critica", config.critical_raise, config.critical_clear),
        ("menor", config.menor_raise, config.menor_clear),
        ("aviso", config.warning_raise, config.warning_clear),
        ("comentario", config.comentario_raise, config.comentario_clear),
    ]
    triggered: list[ChannelHealth] = []
    for severity, raise_at, clear_at in levels:
        if raise_at is None:
            continue
        if value <= float(raise_at):
            triggered.append(severity)  # type: ignore[arg-type]
        elif committed == severity and clear_at is not None and value < float(clear_at):
            triggered.append(severity)  # type: ignore[arg-type]
    if not triggered:
        return "ok"
    return health_from_severities(*triggered)


def _health_from_lower_worse(
    value: Optional[float],
    config: ThresholdCheckConfig,
    *,
    committed: ChannelHealth = "ok",
) -> ChannelHealth:
    return _health_from_thresholds_lower_worse(value, config, committed=committed)


def evaluate_snr_health(
    measurement: ChannelMeasurement,
    config: ThresholdCheckConfig,
    *,
    committed: ChannelHealth = "ok",
) -> ChannelHealth:
    return _health_from_lower_worse(
        measurement.snr_above_noise_db,
        config,
        committed=committed,
    )


def evaluate_carrier_health(
    measurement: ChannelMeasurement,
    config: ThresholdCheckConfig,
    *,
    committed: ChannelHealth = "ok",
) -> ChannelHealth:
    return _health_from_lower_worse(
        measurement.snr_above_noise_db,
        config,
        committed=committed,
    )


def evaluate_channel_health(
    measurement: ChannelMeasurement,
    rules: SupervisionRules,
    *,
    snr_config: ThresholdCheckConfig | None = None,
    carrier_config: ThresholdCheckConfig | None = None,
    committed: ChannelHealth = "ok",
) -> ChannelHealth:
    snr = measurement.snr_above_noise_db
    if snr is None:
        return "unknown"

    if snr_config is not None or carrier_config is not None:
        snr_cfg = snr_config or ThresholdCheckConfig(enabled=False)
        carrier_cfg = carrier_config or ThresholdCheckConfig(
            enabled=True,
            warning_raise=rules.warning_above_noise_db + 1.0,
            critical_raise=rules.carrier_loss_margin_db,
        )
        return _worst_health(
            evaluate_snr_health(measurement, snr_cfg, committed=committed),
            evaluate_carrier_health(measurement, carrier_cfg, committed=committed),
        )

    warning = float(rules.warning_above_noise_db)
    critical = float(rules.critical_above_noise_db)
    carrier_margin = float(rules.carrier_loss_margin_db)
    legacy_snr = ThresholdCheckConfig(
        enabled=True,
        warning_raise=warning,
        critical_raise=critical,
    )
    legacy_carrier = ThresholdCheckConfig(
        enabled=True,
        warning_raise=carrier_margin + 1.0,
        critical_raise=carrier_margin,
    )
    return _worst_health(
        evaluate_snr_health(measurement, legacy_snr, committed=committed),
        evaluate_carrier_health(measurement, legacy_carrier, committed=committed),
    )


def evaluate_channel_health_from_checks(
    measurement: ChannelMeasurement,
    checks: dict[str, ThresholdCheckConfig],
    *,
    committed: ChannelHealth = "ok",
    threshold_mode: str = "noise_relative",
    reference: ChannelReferenceCapture | None = None,
) -> ChannelHealth:
    if threshold_mode == "nominal_delta" and reference is not None and reference.is_valid():
        return _evaluate_nominal_delta(measurement, checks, reference, committed=committed)

    snr_cfg = checks.get(CHECK_SNR, ThresholdCheckConfig(enabled=True))
    carrier_cfg = checks.get(CHECK_CARRIER, ThresholdCheckConfig(enabled=True))
    if not snr_cfg.enabled and not carrier_cfg.enabled:
        return "ok"
    return _worst_health(
        evaluate_snr_health(measurement, snr_cfg, committed=committed),
        evaluate_carrier_health(measurement, carrier_cfg, committed=committed),
    )


def _evaluate_nominal_delta(
    measurement: ChannelMeasurement,
    checks: dict[str, ThresholdCheckConfig],
    reference: ChannelReferenceCapture,
    *,
    committed: ChannelHealth = "ok",
) -> ChannelHealth:
    healths: list[ChannelHealth] = []
    snr_cfg = checks.get(CHECK_SNR, ThresholdCheckConfig(enabled=False))
    if snr_cfg.enabled and reference.snr_above_noise_db is not None and measurement.snr_above_noise_db is not None:
        drop = float(reference.snr_above_noise_db) - float(measurement.snr_above_noise_db)
        healths.append(_health_from_drop_db(drop, snr_cfg, committed=committed))
    carrier_cfg = checks.get(CHECK_CARRIER, ThresholdCheckConfig(enabled=False))
    if (
        carrier_cfg.enabled
        and reference.carrier_dbm is not None
        and measurement.carrier_dbm is not None
    ):
        drop = float(reference.carrier_dbm) - float(measurement.carrier_dbm)
        healths.append(_health_from_drop_db(drop, carrier_cfg, committed=committed))
    if not healths:
        return "unknown"
    return _worst_health(*healths)


def _health_from_drop_db(
    drop_db: float,
    config: ThresholdCheckConfig,
    *,
    committed: ChannelHealth = "ok",
) -> ChannelHealth:
    """Caída respecto a referencia: mayor drop = peor."""
    if not config.enabled:
        return "ok"

    levels: list[tuple[str, Optional[float], Optional[float]]] = [
        ("critica", config.critical_raise, config.critical_clear),
        ("menor", config.menor_raise, config.menor_clear),
        ("aviso", config.warning_raise, config.warning_clear),
        ("comentario", config.comentario_raise, config.comentario_clear),
    ]
    triggered: list[ChannelHealth] = []
    for severity, raise_at, clear_at in levels:
        if raise_at is None:
            continue
        if drop_db >= float(raise_at):
            triggered.append(severity)  # type: ignore[arg-type]
        elif committed == severity and clear_at is not None and drop_db >= float(clear_at):
            triggered.append(severity)  # type: ignore[arg-type]
    if not triggered:
        return "ok"
    return health_from_severities(*triggered)
