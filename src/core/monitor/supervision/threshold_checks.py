"""Catálogo de checks de umbral para supervisión RF.

Cada check define una magnitud medible (SNR, portadora, MER, sync) con umbrales
raise/clear independientes. Los presets (`alarm_presets.py`) agrupan checks; el
modo ``noise_relative`` o ``nominal_delta`` determina la semántica de evaluación.

Ver ``docs/monitor_supervision_premisas.md``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Literal, Optional

CheckId = Literal["snr_above_noise", "carrier_present", "mer_db", "dig_sync"]

CHECK_SNR = "snr_above_noise"
CHECK_CARRIER = "carrier_present"
CHECK_MER = "mer_db"
CHECK_DIG_SYNC = "dig_sync"

ALL_CHECK_IDS: tuple[str, ...] = (
    CHECK_SNR,
    CHECK_CARRIER,
    CHECK_MER,
    CHECK_DIG_SYNC,
)


@dataclass
class ThresholdCheckConfig:
    """Umbrales raise/clear por check y severidad (aviso/menor/critica/comentario)."""

    enabled: bool = True
    warning_raise: Optional[float] = None  # aviso (compat v2)
    warning_clear: Optional[float] = None
    critical_raise: Optional[float] = None  # critica (compat v2)
    critical_clear: Optional[float] = None
    menor_raise: Optional[float] = None
    menor_clear: Optional[float] = None
    comentario_raise: Optional[float] = None
    comentario_clear: Optional[float] = None
    debounce_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"enabled": bool(self.enabled)}
        for key in (
            "warning_raise",
            "warning_clear",
            "critical_raise",
            "critical_clear",
            "menor_raise",
            "menor_clear",
            "comentario_raise",
            "comentario_clear",
            "debounce_ms",
        ):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> ThresholdCheckConfig:
        raw = data or {}
        debounce = raw.get("debounce_ms")
        return cls(
            enabled=bool(raw.get("enabled", True)),
            warning_raise=_optional_float(raw.get("warning_raise")),
            warning_clear=_optional_float(raw.get("warning_clear")),
            critical_raise=_optional_float(raw.get("critical_raise")),
            critical_clear=_optional_float(raw.get("critical_clear")),
            menor_raise=_optional_float(raw.get("menor_raise")),
            menor_clear=_optional_float(raw.get("menor_clear")),
            comentario_raise=_optional_float(raw.get("comentario_raise")),
            comentario_clear=_optional_float(raw.get("comentario_clear")),
            debounce_ms=int(debounce) if debounce is not None else None,
        )


@dataclass(frozen=True)
class CheckDefinition:
    check_id: str
    i18n_name_key: str
    i18n_unit_key: str
    direction: Literal["lower_worse", "bool_false_worse"]
    default_debounce_ms: int
    applies_to: frozenset[str]  # technology tags: analog, digital, dect, all


CHECK_CATALOG: Dict[str, CheckDefinition] = {
    CHECK_SNR: CheckDefinition(
        check_id=CHECK_SNR,
        i18n_name_key="monitor_check_snr",
        i18n_unit_key="monitor_check_unit_db",
        direction="lower_worse",
        default_debounce_ms=500,
        applies_to=frozenset({"all"}),
    ),
    CHECK_CARRIER: CheckDefinition(
        check_id=CHECK_CARRIER,
        i18n_name_key="monitor_check_carrier",
        i18n_unit_key="monitor_check_unit_db",
        direction="lower_worse",
        default_debounce_ms=500,
        applies_to=frozenset({"all"}),
    ),
    CHECK_MER: CheckDefinition(
        check_id=CHECK_MER,
        i18n_name_key="monitor_check_mer",
        i18n_unit_key="monitor_check_unit_db",
        direction="lower_worse",
        default_debounce_ms=1500,
        applies_to=frozenset({"digital"}),
    ),
    CHECK_DIG_SYNC: CheckDefinition(
        check_id=CHECK_DIG_SYNC,
        i18n_name_key="monitor_check_dig_sync",
        i18n_unit_key="monitor_check_unit_bool",
        direction="bool_false_worse",
        default_debounce_ms=1500,
        applies_to=frozenset({"digital"}),
    ),
}


def iter_check_definitions() -> Iterable[CheckDefinition]:
    for check_id in ALL_CHECK_IDS:
        definition = CHECK_CATALOG.get(check_id)
        if definition is not None:
            yield definition


def merge_check_config(
    base: ThresholdCheckConfig,
    partial: Dict[str, Any] | None,
) -> ThresholdCheckConfig:
    if not partial:
        return base
    data = base.to_dict()
    for key, value in partial.items():
        if value is not None:
            data[key] = value
    return ThresholdCheckConfig.from_dict(data)


def default_clear_value(raise_value: float, *, hysteresis: float = 0.5) -> float:
    """Clear ligeramente por encima del raise (anti-flapping)."""
    return float(raise_value) + float(hysteresis)


def _optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
