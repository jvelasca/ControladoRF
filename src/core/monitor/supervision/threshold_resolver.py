"""Resolución de umbrales efectivos — presets, overrides por ámbito y canal.

Precedencia preset: canal → modelo → fabricante → tipo → zona → target → inferido.
Expone filas enriquecidas para la matriz UI del gestor de frecuencias y captura
de referencia nominal.

Ver ``docs/monitor_supervision_premisas.md``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.monitor.supervision.alarm_presets import (
    PRESET_ANALOG_STANDARD,
    PRESET_UNSUPERVISED,
    apply_check_overrides,
    clone_preset_checks,
    get_preset,
    infer_preset_for_equipo,
    list_preset_options,
    preset_from_supervision_rules,
    resolve_active_alarm_preset_id,
)
from core.monitor.supervision.rules_resolver import (
    SCOPE_CHANNEL,
    SCOPE_DEVICE_TYPE,
    SCOPE_MANUFACTURER,
    SCOPE_MODEL,
    SCOPE_ZONE,
    merge_rules,
    rule_override_key,
)
from core.monitor.supervision.supervision_models import (
    ChannelReferenceCapture,
    SupervisionRules,
    SupervisionState,
    SupervisionTarget,
)
from core.monitor.supervision.threshold_checks import (
    CHECK_CARRIER,
    CHECK_DIG_SYNC,
    CHECK_MER,
    CHECK_SNR,
    ThresholdCheckConfig,
)


@dataclass
class ResolvedThresholds:
    preset_id: str
    checks: Dict[str, ThresholdCheckConfig] = field(default_factory=dict)
    has_channel_overrides: bool = False
    threshold_mode: str = "noise_relative"
    reference: ChannelReferenceCapture = field(default_factory=ChannelReferenceCapture)

    def to_supervision_rules(self) -> SupervisionRules:
        """Compatibilidad con evaluadores y AlarmManager existentes."""
        snr = self.checks.get(CHECK_SNR, ThresholdCheckConfig())
        carrier = self.checks.get(CHECK_CARRIER, ThresholdCheckConfig())
        mer = self.checks.get(CHECK_MER, ThresholdCheckConfig())
        sync = self.checks.get(CHECK_DIG_SYNC, ThresholdCheckConfig())
        digital_enabled = bool(mer.enabled or sync.enabled)
        return SupervisionRules(
            warning_above_noise_db=float(snr.warning_raise or 6.0),
            critical_above_noise_db=float(snr.critical_raise or 3.0),
            carrier_loss_margin_db=float(carrier.critical_raise or 2.0),
            debounce_ms=int(snr.debounce_ms or 500),
            digital_metrics_enabled=digital_enabled,
            mer_warning_db=float(mer.warning_raise or 22.0),
            mer_critical_db=float(mer.critical_raise or 14.0),
            digital_debounce_ms=int(mer.debounce_ms or sync.debounce_ms or 1500),
        )


def _user_presets_map(state: SupervisionState) -> Dict[str, Any]:
    from core.monitor.supervision.alarm_presets import AlarmPreset

    result: Dict[str, AlarmPreset] = {}
    for key, raw in (state.user_presets or {}).items():
        if isinstance(raw, dict):
            result[str(key)] = AlarmPreset.from_dict(raw)
    return result


def _resolve_preset_id_for_layer(
    state: SupervisionState,
    scope: str,
    value: str,
) -> str:
    if not value:
        return ""
    override = state.rule_overrides.get(rule_override_key(scope, value))
    if isinstance(override, dict):
        preset_id = str(override.get("preset_id") or "").strip()
        if preset_id:
            return preset_id
    return ""


def resolve_preset_id(
    state: SupervisionState,
    *,
    channel_key: str = "",
    equipo: Dict[str, Any] | None = None,
    target: SupervisionTarget | None = None,
) -> str:
    """Precedencia preset: canal → modelo → fabricante → tipo → zona → target → inferido → global."""
    item = equipo or {}
    layers = (
        (SCOPE_CHANNEL, str(channel_key or "")),
        (SCOPE_MODEL, _clean(item.get("model"))),
        (SCOPE_MANUFACTURER, _clean(item.get("manufacturer"))),
        (SCOPE_DEVICE_TYPE, str(item.get("device_type") or "other")),
        (SCOPE_ZONE, _zone(item.get("zone"))),
    )
    for scope, value in layers:
        preset_id = _resolve_preset_id_for_layer(state, scope, value)
        if preset_id:
            return preset_id
    if target is not None and str(target.preset_id or "").strip():
        return str(target.preset_id).strip()
    active = resolve_active_alarm_preset_id(state)
    if active:
        return active
    default = str(state.default_preset_id or "").strip()
    if default:
        return default
    if item:
        return infer_preset_for_equipo(item)
    return PRESET_ANALOG_STANDARD


def resolve_effective_thresholds(
    state: SupervisionState,
    *,
    channel_key: str = "",
    equipo: Dict[str, Any] | None = None,
    target: SupervisionTarget | None = None,
) -> ResolvedThresholds:
    preset_id = resolve_preset_id(
        state,
        channel_key=channel_key,
        equipo=equipo,
        target=target,
    )
    preset = get_preset(preset_id, _user_presets_map(state))
    if preset is None:
        legacy = preset_from_supervision_rules(state.rules.to_dict())
        checks = clone_preset_checks(legacy)
        preset_id = legacy.preset_id
    else:
        checks = clone_preset_checks(preset)

    # Overrides legacy por ámbito (campos SupervisionRules → checks)
    item = equipo or {}
    scope_layers = (
        (SCOPE_ZONE, _zone(item.get("zone"))),
        (SCOPE_DEVICE_TYPE, str(item.get("device_type") or "other")),
        (SCOPE_MANUFACTURER, _clean(item.get("manufacturer"))),
        (SCOPE_MODEL, _clean(item.get("model"))),
        (SCOPE_CHANNEL, str(channel_key or "")),
    )
    for scope, value in scope_layers:
        if not value:
            continue
        override = state.rule_overrides.get(rule_override_key(scope, value))
        if override:
            checks = _apply_legacy_rules_to_checks(checks, override)

    has_overrides = False
    if target is not None and target.check_overrides:
        checks = apply_check_overrides(checks, target.check_overrides)
        has_overrides = True

    threshold_mode = "noise_relative"
    if preset is not None:
        threshold_mode = str(preset.threshold_mode or "noise_relative")
    if target is not None and str(target.threshold_mode or "") in ("noise_relative", "nominal_delta"):
        threshold_mode = str(target.threshold_mode)

    reference = ChannelReferenceCapture()
    if target is not None:
        reference = ChannelReferenceCapture.from_dict(target.reference.to_dict())

    return ResolvedThresholds(
        preset_id=preset_id,
        checks=checks,
        has_channel_overrides=has_overrides,
        threshold_mode=threshold_mode,
        reference=reference,
    )


def resolve_effective_rules(
    state: SupervisionState,
    *,
    channel_key: str = "",
    equipo: Dict[str, Any] | None = None,
) -> SupervisionRules:
    """API compatible — reglas efectivas para evaluación de alarmas."""
    target = _find_target(state, channel_key)
    resolved = resolve_effective_thresholds(
        state,
        channel_key=channel_key,
        equipo=equipo,
        target=target,
    )
    return resolved.to_supervision_rules()


def threshold_rows_for_state(
    state: SupervisionState,
    equipos: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filas enriquecidas para matriz UI."""
    from core.monitor.supervision.digital_supervision import (
        effective_digital_mode_for_equipo,
        infer_modulation_class,
    )
    from core.monitor.supervision.supervision_resolve import supervision_target_rows

    base_rows = supervision_target_rows(state, equipos)
    targets_by_key = {t.channel_key: t for t in state.targets}
    enriched: List[Dict[str, Any]] = []
    for row in base_rows:
        key = str(row.get("channel_key") or "")
        target = targets_by_key.get(key)
        item = _find_equipo(equipos, key)
        modulation = infer_modulation_class(item) if item else "analog_fm"
        resolved = resolve_effective_thresholds(
            state,
            channel_key=key,
            equipo=item,
            target=target,
        )
        rules = resolved.to_supervision_rules()
        digital_mode = effective_digital_mode_for_equipo(
            modulation_class=modulation,
            digital_metrics_enabled=rules.digital_metrics_enabled,
        )
        inferred = infer_preset_for_equipo(item) if item else PRESET_ANALOG_STANDARD
        snr = resolved.checks.get(CHECK_SNR, ThresholdCheckConfig())
        mer = resolved.checks.get(CHECK_MER, ThresholdCheckConfig())
        from core.monitor.supervision.alarm_rule_format import format_preset_alarm_summary

        enriched.append(
            {
                **row,
                "preset_id": resolved.preset_id,
                "inferred_preset_id": inferred,
                "has_threshold_overrides": resolved.has_channel_overrides,
                "modulation_class": modulation,
                "digital_mode": digital_mode,
                "snr_warning_db": snr.warning_raise,
                "snr_critical_db": snr.critical_raise,
                "mer_warning_db": mer.warning_raise if mer.enabled else None,
                "mer_critical_db": mer.critical_raise if mer.enabled else None,
                "snr_enabled": snr.enabled,
                "mer_enabled": mer.enabled,
                "threshold_mode": resolved.threshold_mode,
                "reference_valid": target.reference.is_valid() if target else False,
                "alarm_summary": format_preset_alarm_summary(
                    resolved.checks,
                    threshold_mode=resolved.threshold_mode,
                    tr=tr_i18n,
                ),
            }
        )
    return enriched


