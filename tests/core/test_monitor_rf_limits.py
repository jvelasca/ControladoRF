"""Límites de ganancia HackRF — delegación libhackrf nativa."""
from __future__ import annotations

from core.monitor.hackrf_rx_gains import snap_gains, calibrate_hackrf_antenna_power_db, HACKRF_ANTENNA_OFFSET_DB
from core.monitor.monitor_rf_limits import (
    clamp_hackrf_rx_gains,
    iq_rx_gain_compensation_db,
    max_lna_gain_db,
    max_vga_gain_db,
)


def test_snap_only_no_cross_clamp():
    lna, vga, amp, warn = clamp_hackrf_rx_gains(40, 62, False)
    assert lna == 40
    assert vga == 62
    assert amp is False
    assert warn == "monitor_rf_gain_high_sum"


def test_lna_change_preserves_vga():
    lna, vga, _, _ = clamp_hackrf_rx_gains(32, 34, False, changed="lna")
    assert lna == 32
    assert vga == 34


def test_vga_change_preserves_lna():
    lna, vga, _, _ = clamp_hackrf_rx_gains(24, 40, False, changed="vga")
    assert lna == 24
    assert vga == 40


def test_max_gains_are_libhackrf_limits():
    assert max_vga_gain_db(0, False) == 62
    assert max_lna_gain_db(0, False) == 40


def test_iq_rx_gain_compensation_uses_11db_amp():
    assert iq_rx_gain_compensation_db(lna_gain_db=16, vga_gain_db=20, rf_amp_enable=False) == 36.0
    assert iq_rx_gain_compensation_db(lna_gain_db=16, vga_gain_db=20, rf_amp_enable=True) == 47.0


def test_sdrpp_default_combo():
    g = snap_gains(24, 34, False)
    assert g.lna_db + g.vga_db == 58


def test_calibrate_hackrf_antenna_power_adds_offset_after_gain():
    raw = -50.0
    out = float(
        calibrate_hackrf_antenna_power_db(
            raw,
            lna_gain_db=16,
            vga_gain_db=20,
            rf_amp_enable=False,
        )
    )
    assert out == raw - 36.0 + HACKRF_ANTENNA_OFFSET_DB
