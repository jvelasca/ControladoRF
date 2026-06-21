"""Tests del modo desarrollador."""
from core.developer_mode import (
    CONFIG_KEY,
    is_developer_mode,
    read_developer_mode,
    verify_developer_password,
    write_developer_mode,
)


def test_verify_developer_password():
    assert verify_developer_password("1493") is True
    assert verify_developer_password("wrong") is False


def test_developer_mode_persistence():
    stored: dict = {}

    def get_config():
        return dict(stored)

    def set_config(config):
        stored.clear()
        stored.update(config)

    assert read_developer_mode(get_config) is False
    write_developer_mode(get_config, set_config, True)
    assert read_developer_mode(get_config) is True
    assert stored[CONFIG_KEY] is True
    write_developer_mode(get_config, set_config, False)
    assert read_developer_mode(get_config) is False
    assert CONFIG_KEY not in stored


def test_is_developer_mode():
    assert is_developer_mode({}) is False
    assert is_developer_mode({"developer_mode": True}) is True


def test_read_developer_mode_accepts_config_dict():
    assert read_developer_mode({}) is False
    assert read_developer_mode({"developer_mode": True}) is True
