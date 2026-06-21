"""Árbol de supervisión — agrupación y rollup de estados de alarma."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Literal, Optional, Sequence

from core.inventory_catalog import (
    GROUP_DEVICE_TYPE,
    GROUP_NETWORK,
    GROUP_NONE,
    GROUP_SERIES,
    GROUP_ZONE,
    _TYPE_I18N,
    enrich_equipo_metadata,
)
from core.inventory_channel import find_equipo_in_list, normalize_equipo
from core.monitor.supervision.digital_supervision import effective_digital_mode_for_equipo
from core.monitor.supervision.rules_resolver import resolve_effective_rules
from core.monitor.supervision.supervision_models import (
    AlarmDisplayRow,
    ResolvedSupervisionTarget,
    SupervisionChannelMetrics,
    SupervisionState,
)

GROUP_MODEL = "model"
GROUP_MANUFACTURER = "manufacturer"

SUPERVISION_TREE_GROUP_MODES = (
    GROUP_ZONE,
    GROUP_DEVICE_TYPE,
    GROUP_MODEL,
    GROUP_MANUFACTURER,
    GROUP_NETWORK,
    GROUP_SERIES,
    GROUP_NONE,
)

SupervisionRollup = Literal["ok", "warning_latched", "warning", "critical"]

TreeIconTone = Literal[
    "ok",
    "comentario",
    "critical_pending",
    "warning_pending",
    "acknowledged",
    "latched_critical",
    "latched_warning",
]

_ROLLUP_RANK = {
    "ok": 0,
    "warning_latched": 1,
    "warning": 2,
    "critical": 3,
}


@dataclass(frozen=True)
class SupervisionTreeChannel:
    channel_key: str
    label: str
    frequency_mhz: float
    alarm_state: str
    rollup: SupervisionRollup
    can_ack: bool
    enabled: bool = True
    device_type: str = "other"
    snr_db: Optional[float] = None
    mer_db: Optional[float] = None
    sync_ok: Optional[bool] = None
    digital_mode: str = "none"
    is_digital: bool = False
    icon_tone: TreeIconTone = "ok"


@dataclass
class SupervisionTreeGroup:
    group_key: str
    label: str
    rollup: SupervisionRollup
    channels: List[SupervisionTreeChannel] = field(default_factory=list)

    @property
    def channel_count(self) -> int:
        return len(self.channels)


def rollup_from_alarm_state(state: str) -> SupervisionRollup:
    if state in ("critical", "critical_latched"):
        return "critical"
    if state == "warning":
        return "warning"
    if state == "warning_latched":
        return "warning_latched"
    return "ok"


def tree_icon_tone_blinks(tone: TreeIconTone) -> bool:
    return tone in (
        "critical_pending",
        "warning_pending",
        "latched_critical",
        "latched_warning",
    )


def resolve_tree_icon_tone(
    alarm_state: str,
    *,
    alarm_row: AlarmDisplayRow | None = None,
) -> TreeIconTone:
    """Tono visual del icono según estado y fila activa (parpadeo / ack / comentario)."""
    if alarm_row is not None:
        if alarm_row.phase == "active":
            if alarm_row.severity == "comentario":
                return "comentario"
            if alarm_row.acknowledged:
                return "acknowledged"
            if alarm_row.severity == "critica":
                return "critical_pending"
            return "warning_pending"
        if alarm_row.phase == "latched":
            if "critica" in str(alarm_row.severity):
                return "latched_critical"
            return "latched_warning"

    if alarm_state == "comentario":
        return "comentario"
    if alarm_state == "critical":
        return "critical_pending"
    if alarm_state == "critical_latched":
        return "latched_critical"
    if alarm_state == "warning_latched":
        return "latched_warning"
    if alarm_state == "warning":
        return "warning_pending"
    return "ok"


def merge_rollups(current: SupervisionRollup, other: SupervisionRollup) -> SupervisionRollup:
    return current if _ROLLUP_RANK[current] >= _ROLLUP_RANK[other] else other


def _group_key_for_item(item: Dict, group_mode: str) -> str:
    if group_mode == GROUP_DEVICE_TYPE:
        return str(item.get("device_type") or "other")
    if group_mode == GROUP_ZONE:
        return str(item.get("zone") or "Default")
    if group_mode == GROUP_NETWORK:
        return str(item.get("network") or "Default")
    if group_mode == GROUP_SERIES:
        return str(item.get("series") or "—")
    if group_mode == GROUP_MODEL:
        return str(item.get("model") or "—")
    if group_mode == GROUP_MANUFACTURER:
        return str(item.get("manufacturer") or "—")
    return GROUP_NONE


def group_label_for_key(group_mode: str, key: str, tr: Callable[[str], str]) -> str:
    if group_mode == GROUP_DEVICE_TYPE:
        i18n_key = _TYPE_I18N.get(key, "inventory_type_other")
        return tr(i18n_key)
    return key if key not in ("", "—") else "—"


def build_supervision_tree(
    resolved: Sequence[ResolvedSupervisionTarget],
    equipos: List[Dict],
    alarm_states: Dict[str, str],
    *,
    group_mode: str,
    alarm_rows: Optional[Sequence[AlarmDisplayRow]] = None,
    channel_metrics: Optional[Dict[str, SupervisionChannelMetrics]] = None,
    supervision_state: Optional[SupervisionState] = None,
    tr: Callable[[str], str],
) -> List[SupervisionTreeGroup]:
    """Construye grupos con canales supervisados activos y rollup de alarmas."""
    if group_mode not in SUPERVISION_TREE_GROUP_MODES:
        group_mode = GROUP_ZONE

    normalized = [normalize_equipo(item) for item in equipos if isinstance(item, dict)]
    ack_by_key: Dict[str, bool] = {}
    row_by_key: Dict[str, AlarmDisplayRow] = {}
    if alarm_rows:
        for row in alarm_rows:
            ack_by_key[row.channel_key] = row.can_ack
            row_by_key[row.channel_key] = row
    metrics_by_key = channel_metrics or {}

    flat_channels: List[SupervisionTreeChannel] = []
    for target in resolved:
        enabled = bool(target.enabled)
        state = alarm_states.get(target.channel_key, "ok") if enabled else "ok"
        rollup = rollup_from_alarm_state(state) if enabled else "ok"
        item = find_equipo_in_list(normalized, target.channel_key)
        if item is None:
            item = enrich_equipo_metadata({"channel_key": target.channel_key})
        modulation = str(item.get("modulation_class") or "analog_fm")
        is_digital = str(modulation).startswith("digital_")
        metrics = metrics_by_key.get(target.channel_key)
        digital_mode = metrics.digital_mode if metrics is not None else "none"
        if is_digital and supervision_state is not None and metrics is None:
            rules = resolve_effective_rules(
                supervision_state,
                channel_key=target.channel_key,
                equipo=item,
            )
            digital_mode = effective_digital_mode_for_equipo(
                modulation_class=modulation,
                digital_metrics_enabled=rules.digital_metrics_enabled,
            )
        icon_tone = resolve_tree_icon_tone(
            state,
            alarm_row=row_by_key.get(target.channel_key),
        )
        flat_channels.append(
            SupervisionTreeChannel(
                channel_key=target.channel_key,
                label=target.label,
                frequency_mhz=target.frequency_hz / 1e6,
                alarm_state=state,
                rollup=rollup,
                can_ack=ack_by_key.get(target.channel_key, False) if enabled else False,
                enabled=enabled,
                device_type=str(target.device_type or "other"),
                snr_db=metrics.snr_db if metrics is not None else None,
                mer_db=metrics.mer_db if metrics is not None else None,
                sync_ok=metrics.sync_ok if metrics is not None else None,
                digital_mode=digital_mode,
                is_digital=is_digital,
                icon_tone=icon_tone,
            )
        )

    if not flat_channels:
        return []

    if group_mode == GROUP_NONE:
        rollup = "ok"
        for channel in flat_channels:
            if channel.enabled:
                rollup = merge_rollups(rollup, channel.rollup)
        return [
            SupervisionTreeGroup(
                group_key=GROUP_NONE,
                label=tr("monitor_supervision_tree_all"),
                rollup=rollup,
                channels=sorted(flat_channels, key=lambda row: (row.frequency_mhz, row.label.casefold())),
            )
        ]

    buckets: Dict[str, List[SupervisionTreeChannel]] = {}

    for channel in flat_channels:
        item = find_equipo_in_list(normalized, channel.channel_key)
        if item is None:
            item = enrich_equipo_metadata({"channel_key": channel.channel_key})
        gkey = _group_key_for_item(item, group_mode)
        buckets.setdefault(gkey, []).append(channel)

    groups: List[SupervisionTreeGroup] = []
    for gkey in sorted(buckets.keys(), key=lambda value: group_label_for_key(group_mode, value, tr).casefold()):
        channels = sorted(buckets[gkey], key=lambda row: (row.frequency_mhz, row.label.casefold()))
        rollup = "ok"
        for channel in channels:
            if channel.enabled:
                rollup = merge_rollups(rollup, channel.rollup)
        label = group_label_for_key(group_mode, gkey, tr)
        groups.append(
            SupervisionTreeGroup(
                group_key=gkey,
                label=label,
                rollup=rollup,
                channels=channels,
            )
        )
    return groups