def set_channel_preset(
    state: SupervisionState,
    channel_key: str,
    preset_id: str,
    *,
    clear_overrides: bool = False,
) -> None:
    target = _find_target(state, channel_key)
    if target is None:
        return
    target.preset_id = str(preset_id or "").strip()
    if clear_overrides:
        target.check_overrides = {}
    preset = get_preset(target.preset_id, _user_presets_map(state))
    if preset is not None and preset.threshold_mode:
        target.threshold_mode = preset.threshold_mode


def apply_preset_to_channels(
    state: SupervisionState,
    channel_keys: List[str],
    preset_id: str,
    *,
    clear_overrides: bool = True,
) -> int:
    """Asigna un preset a varios canales. Devuelve cuántos se actualizaron."""
    updated = 0
    for key in channel_keys:
        if not key:
            continue
        if _find_target(state, key) is None:
            continue
        set_channel_preset(state, key, preset_id, clear_overrides=clear_overrides)
        target = _find_target(state, key)
        if target is None:
            continue
        if preset_id == PRESET_UNSUPERVISED:
            target.enabled = False
        elif preset_id != PRESET_UNSUPERVISED:
            target.enabled = True
        updated += 1
    return updated


def clear_references_for_channels(state: SupervisionState, channel_keys: List[str]) -> int:
    """Elimina referencias nominales memorizadas."""
    count = 0
    for key in channel_keys:
        target = _find_target(state, key)
        if target is None or not target.reference.is_valid():
            continue
        clear_channel_reference(state, key)
        count += 1
    return count


