"""Persistencia de supervisión en ``project.modules.monitor``."""
from __future__ import annotations

from typing import Any, Dict

from core.monitor.supervision.supervision_models import SupervisionState

SUPERVISION_MODULE_KEY = "supervision"


def default_supervision_state() -> SupervisionState:
    return SupervisionState()


def get_supervision_module(project) -> Dict[str, Any]:
    modules = getattr(project, "modules", None) or {}
    monitor = modules.setdefault("monitor", {})
    if not isinstance(monitor, dict):
        monitor = {}
        modules["monitor"] = monitor
    supervision = monitor.setdefault(SUPERVISION_MODULE_KEY, {})
    return supervision if isinstance(supervision, dict) else {}


def load_supervision(project) -> SupervisionState:
    if project is None:
        return default_supervision_state()
    raw = get_supervision_module(project)
    return SupervisionState.from_dict(raw)


def save_supervision(project, state: SupervisionState) -> None:
    module = get_supervision_module(project)
    module.clear()
    module.update(state.to_dict())
