"""Ganancias RX HackRF — port greenfield desde legacy."""
from __future__ import annotations

from core.rf.types import RxGainConfig

# Reutiliza tabla probada hasta completar desacople del archive.
from core.monitor.hackrf_rx_gains import snap_gains as _legacy_snap


def snap_rx_gains(config: RxGainConfig) -> RxGainConfig:
    g = _legacy_snap(config.lna_db, config.vga_db, config.rf_amp_enable)
    return RxGainConfig(lna_db=g.lna_db, vga_db=g.vga_db, rf_amp_enable=g.amp_enable)