def set_channel_snr_thresholds(
    state: SupervisionState,
    channel_key: str,
    *,
    warning_db: float,
    critical_db: float,
) -> None:
    target = _find_target(state, channel_key)
    if target is None:
        return
    partial = target.check_overrides.setdefault(CHECK_SNR, {})
    partial["warning_raise"] = float(warning_db)
    partial["critical_raise"] = float(critical_db)
    partial["enabled"] = True


def capture_channel_reference(
    state: SupervisionState,
    channel_key: str,
    *,
    snr_above_noise_db: float | None = None,
    carrier_dbm: float | None = None,
    mer_db: float | None = None,
    sync_ok: bool | None = None,
    captured_at_iso: str = "",
) -> bool:
    target = _find_target(state, channel_key)
    if target is None:
        return False
    from datetime import datetime, timezone

    target.reference = ChannelReferenceCapture(
        snr_above_noise_db=snr_above_noise_db,
        carrier_dbm=carrier_dbm,
        mer_db=mer_db,
        sync_ok=sync_ok,
        captured_at_iso=captured_at_iso or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    return True


def clear_channel_reference(state: SupervisionState, channel_key: str) -> None:
    target = _find_target(state, channel_key)
    if target is not None:
        target.reference = ChannelReferenceCapture()


def preset_matrix_rows(state: SupervisionState) -> List[Dict[str, Any]]:
    """Filas resumidas para panel ALARMAS (Normal/Estricto + usuario)."""
    from core.monitor.supervision.alarm_policy_rules import ensure_preset_rules, format_rule_summary
    from core.monitor.supervision.alarm_presets import (
        list_alarm_threshold_preset_options,
        preset_display_name,
        resolve_active_alarm_preset_id,
    )

    user_presets = _user_presets_map(state)
    active_id = resolve_active_alarm_preset_id(state)
    rows: List[Dict[str, Any]] = []
    for preset_id in list_alarm_threshold_preset_options(user_presets):
        preset = get_preset(preset_id, user_presets)
        if preset is None:
            continue
        mode = str(preset.threshold_mode or "noise_relative")
        rules = ensure_preset_rules(preset)
        rows.append(
            {
                "preset_id": preset_id,
                "name": preset_display_name(preset, tr=tr_i18n),
                "is_builtin": preset.is_fundamental,
                "is_active": preset_id == active_id,
                "threshold_mode": mode,
                "rule_count": sum(1 for rule in rules if rule.enabled),
                "summary": format_rule_summary(rules, threshold_mode=mode, tr=tr_i18n),
            }
        )
    return rows


def tr_i18n(key: str, **kwargs) -> str:
    from i18n.json_translation import tr

    return tr(key, **kwargs)


def set_channel_mer_thresholds(
    state: SupervisionState,
    channel_key: str,
    *,
    warning_db: float,
    critical_db: float,
    enabled: bool = True,
) -> None:
    target = _find_target(state, channel_key)
    if target is None:
        return
    partial = target.check_overrides.setdefault(CHECK_MER, {})
    partial["warning_raise"] = float(warning_db)
    partial["critical_raise"] = float(critical_db)
    partial["enabled"] = bool(enabled)
    sync_partial = target.check_overrides.setdefault(CHECK_DIG_SYNC, {})
    sync_partial["enabled"] = bool(enabled)


def _apply_legacy_rules_to_checks(
    checks: Dict[str, ThresholdCheckConfig],
    override: Dict[str, Any],
) -> Dict[str, ThresholdCheckConfig]:
    merged_rules = merge_rules(
        SupervisionRules.from_dict({}),
        override,
    ).to_dict()
    legacy_preset = preset_from_supervision_rules(merged_rules)
    result = dict(checks)
    for check_id, cfg in legacy_preset.checks.items():
        if check_id == CHECK_SNR and any(
            key in override
            for key in ("warning_above_noise_db", "critical_above_noise_db", "debounce_ms")
        ):
            result[check_id] = ThresholdCheckConfig.from_dict(cfg.to_dict())
        if check_id == CHECK_CARRIER and "carrier_loss_margin_db" in override:
            result[check_id] = ThresholdCheckConfig.from_dict(cfg.to_dict())
        if check_id in (CHECK_MER, CHECK_DIG_SYNC) and any(
            key in override
            for key in (
                "digital_metrics_enabled",
                "mer_warning_db",
                "mer_critical_db",
                "digital_debounce_ms",
            )
        ):
            result[check_id] = ThresholdCheckConfig.from_dict(cfg.to_dict())
    if "check_overrides" in override and isinstance(override["check_overrides"], dict):
        result = apply_check_overrides(result, override["check_overrides"])
    return result


def _find_target(state: SupervisionState, channel_key: str) -> SupervisionTarget | None:
    for target in state.targets:
        if target.channel_key == channel_key:
            return target
    return None


def _find_equipo(equipos: List[Dict[str, Any]], channel_key: str) -> Dict[str, Any]:
    from core.inventory_channel import find_equipo_in_list, normalize_equipo

    normalized = [normalize_equipo(item) for item in equipos if isinstance(item, dict)]
    return find_equipo_in_list(normalized, channel_key) or {}


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text in ("", "—", "-", "?") else text


def _zone(value: Any) -> str:
    text = _clean(value)
    return text or "Default"
