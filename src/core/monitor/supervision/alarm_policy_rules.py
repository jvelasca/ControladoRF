"""Reglas de política de alarmas por preset (filas × severidad).

Cada ``AlarmPolicyRule`` define una condición medible y la severidad que dispara
(``critica``, ``menor``, ``aviso``, ``comentario``). Se compilan a
``ThresholdCheckConfig`` para el motor existente y se editan en el modal de presets.

Ver ``docs/monitor_supervision_premisas.md``.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional

from core.monitor.supervision.alarm_severity import (
    ALL_ALARM_SEVERITIES,
    AlarmSeverityLevel,
    SEVERITY_RANK,
    normalize_severity,
)
from core.monitor.supervision.supervision_models import ChannelReferenceCapture
from core.monitor.supervision.threshold_checks import (
    CHECK_CARRIER,
    CHECK_DIG_SYNC,
    CHECK_MER,
    CHECK_SNR,
    ThresholdCheckConfig,
    default_clear_value,
)

ConditionType = str

COND_DROP_SNR = "drop_snr"
COND_DROP_CARRIER = "drop_carrier"
COND_DROP_MER = "drop_mer"
COND_SNR_BELOW = "snr_below"
COND_CARRIER_BELOW = "carrier_below"
COND_MER_BELOW = "mer_below"
COND_RX_LEVEL_BELOW = "rx_level_below"
COND_TX_LEVEL_ABOVE = "tx_level_above"
COND_SYNC_LOST = "sync_lost"

DROP_CONDITIONS: tuple[str, ...] = (COND_DROP_SNR, COND_DROP_CARRIER, COND_DROP_MER)
BELOW_CONDITIONS: tuple[str, ...] = (
    COND_SNR_BELOW,
    COND_CARRIER_BELOW,
    COND_MER_BELOW,
    COND_RX_LEVEL_BELOW,
    COND_TX_LEVEL_ABOVE,
)

CONDITION_I18N: dict[str, str] = {
    COND_DROP_SNR: "monitor_alarm_cond_drop_snr",
    COND_DROP_CARRIER: "monitor_alarm_cond_drop_carrier",
    COND_DROP_MER: "monitor_alarm_cond_drop_mer",
    COND_SNR_BELOW: "monitor_alarm_cond_snr_below",
    COND_CARRIER_BELOW: "monitor_alarm_cond_carrier_below",
    COND_MER_BELOW: "monitor_alarm_cond_mer_below",
    COND_RX_LEVEL_BELOW: "monitor_alarm_cond_rx_below",
    COND_TX_LEVEL_ABOVE: "monitor_alarm_cond_tx_above",
    COND_SYNC_LOST: "monitor_alarm_cond_sync_lost",
}

CONDITION_TO_CHECK: dict[str, str] = {
    COND_DROP_SNR: CHECK_SNR,
    COND_DROP_CARRIER: CHECK_CARRIER,
    COND_DROP_MER: CHECK_MER,
    COND_SNR_BELOW: CHECK_SNR,
    COND_CARRIER_BELOW: CHECK_CARRIER,
    COND_MER_BELOW: CHECK_MER,
    COND_RX_LEVEL_BELOW: CHECK_CARRIER,
    COND_SYNC_LOST: CHECK_DIG_SYNC,
}


@dataclass
class AlarmPolicyRule:
    rule_id: str
    condition_type: str
    threshold: Optional[float] = None
    severity: AlarmSeverityLevel = "aviso"
    comment: str = ""
    enabled: bool = True
    debounce_ms: Optional[int] = None
    auto_clear_s: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "rule_id": self.rule_id,
            "condition_type": self.condition_type,
            "severity": self.severity,
            "enabled": bool(self.enabled),
        }
        if self.threshold is not None:
            payload["threshold"] = float(self.threshold)
        if self.comment:
            payload["comment"] = self.comment
        if self.debounce_ms is not None:
            payload["debounce_ms"] = int(self.debounce_ms)
        if self.auto_clear_s is not None:
            payload["auto_clear_s"] = float(self.auto_clear_s)
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AlarmPolicyRule:
        raw = data or {}
        severity = normalize_severity(str(raw.get("severity") or "aviso")) or "aviso"
        threshold = raw.get("threshold")
        debounce = raw.get("debounce_ms")
        auto_clear = raw.get("auto_clear_s")
        return cls(
            rule_id=str(raw.get("rule_id") or uuid.uuid4().hex[:12]),
            condition_type=str(raw.get("condition_type") or COND_SNR_BELOW),
            threshold=float(threshold) if threshold is not None else None,
            severity=severity,
            comment=str(raw.get("comment") or ""),
            enabled=bool(raw.get("enabled", True)),
            debounce_ms=int(debounce) if debounce is not None else None,
            auto_clear_s=float(auto_clear) if auto_clear is not None else None,
        )


def new_rule_id() -> str:
    return uuid.uuid4().hex[:12]


def default_conditions_for_mode(threshold_mode: str, technology: str) -> List[str]:
    """Condiciones sugeridas al crear un preset vacío."""
    if threshold_mode == "nominal_delta":
        base = [COND_DROP_SNR, COND_DROP_CARRIER]
        if technology in ("digital", "nominal"):
            base.extend([COND_DROP_MER, COND_SYNC_LOST])
        return base
    base = [COND_SNR_BELOW, COND_CARRIER_BELOW]
    if technology in ("digital", "nominal"):
        base.extend([COND_MER_BELOW, COND_SYNC_LOST])
    return base


def rules_from_checks(
    checks: Dict[str, ThresholdCheckConfig],
    *,
    threshold_mode: str,
) -> List[AlarmPolicyRule]:
    """Genera filas de política a partir de checks legacy (migración / builtins)."""
    rules: List[AlarmPolicyRule] = []
    is_nominal = threshold_mode == "nominal_delta"

    def _add_pair(
        check_id: str,
        drop_cond: str,
        below_cond: str,
        cfg: ThresholdCheckConfig,
    ) -> None:
        if not cfg.enabled:
            return
        cond = drop_cond if is_nominal else below_cond
        if cfg.warning_raise is not None:
            rules.append(
                AlarmPolicyRule(
                    rule_id=new_rule_id(),
                    condition_type=cond,
                    threshold=float(cfg.warning_raise),
                    severity="aviso",
                    enabled=True,
                )
            )
        if cfg.critical_raise is not None:
            rules.append(
                AlarmPolicyRule(
                    rule_id=new_rule_id(),
                    condition_type=cond,
                    threshold=float(cfg.critical_raise),
                    severity="critica",
                    enabled=True,
                )
            )
        if cfg.menor_raise is not None:
            rules.append(
                AlarmPolicyRule(
                    rule_id=new_rule_id(),
                    condition_type=cond,
                    threshold=float(cfg.menor_raise),
                    severity="menor",
                    enabled=True,
                )
            )
        if cfg.comentario_raise is not None:
            rules.append(
                AlarmPolicyRule(
                    rule_id=new_rule_id(),
                    condition_type=cond,
                    threshold=float(cfg.comentario_raise),
                    severity="comentario",
                    enabled=True,
                )
            )

    _add_pair(CHECK_SNR, COND_DROP_SNR, COND_SNR_BELOW, checks.get(CHECK_SNR, ThresholdCheckConfig(enabled=False)))
    _add_pair(
        CHECK_CARRIER,
        COND_DROP_CARRIER,
        COND_CARRIER_BELOW,
        checks.get(CHECK_CARRIER, ThresholdCheckConfig(enabled=False)),
    )
    _add_pair(CHECK_MER, COND_DROP_MER, COND_MER_BELOW, checks.get(CHECK_MER, ThresholdCheckConfig(enabled=False)))

    sync_cfg = checks.get(CHECK_DIG_SYNC, ThresholdCheckConfig(enabled=False))
    if sync_cfg.enabled:
        rules.append(
            AlarmPolicyRule(
                rule_id=new_rule_id(),
                condition_type=COND_SYNC_LOST,
                threshold=None,
                severity="critica",
                enabled=True,
            )
        )
    return rules


def _severity_field(severity: AlarmSeverityLevel, *, prefix: str) -> str:
    return f"{prefix}_{severity}"


def checks_from_rules(
    rules: Iterable[AlarmPolicyRule],
    *,
    threshold_mode: str,
    debounce_ms: int = 500,
    digital_debounce_ms: int = 1500,
) -> Dict[str, ThresholdCheckConfig]:
    """Compila reglas de política a checks del motor (peor umbral por severidad)."""
    enabled_checks: Dict[str, bool] = {}
    raises: Dict[str, Dict[str, float]] = {}
    debounces: Dict[str, int] = {}

    for rule in rules:
        if not rule.enabled:
            continue
        if rule.condition_type == COND_SYNC_LOST:
            enabled_checks[CHECK_DIG_SYNC] = True
            if rule.debounce_ms is not None:
                debounces[CHECK_DIG_SYNC] = max(debounces.get(CHECK_DIG_SYNC, 0), int(rule.debounce_ms))
            continue
        if rule.condition_type in (COND_TX_LEVEL_ABOVE,):
            continue  # reservado — sin motor aún
        check_id = CONDITION_TO_CHECK.get(rule.condition_type)
        if not check_id:
            continue
        enabled_checks[check_id] = True
        if rule.debounce_ms is not None:
            debounces[check_id] = max(debounces.get(check_id, 0), int(rule.debounce_ms))
        if rule.threshold is None:
            continue
        bucket = raises.setdefault(check_id, {})
        current = bucket.get(rule.severity)
        value = float(rule.threshold)
        if current is None:
            bucket[rule.severity] = value
        elif rule.severity in ("critica", "menor"):
            bucket[rule.severity] = max(current, value) if threshold_mode == "nominal_delta" else min(current, value)
        else:
            bucket[rule.severity] = max(current, value) if threshold_mode == "nominal_delta" else min(current, value)

    def _build(check_id: str, default_debounce: int) -> ThresholdCheckConfig:
        if not enabled_checks.get(check_id):
            return ThresholdCheckConfig(enabled=False)
        sev = raises.get(check_id, {})
        effective_debounce = debounces.get(check_id, default_debounce)

        def _pick(*keys: str) -> Optional[float]:
            for key in keys:
                if key in sev:
                    return float(sev[key])
            return None

        cfg = ThresholdCheckConfig(
            enabled=True,
            critical_raise=_pick("critica"),
            menor_raise=_pick("menor"),
            warning_raise=_pick("aviso"),
            comentario_raise=_pick("comentario"),
            debounce_ms=effective_debounce,
        )
        for field_name in ("critical_raise", "menor_raise", "warning_raise", "comentario_raise"):
            value = getattr(cfg, field_name)
            if value is not None:
                clear_name = field_name.replace("_raise", "_clear")
                setattr(cfg, clear_name, default_clear_value(float(value)))
        return cfg

    return {
        CHECK_SNR: _build(CHECK_SNR, debounce_ms),
        CHECK_CARRIER: _build(CHECK_CARRIER, debounce_ms),
        CHECK_MER: _build(CHECK_MER, digital_debounce_ms),
        CHECK_DIG_SYNC: ThresholdCheckConfig(
            enabled=bool(enabled_checks.get(CHECK_DIG_SYNC)),
            debounce_ms=debounces.get(CHECK_DIG_SYNC, digital_debounce_ms),
        )
        if enabled_checks.get(CHECK_DIG_SYNC)
        else ThresholdCheckConfig(enabled=False),
    }


def ensure_preset_rules(preset) -> List[AlarmPolicyRule]:
    """Devuelve reglas del preset; las genera desde checks si faltan."""
    rules = getattr(preset, "rules", None) or []
    if rules:
        return [AlarmPolicyRule.from_dict(r.to_dict()) if hasattr(r, "to_dict") else AlarmPolicyRule.from_dict(r) for r in rules]
    return rules_from_checks(preset.checks, threshold_mode=str(preset.threshold_mode or "noise_relative"))


def format_rule_label(
    rule: AlarmPolicyRule,
    *,
    threshold_mode: str,
    tr: Callable[[str], str],
) -> str:
    cond_key = CONDITION_I18N.get(rule.condition_type, rule.condition_type)
    cond = tr(cond_key)
    if rule.condition_type == COND_SYNC_LOST:
        return cond
    if rule.threshold is None:
        return cond
    value = f"{rule.threshold:.1f}"
    if rule.condition_type in DROP_CONDITIONS:
        return tr("monitor_alarm_rule_row_drop").format(condition=cond, value=value)
    if rule.condition_type == COND_RX_LEVEL_BELOW:
        return tr("monitor_alarm_rule_row_rx_below").format(value=value)
    if rule.condition_type == COND_TX_LEVEL_ABOVE:
        return tr("monitor_alarm_rule_row_tx_above").format(value=value)
    return tr("monitor_alarm_rule_row_below").format(condition=cond, value=value)


def format_rule_summary(
    rules: Iterable[AlarmPolicyRule],
    *,
    threshold_mode: str,
    tr: Callable[[str], str],
) -> str:
    parts: List[str] = []
    for rule in rules:
        if not rule.enabled:
            continue
        label = format_rule_label(rule, threshold_mode=threshold_mode, tr=tr)
        sev = tr(f"monitor_severity_{rule.severity}")
        parts.append(f"{label} → {sev}")
    return tr("monitor_alarm_rule_sep").join(parts) if parts else "—"


def preset_policy_rows(
    preset,
    *,
    tr: Callable[[str], str],
) -> List[Dict[str, Any]]:
    rules = ensure_preset_rules(preset)
    mode = str(preset.threshold_mode or "noise_relative")
    rows: List[Dict[str, Any]] = []
    for rule in rules:
        if not rule.enabled:
            continue
        row = {
            "rule_id": rule.rule_id,
            "label": format_rule_label(rule, threshold_mode=mode, tr=tr),
            "severity": rule.severity,
            "comment": rule.comment,
            "threshold": rule.threshold,
            "condition_type": rule.condition_type,
        }
        for sev in ALL_ALARM_SEVERITIES:
            row[sev] = rule.severity == sev
        rows.append(row)
    return rows
