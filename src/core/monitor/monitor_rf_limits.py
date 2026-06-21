"""Compatibilidad RX HackRF — delega en hackrf_rx_gains (libhackrf nativo)."""
from __future__ import annotations

from typing import Optional, Tuple

from core.monitor.hackrf_rx_gains import (
    HACKRF_AMP_NOMINAL_GAIN_DB,
    LNA_GAIN_MAX_DB,
    LNA_GAIN_STEPS_DB,
    VGA_GAIN_MAX_DB,
    VGA_GAIN_STEP_DB,
    gains_from_params,
    iq_rx_gain_compensation_db,
    snap_gains,
    snap_gains_for_source,
    snap_lna_db,
    snap_vga_db,
)

# Re-export para código legacy.
HACKRF_PREAMP_GAIN_DB = HACKRF_AMP_NOMINAL_GAIN_DB
HACKRF_MAX_LNA_VGA_SUM = LNA_GAIN_MAX_DB + VGA_GAIN_MAX_DB

snap_lna_gain_db = snap_lna_db
snap_vga_gain_db = snap_vga_db


def max_vga_gain_db(lna_gain_db: int, rf_amp_enable: bool) -> int:
    """Techo fijo libhackrf (independiente de LNA)."""
    _ = lna_gain_db, rf_amp_enable
    return VGA_GAIN_MAX_DB


def max_lna_gain_db(vga_gain_db: int, rf_amp_enable: bool) -> int:
    """Techo fijo libhackrf (independiente de VGA)."""
    _ = vga_gain_db, rf_amp_enable
    return LNA_GAIN_MAX_DB


def clamp_hackrf_rx_gains(
    lna_gain_db: int,
    vga_gain_db: int,
    rf_amp_enable: bool,
    *,
    changed: str | None = None,
) -> Tuple[int, int, bool, Optional[str]]:
    """Solo cuantiza pasos; no acopla LNA/VGA (semántica hackrf_transfer)."""
    _ = changed
    g = snap_gains(lna_gain_db, vga_gain_db, rf_amp_enable)
    from core.monitor.hackrf_rx_gains import high_gain_warning

    warn = high_gain_warning(g.lna_db, g.vga_db, g.amp_enable)
    return g.lna_db, g.vga_db, g.amp_enable, warn


def clamp_rf_gains_for_source(
    source_id: str,
    lna_gain_db: int,
    vga_gain_db: int,
    rf_amp_enable: bool,
    *,
    changed: str | None = None,
) -> Tuple[int, int, bool, Optional[str]]:
    _ = changed
    return snap_gains_for_source(source_id, lna_gain_db, vga_gain_db, rf_amp_enable)
