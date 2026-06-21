"""Modo desarrollador (acceso administrador) persistido en configuración global."""
from __future__ import annotations

from typing import Any, Callable, Dict, Union

CONFIG_KEY = "developer_mode"

# Contraseña local de desarrollo; no se persiste en disco.
_DEVELOPER_PASSWORD = "1493"

ConfigSource = Union[Callable[[], Dict[str, Any]], Dict[str, Any]]


def _resolve_config(store_get_config: ConfigSource) -> Dict[str, Any]:
    if callable(store_get_config):
        return dict(store_get_config() or {})
    if isinstance(store_get_config, dict):
        return dict(store_get_config)
    return {}


def is_developer_mode(config: Dict[str, Any] | None) -> bool:
    if not config:
        return False
    return bool(config.get(CONFIG_KEY))


def verify_developer_password(password: str) -> bool:
    return password == _DEVELOPER_PASSWORD


def read_developer_mode(store_get_config: ConfigSource) -> bool:
    return is_developer_mode(_resolve_config(store_get_config))


def write_developer_mode(
    store_get_config: ConfigSource,
    store_set_config: Callable[[Dict[str, Any]], None],
    enabled: bool,
) -> None:
    config = _resolve_config(store_get_config)
    if enabled:
        config[CONFIG_KEY] = True
    else:
        config.pop(CONFIG_KEY, None)
    store_set_config(config)
