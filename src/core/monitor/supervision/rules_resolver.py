"""Resolución de umbrales de supervisión — global, zona, tipo, fabricante, modelo y canal."""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core.inventory_catalog import _TYPE_I18N
from core.inventory_channel import find_equipo_in_list, normalize_equipo
from core.monitor.supervision.supervision_models import SupervisionRules, SupervisionState

SCOPE_GLOBAL = "global"
SCOPE_ZONE = "zone"
SCOPE_DEVICE_TYPE = "device_type"
SCOPE_MANUFACTURER = "manufacturer"
SCOPE_MODEL = "model"
SCOPE_CHANNEL = "channel"

# De menos a más específico (el último aplicado prevalece en conflictos de campo).
SCOPE_LAYER_ORDER = (
    SCOPE_ZONE,
    SCOPE_DEVICE_TYPE,
    SCOPE_MANUFACTURER,
    SCOPE_MODEL,
    SCOPE_CHANNEL,
)

THRESHOLD_SCOPES = (
    SCOPE_GLOBAL,
    SCOPE_ZONE,
    SCOPE_DEVICE_TYPE,
    SCOPE_MANUFACTURER,
    SCOPE_MODEL,
    SCOPE_CHANNEL,
)


def rule_override_key(scope: str, value: str) -> str:
    return f"{scope}:{value}"


def parse_rule_override_key(key: str) -> Tuple[str, str]:
    raw = str(key or "")
    if ":" not in raw:
        return "", raw
    scope, value = raw.split(":", 1)
    return scope, value


def merge_rules(base: SupervisionRules, partial: Dict[str, Any] | None) -> SupervisionRules:
    if not partial:
        return base
    data = base.to_dict()
    for field in (
        "warning_above_noise_db",
        "critical_above_noise_db",
        "carrier_loss_margin_db",
        "debounce_ms",
        "digital_metrics_enabled",
        "mer_warning_db",
        "mer_critical_db",
        "digital_debounce_ms",
    ):
        if field in partial and partial[field] is not None:
            data[field] = partial[field]
    return SupervisionRules.from_dict(data)


def resolve_effective_rules(
    state: SupervisionState,
    *,
    channel_key: str = "",
    equipo: Dict[str, Any] | None = None,
) -> SupervisionRules:
    """Precedencia: canal → modelo → fabricante → tipo → zona → preset global."""
    from core.monitor.supervision.threshold_resolver import resolve_effective_rules as _resolve

    return _resolve(state, channel_key=channel_key, equipo=equipo)


def resolve_rules_for_scope(
    state: SupervisionState,
    scope: str,
    key: str = "",
    *,
    equipos: Optional[List[Dict[str, Any]]] = None,
) -> SupervisionRules:
    """Reglas efectivas mostradas al editar un ámbito concreto."""
    if scope == SCOPE_GLOBAL or not scope:
        return SupervisionRules.from_dict(state.rules.to_dict())
    if not key:
        return SupervisionRules.from_dict(state.rules.to_dict())

    temp = clone_supervision_state(state)
    saved_override = state.rule_overrides.get(rule_override_key(scope, key))
    clear_rule_override(temp, scope, key)

    if scope == SCOPE_CHANNEL:
        equipo = _find_equipo(equipos or [], key)
        return resolve_effective_rules(temp, channel_key=key, equipo=equipo)

    sample = _sample_equipo_for_scope(equipos or [], scope, key)
    if sample:
        inherited = resolve_effective_rules(
            temp,
            channel_key=str(sample.get("channel_key") or ""),
            equipo=sample,
        )
    else:
        inherited = SupervisionRules.from_dict(temp.rules.to_dict())

    if saved_override:
        return merge_rules(inherited, saved_override)
    return inherited


def has_rule_override(state: SupervisionState, scope: str, key: str) -> bool:
    if scope == SCOPE_GLOBAL or not key:
        return False
    return rule_override_key(scope, key) in state.rule_overrides


def set_rule_override(
    state: SupervisionState,
    scope: str,
    key: str,
    rules: SupervisionRules,
) -> None:
    if scope == SCOPE_GLOBAL or not key:
        state.rules = SupervisionRules.from_dict(rules.to_dict())
        return
    state.rule_overrides[rule_override_key(scope, key)] = rules.to_dict()


def clear_rule_override(state: SupervisionState, scope: str, key: str) -> None:
    if scope == SCOPE_GLOBAL or not key:
        return
    state.rule_overrides.pop(rule_override_key(scope, key), None)


