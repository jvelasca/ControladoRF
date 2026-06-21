"""Presets de umbrales por tecnología RF.

Presets integrados (``BUILTIN_PRESETS``) son solo lectura en UI; el operador los
copia a ``user_presets`` para personalizar. Modos: ``noise_relative`` (vs ruido
local) y ``nominal_delta`` (caída vs referencia fijada en el aire).

Ver ``docs/monitor_supervision_premisas.md``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from core.inventory_catalog import (
    DEVICE_TYPE_IEM,
    DEVICE_TYPE_INTERCOM,
    DEVICE_TYPE_MICROPHONE,
)
from core.monitor.supervision.digital_supervision import (
    MODULATION_ANALOG,
    MODULATION_DIGITAL_DAB,
    MODULATION_DIGITAL_QAM,
    MODULATION_DIGITAL_QPSK,
    infer_modulation_class,
    is_digital_modulation_class,
)
from core.monitor.supervision.alarm_policy_rules import (
    AlarmPolicyRule,
    COND_CARRIER_BELOW,
    COND_DROP_CARRIER,
    COND_DROP_MER,
    COND_DROP_SNR,
    COND_MER_BELOW,
    COND_SNR_BELOW,
    COND_SYNC_LOST,
    COND_TX_LEVEL_ABOVE,
    checks_from_rules,
    ensure_preset_rules,
    new_rule_id,
    rules_from_checks,
)
from core.monitor.supervision.threshold_checks import (
    CHECK_CARRIER,
    CHECK_DIG_SYNC,
    CHECK_MER,
    CHECK_SNR,
    ThresholdCheckConfig,
    default_clear_value,
    merge_check_config,
)

PRESET_ALARM_NORMAL_FM = "alarm_normal_fm"
PRESET_ALARM_STRICT_FM = "alarm_strict_fm"
PRESET_ALARM_NORMAL_DIG = "alarm_normal_dig"
PRESET_ALARM_STRICT_DIG = "alarm_strict_dig"
# Alias legacy (proyectos guardados con ids antiguos)
PRESET_ALARM_NORMAL = PRESET_ALARM_NORMAL_FM
PRESET_ALARM_STRICT = PRESET_ALARM_STRICT_FM
PRESET_ANALOG_STANDARD = "analog_standard"
PRESET_ANALOG_STRICT = "analog_strict"
PRESET_DIGITAL_QPSK = "digital_qpsk"
PRESET_DIGITAL_QAM = "digital_qam"
PRESET_DIGITAL_RELAXED = "digital_relaxed"
PRESET_DECT = "dect_voice"
PRESET_INTERCOM = "intercom_ifb"
PRESET_CARRIER_ONLY = "carrier_only"
PRESET_UNSUPERVISED = "unsupervised"
PRESET_NOMINAL_STANDARD = "nominal_standard"
PRESET_NOMINAL_STRICT = "nominal_strict"

FUNDAMENTAL_PRESET_ORDER: tuple[str, ...] = (
    PRESET_ALARM_NORMAL_FM,
    PRESET_ALARM_STRICT_FM,
    PRESET_ALARM_NORMAL_DIG,
    PRESET_ALARM_STRICT_DIG,
)

FUNDAMENTAL_PRESET_IDS = frozenset(FUNDAMENTAL_PRESET_ORDER)

LEGACY_FUNDAMENTAL_ALIASES: Dict[str, str] = {
    "alarm_normal": PRESET_ALARM_NORMAL_FM,
    "alarm_strict": PRESET_ALARM_STRICT_FM,
}


def normalize_alarm_preset_id(preset_id: str) -> str:
    pid = str(preset_id or "").strip()
    return LEGACY_FUNDAMENTAL_ALIASES.get(pid, pid)


def _snr(w: float, c: float, *, debounce: int = 500) -> ThresholdCheckConfig:
    return ThresholdCheckConfig(
        enabled=True,
        warning_raise=w,
        warning_clear=default_clear_value(w),
        critical_raise=c,
        critical_clear=default_clear_value(c),
        debounce_ms=debounce,
    )


def _carrier(margin: float, *, debounce: int = 500) -> ThresholdCheckConfig:
    return ThresholdCheckConfig(
        enabled=True,
        warning_raise=margin + 1.0,
        warning_clear=default_clear_value(margin + 1.0),
        critical_raise=margin,
        critical_clear=default_clear_value(margin),
        debounce_ms=debounce,
    )


def _mer(w: float, c: float, *, debounce: int = 1500) -> ThresholdCheckConfig:
    return ThresholdCheckConfig(
        enabled=True,
        warning_raise=w,
        warning_clear=default_clear_value(w),
        critical_raise=c,
        critical_clear=default_clear_value(c),
        debounce_ms=debounce,
    )


def _sync(*, debounce: int = 1500) -> ThresholdCheckConfig:
    return ThresholdCheckConfig(enabled=True, debounce_ms=debounce)


def _disabled() -> ThresholdCheckConfig:
    return ThresholdCheckConfig(enabled=False)


@dataclass
class AlarmPreset:
    preset_id: str
    name_key: str
    technology: str
    checks: Dict[str, ThresholdCheckConfig] = field(default_factory=dict)
    rules: List[AlarmPolicyRule] = field(default_factory=list)
    is_builtin: bool = True
    is_fundamental: bool = False
    threshold_mode: str = "noise_relative"

    def to_dict(self) -> Dict[str, Any]:
        policy_rules = self.rules if self.rules else rules_from_checks(
            self.checks, threshold_mode=self.threshold_mode
        )
        payload: Dict[str, Any] = {
            "preset_id": self.preset_id,
            "name_key": self.name_key,
            "technology": self.technology,
            "checks": {key: cfg.to_dict() for key, cfg in self.checks.items()},
            "rules": [rule.to_dict() for rule in policy_rules],
            "is_builtin": bool(self.is_builtin),
            "is_fundamental": bool(self.is_fundamental),
        }
        if self.threshold_mode and self.threshold_mode != "noise_relative":
            payload["threshold_mode"] = self.threshold_mode
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AlarmPreset:
        checks_raw = data.get("checks") or {}
        checks = {
            str(key): ThresholdCheckConfig.from_dict(value)
            for key, value in checks_raw.items()
            if isinstance(value, dict)
        }
        rules_raw = data.get("rules") or []
        rules = [
            AlarmPolicyRule.from_dict(item)
            for item in rules_raw
            if isinstance(item, dict)
        ]
        mode = str(data.get("threshold_mode") or "noise_relative")
        if mode not in ("noise_relative", "nominal_delta"):
            mode = "noise_relative"
        if not rules:
            rules = rules_from_checks(checks, threshold_mode=mode)
        else:
            checks = checks_from_rules(rules, threshold_mode=mode)
        preset_id = str(data.get("preset_id") or "")
        is_fundamental = bool(data.get("is_fundamental")) or preset_id in FUNDAMENTAL_PRESET_IDS
        return cls(
            preset_id=preset_id,
            name_key=str(data.get("name_key") or data.get("preset_id") or ""),
            technology=str(data.get("technology") or "custom"),
            checks=checks,
            rules=rules,
            is_builtin=bool(data.get("is_builtin", False)) or is_fundamental,
            is_fundamental=is_fundamental,
            threshold_mode=mode,
        )

    def sync_checks_from_rules(self) -> None:
        self.checks = checks_from_rules(self.rules, threshold_mode=self.threshold_mode)


def build_fundamental_alarm_rules(*, fm: bool, strict: bool) -> List[AlarmPolicyRule]:
    """Matriz unificada analógica/digital: FM omite MER/sync; DIG las incluye."""
    if fm:
        if strict:
            rows = [
                (COND_DROP_SNR, 3.0, "critica", 500, None),
                (COND_DROP_SNR, 6.0, "menor", 500, None),
                (COND_SNR_BELOW, 10.0, "aviso", 500, 30.0),
                (COND_SNR_BELOW, 6.0, "critica", 500, None),
                (COND_CARRIER_BELOW, 3.0, "aviso", 500, 30.0),
                (COND_DROP_CARRIER, 3.0, "critica", 500, None),
                (COND_TX_LEVEL_ABOVE, 6.0, "aviso", 500, 60.0),
            ]
        else:
            rows = [
                (COND_DROP_SNR, 3.0, "critica", 500, None),
                (COND_DROP_SNR, 6.0, "menor", 500, None),
                (COND_SNR_BELOW, 6.0, "aviso", 500, 30.0),
                (COND_SNR_BELOW, 3.0, "critica", 500, None),
                (COND_CARRIER_BELOW, 2.0, "aviso", 500, 30.0),
                (COND_TX_LEVEL_ABOVE, 6.0, "aviso", 500, 60.0),
            ]
        technology = "fm"
    else:
        if strict:
            rows = [
                (COND_DROP_SNR, 3.0, "critica", 500, None),
                (COND_DROP_SNR, 6.0, "menor", 500, None),
                (COND_SNR_BELOW, 10.0, "aviso", 500, 30.0),
                (COND_SNR_BELOW, 6.0, "critica", 500, None),
                (COND_MER_BELOW, 24.0, "aviso", 1500, 45.0),
                (COND_MER_BELOW, 16.0, "critica", 1500, None),
                (COND_DROP_MER, 3.0, "critica", 1500, None),
                (COND_SYNC_LOST, None, "critica", 1500, None),
                (COND_CARRIER_BELOW, 3.0, "aviso", 500, 30.0),
                (COND_TX_LEVEL_ABOVE, 6.0, "aviso", 500, 60.0),
            ]
        else:
            rows = [
                (COND_DROP_SNR, 3.0, "critica", 500, None),
                (COND_DROP_SNR, 6.0, "menor", 500, None),
                (COND_SNR_BELOW, 8.0, "aviso", 500, 30.0),
                (COND_SNR_BELOW, 4.0, "critica", 500, None),
                (COND_MER_BELOW, 22.0, "aviso", 1500, 45.0),
                (COND_MER_BELOW, 14.0, "critica", 1500, None),
                (COND_SYNC_LOST, None, "critica", 1500, None),
                (COND_CARRIER_BELOW, 2.0, "aviso", 500, 30.0),
                (COND_TX_LEVEL_ABOVE, 6.0, "aviso", 500, 60.0),
            ]
        technology = "digital"
    del technology
    rules: List[AlarmPolicyRule] = []
    for cond, threshold, severity, debounce_ms, auto_clear_s in rows:
        rules.append(
            AlarmPolicyRule(
                rule_id=new_rule_id(),
                condition_type=cond,
                threshold=threshold,
                severity=severity,  # type: ignore[arg-type]
                debounce_ms=debounce_ms,
                auto_clear_s=auto_clear_s,
                enabled=True,
            )
        )
    return rules


def _build_builtin_presets() -> Dict[str, AlarmPreset]:
    normal_fm_rules = build_fundamental_alarm_rules(fm=True, strict=False)
    strict_fm_rules = build_fundamental_alarm_rules(fm=True, strict=True)
    normal_dig_rules = build_fundamental_alarm_rules(fm=False, strict=False)
    strict_dig_rules = build_fundamental_alarm_rules(fm=False, strict=True)
    return {
        PRESET_ALARM_NORMAL_FM: AlarmPreset(
            preset_id=PRESET_ALARM_NORMAL_FM,
            name_key="monitor_preset_alarm_normal_fm",
            technology="fm",
            rules=normal_fm_rules,
            checks=checks_from_rules(normal_fm_rules, threshold_mode="noise_relative"),
            is_builtin=True,
            is_fundamental=True,
        ),
        PRESET_ALARM_STRICT_FM: AlarmPreset(
            preset_id=PRESET_ALARM_STRICT_FM,
            name_key="monitor_preset_alarm_strict_fm",
            technology="fm",
            rules=strict_fm_rules,
            checks=checks_from_rules(strict_fm_rules, threshold_mode="noise_relative"),
            is_builtin=True,
            is_fundamental=True,
        ),
        PRESET_ALARM_NORMAL_DIG: AlarmPreset(
            preset_id=PRESET_ALARM_NORMAL_DIG,
            name_key="monitor_preset_alarm_normal_dig",
            technology="digital",
            rules=normal_dig_rules,
            checks=checks_from_rules(normal_dig_rules, threshold_mode="noise_relative"),
            is_builtin=True,
            is_fundamental=True,
        ),
        PRESET_ALARM_STRICT_DIG: AlarmPreset(
            preset_id=PRESET_ALARM_STRICT_DIG,
            name_key="monitor_preset_alarm_strict_dig",
            technology="digital",
            rules=strict_dig_rules,
            checks=checks_from_rules(strict_dig_rules, threshold_mode="noise_relative"),
            is_builtin=True,
            is_fundamental=True,
        ),
        PRESET_ANALOG_STANDARD: AlarmPreset(
            preset_id=PRESET_ANALOG_STANDARD,
            name_key="monitor_preset_analog_standard",
            technology="analog",
            checks={
                CHECK_SNR: _snr(6.0, 3.0),
                CHECK_CARRIER: _carrier(2.0),
                CHECK_MER: _disabled(),
                CHECK_DIG_SYNC: _disabled(),
            },
        ),
        PRESET_ANALOG_STRICT: AlarmPreset(
            preset_id=PRESET_ANALOG_STRICT,
            name_key="monitor_preset_analog_strict",
            technology="analog",
            checks={
                CHECK_SNR: _snr(10.0, 6.0),
                CHECK_CARRIER: _carrier(3.0),
                CHECK_MER: _disabled(),
                CHECK_DIG_SYNC: _disabled(),
            },
        ),
        PRESET_DIGITAL_QPSK: AlarmPreset(
            preset_id=PRESET_DIGITAL_QPSK,
            name_key="monitor_preset_digital_qpsk",
            technology="digital",
            checks={
                CHECK_SNR: _snr(8.0, 4.0),
                CHECK_CARRIER: _carrier(2.0),
                CHECK_MER: _mer(24.0, 16.0),
                CHECK_DIG_SYNC: _sync(),
            },
        ),
        PRESET_DIGITAL_QAM: AlarmPreset(
            preset_id=PRESET_DIGITAL_QAM,
            name_key="monitor_preset_digital_qam",
            technology="digital",
            checks={
                CHECK_SNR: _snr(6.0, 3.0),
                CHECK_CARRIER: _carrier(2.0),
                CHECK_MER: _mer(20.0, 12.0),
                CHECK_DIG_SYNC: _sync(),
            },
        ),
        PRESET_DIGITAL_RELAXED: AlarmPreset(
            preset_id=PRESET_DIGITAL_RELAXED,
            name_key="monitor_preset_digital_relaxed",
            technology="digital",
            checks={
                CHECK_SNR: _snr(6.0, 3.0),
                CHECK_CARRIER: _carrier(2.0),
                CHECK_MER: _disabled(),
                CHECK_DIG_SYNC: _disabled(),
            },
        ),
        PRESET_DECT: AlarmPreset(
            preset_id=PRESET_DECT,
            name_key="monitor_preset_dect",
            technology="dect",
            checks={
                CHECK_SNR: _snr(12.0, 8.0),
                CHECK_CARRIER: _carrier(4.0),
                CHECK_MER: _disabled(),
                CHECK_DIG_SYNC: _disabled(),
            },
        ),
        PRESET_INTERCOM: AlarmPreset(
            preset_id=PRESET_INTERCOM,
            name_key="monitor_preset_intercom",
            technology="intercom",
            checks={
                CHECK_SNR: _snr(8.0, 5.0),
                CHECK_CARRIER: _carrier(3.0),
                CHECK_MER: _disabled(),
                CHECK_DIG_SYNC: _disabled(),
            },
        ),
        PRESET_CARRIER_ONLY: AlarmPreset(
            preset_id=PRESET_CARRIER_ONLY,
            name_key="monitor_preset_carrier_only",
            technology="accessory",
            checks={
                CHECK_SNR: _disabled(),
                CHECK_CARRIER: _carrier(2.0),
                CHECK_MER: _disabled(),
                CHECK_DIG_SYNC: _disabled(),
            },
        ),
        PRESET_UNSUPERVISED: AlarmPreset(
            preset_id=PRESET_UNSUPERVISED,
            name_key="monitor_preset_unsupervised",
            technology="none",
            checks={
                CHECK_SNR: _disabled(),
                CHECK_CARRIER: _disabled(),
                CHECK_MER: _disabled(),
                CHECK_DIG_SYNC: _disabled(),
            },
        ),
        PRESET_NOMINAL_STANDARD: AlarmPreset(
            preset_id=PRESET_NOMINAL_STANDARD,
            name_key="monitor_preset_nominal_standard",
            technology="nominal",
            threshold_mode="nominal_delta",
            checks={
                CHECK_SNR: _snr(3.0, 6.0),
                CHECK_CARRIER: _carrier(3.0),
                CHECK_MER: _mer(3.0, 6.0),
                CHECK_DIG_SYNC: _sync(),
            },
        ),
        PRESET_NOMINAL_STRICT: AlarmPreset(
            preset_id=PRESET_NOMINAL_STRICT,
            name_key="monitor_preset_nominal_strict",
            technology="nominal",
            threshold_mode="nominal_delta",
            checks={
                CHECK_SNR: _snr(2.0, 4.0),
                CHECK_CARRIER: _carrier(2.0),
                CHECK_MER: _mer(2.0, 4.0),
                CHECK_DIG_SYNC: _sync(),
            },
        ),
    }


BUILTIN_PRESETS: Dict[str, AlarmPreset] = _build_builtin_presets()

BUILTIN_PRESET_ORDER: tuple[str, ...] = (
    PRESET_ANALOG_STANDARD,
    PRESET_ANALOG_STRICT,
    PRESET_NOMINAL_STANDARD,
    PRESET_NOMINAL_STRICT,
    PRESET_DIGITAL_QPSK,
    PRESET_DIGITAL_QAM,
    PRESET_DIGITAL_RELAXED,
    PRESET_DECT,
    PRESET_INTERCOM,
    PRESET_CARRIER_ONLY,
    PRESET_UNSUPERVISED,
)


def get_preset(preset_id: str, user_presets: Dict[str, AlarmPreset] | None = None) -> Optional[AlarmPreset]:
    pid = normalize_alarm_preset_id(str(preset_id or "").strip())
    if not pid:
        return None
    builtin = BUILTIN_PRESETS.get(pid)
    if builtin is not None:
        return builtin
    if user_presets and pid in user_presets:
        return user_presets[pid]
    return None


def is_fundamental_preset(preset_id: str) -> bool:
    return normalize_alarm_preset_id(str(preset_id or "")) in FUNDAMENTAL_PRESET_IDS


def list_alarm_threshold_preset_options(user_presets: Dict[str, AlarmPreset] | None = None) -> List[str]:
    """Presets visibles en el diálogo Umbrales: Normal, Estricto + usuario."""
    ids = list(FUNDAMENTAL_PRESET_ORDER)
    if user_presets:
        for pid in sorted(user_presets.keys()):
            if pid not in ids:
                ids.append(pid)
    return ids


def preset_display_name(preset: AlarmPreset, *, tr: Any = None) -> str:
    if preset.is_fundamental or preset.is_builtin:
        if tr is not None:
            return str(tr(preset.name_key))
        return preset.name_key
    return str(preset.name_key)


def resolve_active_alarm_preset_id(state) -> str:
    active = normalize_alarm_preset_id(str(getattr(state, "active_alarm_preset_id", "") or ""))
    user_presets = _user_presets_from_state(state)
    if active and get_preset(active, user_presets) is not None:
        return active
    legacy = normalize_alarm_preset_id(str(getattr(state, "default_preset_id", "") or ""))
    if legacy and get_preset(legacy, user_presets) is not None:
        return legacy
    return PRESET_ALARM_NORMAL_FM


def _user_presets_from_state(state) -> Dict[str, AlarmPreset]:
    raw = getattr(state, "user_presets", None) or {}
    return {
        key: AlarmPreset.from_dict(value)
        for key, value in raw.items()
        if isinstance(value, dict)
    }


def list_preset_options(user_presets: Dict[str, AlarmPreset] | None = None) -> List[str]:
    ids = list(BUILTIN_PRESET_ORDER)
    if user_presets:
        for pid in sorted(user_presets.keys()):
            if pid not in ids:
                ids.append(pid)
    return ids


def infer_preset_for_equipo(equipo: Dict[str, Any]) -> str:
    """Preset sugerido según tipo de dispositivo y modulación."""
    device_type = str(equipo.get("device_type") or "other")
    modulation = infer_modulation_class(equipo)

    if device_type == DEVICE_TYPE_INTERCOM:
        return PRESET_INTERCOM
    if device_type == DEVICE_TYPE_IEM:
        if modulation == MODULATION_DIGITAL_QAM:
            return PRESET_DIGITAL_QAM
        return PRESET_ANALOG_STANDARD
    if modulation == MODULATION_DIGITAL_DAB:
        return PRESET_DIGITAL_QPSK
    if modulation == MODULATION_DIGITAL_QAM:
        return PRESET_DIGITAL_QAM
    if modulation == MODULATION_DIGITAL_QPSK or is_digital_modulation_class(modulation):
        return PRESET_DIGITAL_QPSK
    if "DECT" in f"{equipo.get('series', '')} {equipo.get('model', '')}".upper():
        return PRESET_DECT
    if device_type == DEVICE_TYPE_MICROPHONE:
        return PRESET_ANALOG_STANDARD
    if device_type in ("antenna_accessory", "charger", "spectrum_manager"):
        return PRESET_CARRIER_ONLY
    if modulation == MODULATION_ANALOG:
        return PRESET_ANALOG_STANDARD
    return PRESET_ANALOG_STANDARD


def clone_preset_checks(preset: AlarmPreset) -> Dict[str, ThresholdCheckConfig]:
    rules = [AlarmPolicyRule.from_dict(r.to_dict()) for r in ensure_preset_rules(preset)]
    return checks_from_rules(rules, threshold_mode=str(preset.threshold_mode or "noise_relative"))


def clone_preset_rules(preset: AlarmPreset) -> List[AlarmPolicyRule]:
    return [AlarmPolicyRule.from_dict(r.to_dict()) for r in ensure_preset_rules(preset)]


def apply_check_overrides(
    checks: Dict[str, ThresholdCheckConfig],
    overrides: Dict[str, Dict[str, Any]] | None,
) -> Dict[str, ThresholdCheckConfig]:
    if not overrides:
        return checks
    merged = dict(checks)
    for check_id, partial in overrides.items():
        if check_id not in merged:
            merged[check_id] = ThresholdCheckConfig()
        merged[check_id] = merge_check_config(merged[check_id], partial)
    return merged


def preset_from_supervision_rules(rules_dict: Dict[str, Any]) -> AlarmPreset:
    """Convierte reglas legacy v1 en preset equivalente."""
    warning = float(rules_dict.get("warning_above_noise_db", 6.0))
    critical = float(rules_dict.get("critical_above_noise_db", 3.0))
    carrier = float(rules_dict.get("carrier_loss_margin_db", 2.0))
    digital = bool(rules_dict.get("digital_metrics_enabled", True))
    mer_w = float(rules_dict.get("mer_warning_db", 22.0))
    mer_c = float(rules_dict.get("mer_critical_db", 14.0))
    debounce = int(rules_dict.get("debounce_ms", 500))
    dig_debounce = int(rules_dict.get("digital_debounce_ms", 1500))
    return AlarmPreset(
        preset_id="legacy_custom",
        name_key="monitor_preset_legacy",
        technology="custom",
        checks={
            CHECK_SNR: _snr(warning, critical, debounce=debounce),
            CHECK_CARRIER: _carrier(carrier, debounce=debounce),
            CHECK_MER: _mer(mer_w, mer_c, debounce=dig_debounce) if digital else _disabled(),
            CHECK_DIG_SYNC: _sync(debounce=dig_debounce) if digital else _disabled(),
        },
        is_builtin=False,
    )


def iter_all_presets(user_presets: Dict[str, AlarmPreset] | None = None) -> Iterable[AlarmPreset]:
    for pid in BUILTIN_PRESET_ORDER:
        preset = BUILTIN_PRESETS.get(pid)
        if preset is not None:
            yield preset
    if user_presets:
        for pid in sorted(user_presets.keys()):
            yield user_presets[pid]
