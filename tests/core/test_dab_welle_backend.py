"""Tests welle-cli backend (DAB+ audio externo)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.monitor.dab_welle_backend import (
    WelleCliProbe,
    format_welle_cli_command,
    launch_welle_cli,
    welle_dab_channel_label,
)


def test_welle_dab_channel_label_202928_mhz() -> None:
    label = welle_dab_channel_label(202_928_000.0)
    assert label
    assert label[0].isdigit()


def test_format_welle_cli_command_includes_channel_and_hackrf() -> None:
    probe = WelleCliProbe(available=True, executable="/usr/bin/welle-cli", message_key="monitor_dab_welle_ok")
    with patch("core.monitor.dab_welle_backend.probe_welle_cli", return_value=probe):
        cmd = format_welle_cli_command(202_928_000.0, executable="/usr/bin/welle-cli")
    assert "welle-cli" in cmd
    assert "hackrf" in cmd
    assert welle_dab_channel_label(202_928_000.0) in cmd


def test_launch_welle_cli_missing() -> None:
    probe = WelleCliProbe(available=False, executable=None, message_key="monitor_dab_welle_missing")
    with patch("core.monitor.dab_welle_backend.probe_welle_cli", return_value=probe):
        result = launch_welle_cli(202_928_000.0)
    assert not result.ok
    assert result.message_key == "monitor_dab_welle_missing"


def test_launch_welle_cli_ok() -> None:
    probe = WelleCliProbe(available=True, executable="/usr/bin/welle-cli", message_key="monitor_dab_welle_ok")
    popen = MagicMock()
    with patch("core.monitor.dab_welle_backend.probe_welle_cli", return_value=probe), patch(
        "core.monitor.dab_welle_backend.subprocess.Popen", popen
    ):
        result = launch_welle_cli(202_928_000.0, web_port=7970)
    assert result.ok
    assert result.channel == welle_dab_channel_label(202_928_000.0)
    assert result.web_url == "http://localhost:7970/"
    popen.assert_called_once()