def set_channel_digital_metrics(
    state: SupervisionState,
    channel_key: str,
    *,
    enabled: bool,
    equipos: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Fija modo digital (MER/sync) para un canal concreto."""
    equipo = _find_equipo(equipos or [], channel_key)
    rules = resolve_effective_rules(state, channel_key=channel_key, equipo=equipo)
    rules.digital_metrics_enabled = bool(enabled)
    set_rule_override(state, SCOPE_CHANNEL, channel_key, rules)


def validate_rules(warning_db: float, critical_db: float) -> bool:
    """El umbral crítico debe ser menor o igual que el de aviso (SNR más exigente)."""
    return float(critical_db) <= float(warning_db)


def validate_mer_rules(warning_db: float, critical_db: float) -> bool:
    """MER crítico debe ser menor o igual que aviso (más exigente)."""
    return float(critical_db) <= float(warning_db)


def collect_scope_options(
    equipos: Iterable[Dict[str, Any]],
    *,
    tr: Callable[[str], str] | None = None,
) -> Dict[str, List[Tuple[str, str]]]:
    """Opciones para combos del diálogo: (id, etiqueta)."""
    normalized = [normalize_equipo(item) for item in equipos if isinstance(item, dict)]
    zones: Dict[str, str] = {}
    device_types: Dict[str, str] = {}
    manufacturers: Dict[str, str] = {}
    models: Dict[str, str] = {}
    channels: List[Tuple[str, str]] = []

    translate = tr or (lambda key: key)

    for item in normalized:
        zone = _zone_scope_value(item.get("zone"))
        zones[zone] = zone
        dtype = str(item.get("device_type") or "other")
        i18n_key = _TYPE_I18N.get(dtype, "inventory_type_other")
        device_types[dtype] = translate(i18n_key)
        manufacturer = _clean_scope_value(item.get("manufacturer"))
        model = _clean_scope_value(item.get("model"))
        if manufacturer:
            manufacturers[manufacturer] = manufacturer
        if model:
            models[model] = model
        key = str(item.get("channel_key") or "")
        if not key:
            continue
        label = str(item.get("channel_name") or item.get("device_name") or key)
        freq = item.get("frequency_mhz")
        if freq not in (None, ""):
            try:
                label = f"{label} · {float(freq):.3f} MHz"
            except (TypeError, ValueError):
                pass
        channels.append((key, label))

    channels.sort(key=lambda row: row[1].casefold())
    zone_rows = sorted(((key, key) for key in zones), key=lambda row: row[1].casefold())
    device_rows = sorted(device_types.items(), key=lambda row: row[1].casefold())
    manufacturer_rows = sorted(((key, key) for key in manufacturers), key=lambda row: row[1].casefold())
    model_rows = sorted(((key, key) for key in models), key=lambda row: row[1].casefold())
    return {
        SCOPE_ZONE: zone_rows,
        SCOPE_DEVICE_TYPE: device_rows,
        SCOPE_MANUFACTURER: manufacturer_rows,
        SCOPE_MODEL: model_rows,
        SCOPE_CHANNEL: channels,
    }


def clone_supervision_state(state: SupervisionState) -> SupervisionState:
    from core.monitor.supervision.supervision_models import SupervisionState as State

    return State.from_dict(state.to_dict())


def _zone_scope_value(value: Any) -> str:
    text = _clean_scope_value(value)
    return text or "Default"


def _clean_scope_value(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text in ("—", "-", "?"):
        return ""
    return text


def _find_equipo(equipos: List[Dict[str, Any]], channel_key: str) -> Dict[str, Any]:
    normalized = [normalize_equipo(item) for item in equipos if isinstance(item, dict)]
    found = find_equipo_in_list(normalized, channel_key)
    return found or {}


def _sample_equipo_for_scope(
    equipos: List[Dict[str, Any]],
    scope: str,
    key: str,
) -> Dict[str, Any]:
    normalized = [normalize_equipo(item) for item in equipos if isinstance(item, dict)]
    for item in normalized:
        if scope == SCOPE_ZONE and _zone_scope_value(item.get("zone")) == key:
            return item
        if scope == SCOPE_DEVICE_TYPE and str(item.get("device_type") or "other") == key:
            return item
        if scope == SCOPE_MANUFACTURER and _clean_scope_value(item.get("manufacturer")) == key:
            return item
        if scope == SCOPE_MODEL and _clean_scope_value(item.get("model")) == key:
            return item
    return {}
