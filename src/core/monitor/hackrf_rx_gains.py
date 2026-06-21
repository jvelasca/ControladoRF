"""Ganancias RX HackRF — semántica libhackrf / hackrf_transfer (1:1 con SDR++).

Referencia: https://hackrf.readthedocs.io/en/latest/setting_gain.html
- RF amp (``-a``): 0 o ~11 dB (on/off)
- IF / LNA (``-l``): 0–40 dB, pasos de 8 dB
- BB / VGA (``-g``): 0–62 dB, pasos de 2 dB

Cada control es independiente en libhackrf (sin límite LNA+VGA).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from core.monitor.spectrum_params import SpectrumParams

LNA_GAIN_STEPS_DB: tuple[int, ...] = (0, 8, 16, 24, 32, 40)
LNA_GAIN_MIN_DB = 0
LNA_GAIN_MAX_DB = 40
VGA_GAIN_MIN_DB = 0
VGA_GAIN_MAX_DB = 62
VGA_GAIN_STEP_DB = 2
# Doc oficial: ~11 dB nominal (no 14 dB).
HACKRF_AMP_NOMINAL_GAIN_DB = 11.0
# Offset empírico FFT/barrido → dBm referidos a antena (alineado con GQRX / SDR++).
HACKRF_ANTENNA_OFFSET_DB = 32.0
# Aviso informativo si la suma IF+BB es muy alta (saturación posible, no bloqueo).
HACKRF_RX_SUM_WARN_DB = 90


@dataclass(frozen=True)
class HackRfRxGains:
    lna_db: int
    vga_db: int
    amp_enable: bool

    def nominal_gain_db(self) -> float:
        gain = float(self.lna_db) + float(self.vga_db)
        if self.amp_enable:
            gain += HACKRF_AMP_NOMINAL_GAIN_DB
        return gain

    def transfer_args(self) -> dict[str, int | bool]:
        """Argumentos equivalentes a hackrf_transfer -l -g -a."""
        return {
            "lna_gain": self.lna_db,
            "vga_gain": self.vga_db,
            "rf_amp_enable": self.amp_enable,
        }


def snap_lna_db(value: int) -> int:
    """IF gain — redondeo al paso de 8 dB más cercano (libhackrf: value &= ~0x07)."""
    v = max(LNA_GAIN_MIN_DB, min(LNA_GAIN_MAX_DB, int(value)))
    return min(LNA_GAIN_STEPS_DB, key=lambda s: abs(s - v))


def snap_vga_db(value: int) -> int:
    """BB gain — redondeo hacia abajo a par (libhackrf: value &= ~0x01)."""
    v = max(VGA_GAIN_MIN_DB, min(VGA_GAIN_MAX_DB, int(value)))
    return v - (v % VGA_GAIN_STEP_DB)


def snap_gains(
    lna_gain_db: int,
    vga_gain_db: int,
    rf_amp_enable: bool,
) -> HackRfRxGains:
    """Cuantiza cada control sin modificar los demás."""
    return HackRfRxGains(
        lna_db=snap_lna_db(lna_gain_db),
        vga_db=snap_vga_db(vga_gain_db),
        amp_enable=bool(rf_amp_enable),
    )


def gains_from_params(params: SpectrumParams) -> HackRfRxGains:
    return snap_gains(params.lna_gain_db, params.vga_gain_db, params.rf_amp_enable)


def apply_gains_to_params(params: SpectrumParams, gains: HackRfRxGains) -> None:
    params.lna_gain_db = gains.lna_db
    params.vga_gain_db = gains.vga_db
    params.rf_amp_enable = gains.amp_enable


def snap_hackrf_params(params: SpectrumParams) -> SpectrumParams:
    """Copia params con LNA/VGA/P cuantizados (independientes)."""
    updated = params.copy()
    apply_gains_to_params(updated, gains_from_params(updated))
    return updated


def iq_rx_gain_compensation_db(
    *,
    lna_gain_db: int,
    vga_gain_db: int,
    rf_amp_enable: bool,
) -> float:
    """Ganancia RX nominal para referir el espectro a la entrada de antena."""
    return snap_gains(lna_gain_db, vga_gain_db, rf_amp_enable).nominal_gain_db()


def calibrate_hackrf_antenna_power_db(
    power_db,
    *,
    lna_gain_db: int,
    vga_gain_db: int,
    rf_amp_enable: bool,
):
    """Resta ganancia RX y aplica offset de antena (IQ y barrido usan la misma cadena)."""
    import numpy as np

    comp = iq_rx_gain_compensation_db(
        lna_gain_db=lna_gain_db,
        vga_gain_db=vga_gain_db,
        rf_amp_enable=rf_amp_enable,
    )
    return np.asarray(power_db, dtype=float) - comp + HACKRF_ANTENNA_OFFSET_DB


def high_gain_warning(
    lna_gain_db: int,
    vga_gain_db: int,
    rf_amp_enable: bool,
) -> str | None:
    """Aviso opcional (no bloquea) si IF+BB es muy alto."""
    g = snap_gains(lna_gain_db, vga_gain_db, rf_amp_enable)
    if g.lna_db + g.vga_db >= HACKRF_RX_SUM_WARN_DB:
        return "monitor_rf_gain_high_sum"
    return None


def _is_hackrf_source(source_id: str) -> bool:
    if not source_id:
        return False
    if source_id.startswith("hackrf"):
        return True
    return source_id.split("_")[0] == "hackrf"


def snap_gains_for_source(
    source_id: str,
    lna_gain_db: int,
    vga_gain_db: int,
    rf_amp_enable: bool,
) -> Tuple[int, int, bool, str | None]:
    """Snap por fuente; devuelve aviso informativo (nunca recorta el otro control)."""
    if not _is_hackrf_source(source_id):
        return int(lna_gain_db), int(vga_gain_db), bool(rf_amp_enable), None
    g = snap_gains(lna_gain_db, vga_gain_db, rf_amp_enable)
    return g.lna_db, g.vga_db, g.amp_enable, high_gain_warning(g.lna_db, g.vga_db, g.amp_enable)
