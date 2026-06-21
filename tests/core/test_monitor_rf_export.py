"""Export RF — ganancias HackRF válidas sin recorte cruzado."""
from __future__ import annotations

from core.monitor.monitor_rf_limits import clamp_hackrf_rx_gains


def test_clamp_hackrf_high_sum_warns_not_clamps():
    lna, vga, amp, warn = clamp_hackrf_rx_gains(40, 62, True)
    assert lna == 40
    assert vga == 62
    assert amp is True
    assert warn == "monitor_rf_gain_high_sum"


def test_clamp_hackrf_valid_gain():
    lna, vga, amp, warn = clamp_hackrf_rx_gains(16, 20, False)
    assert lna == 16
    assert vga == 20
    assert amp is False
    assert warn is None
