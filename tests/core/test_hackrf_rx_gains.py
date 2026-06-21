"""Ganancias RX HackRF — libhackrf / hackrf_transfer."""
from __future__ import annotations

from core.monitor.hackrf_rx_gains import (
    HACKRF_AMP_NOMINAL_GAIN_DB,
    snap_gains,
    snap_lna_db,
    snap_vga_db,
)
from core.monitor.monitor_freq_span_logic import patch_hackrf_lna, patch_hackrf_vga
from core.monitor.spectrum_params import SpectrumParams


def test_snap_lna_steps():
    assert snap_lna_db(0) == 0
    assert snap_lna_db(7) == 8
    assert snap_lna_db(24) == 24
    assert snap_lna_db(41) == 40


def test_snap_vga_steps():
    assert snap_vga_db(0) == 0
    assert snap_vga_db(33) == 32
    assert snap_vga_db(34) == 34
    assert snap_vga_db(63) == 62


def test_gains_are_independent():
    g = snap_gains(24, 34, False)
    assert g.lna_db == 24
    assert g.vga_db == 34
    g2 = snap_gains(40, 62, True)
    assert g2.lna_db == 40
    assert g2.vga_db == 62
    assert g2.amp_enable is True


def test_nominal_gain_includes_amp():
    g = snap_gains(16, 20, True)
    assert g.nominal_gain_db() == 16 + 20 + HACKRF_AMP_NOMINAL_GAIN_DB


def test_patch_lna_does_not_change_vga():
    base = SpectrumParams(lna_gain_db=16, vga_gain_db=34)
    updated = patch_hackrf_lna(base, 32)
    assert updated.lna_gain_db == 32
    assert updated.vga_gain_db == 34


def test_patch_vga_does_not_change_lna():
    base = SpectrumParams(lna_gain_db=24, vga_gain_db=16)
    updated = patch_hackrf_vga(base, 40)
    assert updated.lna_gain_db == 24
    assert updated.vga_gain_db == 40


def test_transfer_args_match_hackrf_transfer():
    g = snap_gains(24, 34, False)
    assert g.transfer_args() == {
        "lna_gain": 24,
        "vga_gain": 34,
        "rf_amp_enable": False,
    }
