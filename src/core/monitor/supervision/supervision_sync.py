"""Sincroniza objetivos de supervisión con el inventario del proyecto."""
from __future__ import annotations

from typing import Dict, List

from core.inventory_channel import channel_key, equipos_from_project, normalize_equipo
from core.monitor.supervision.device_bandwidth_defaults import default_bandwidth_hz_for_equipo
from core.monitor.supervision.supervision_models import SupervisionState, SupervisionTarget


def sync_supervision_targets(project, state: SupervisionState) -> SupervisionState:
    """Añade canales nuevos (ON por defecto) y elimina claves obsoletas."""
    equipos = equipos_from_project(project) if project is not None else []
    by_key: Dict[str, SupervisionTarget] = {
        target.channel_key: target for target in state.targets if target.channel_key
    }
    synced: List[SupervisionTarget] = []
    for item in equipos:
        key = channel_key(item)
        if not key:
            continue
        existing = by_key.get(key)
        if existing is None:
            synced.append(
                SupervisionTarget(
                    channel_key=key,
                    enabled=True,
                    bandwidth_hz=default_bandwidth_hz_for_equipo(item),
                    bandwidth_source="device_type",
                )
            )
            continue
        target = SupervisionTarget(
            channel_key=key,
            enabled=existing.enabled,
            bandwidth_hz=existing.bandwidth_hz,
            bandwidth_source=existing.bandwidth_source,
            preset_id=existing.preset_id,
            check_overrides=dict(existing.check_overrides),
            threshold_mode=existing.threshold_mode,
            reference=existing.reference,
        )
        if target.bandwidth_source == "device_type":
            target.bandwidth_hz = default_bandwidth_hz_for_equipo(item)
        synced.append(target)
    state.targets = synced
    return state


def apply_equipo_bandwidth_defaults(state: SupervisionState, equipos: List[dict]) -> None:
    """Recalcula BW automático para targets con fuente ``device_type``."""
    by_key = {channel_key(normalize_equipo(item)): item for item in equipos}
    for target in state.targets:
        if target.bandwidth_source != "device_type":
            continue
        item = by_key.get(target.channel_key)
        if item is not None:
            target.bandwidth_hz = default_bandwidth_hz_for_equipo(item)
