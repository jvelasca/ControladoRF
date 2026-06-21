"""Etiquetas de modo FC/F compartidas (toolbar, overlays, franja de estado)."""
from __future__ import annotations

from core.monitor.spectrum_params import SpectrumParams
from i18n.json_translation import tr


def freq_readout_toolbar_title(params: SpectrumParams) -> str:
    if params.freq_readout == "f":
        return tr("monitor_lcd_freq_marker")
    return tr("monitor_lcd_freq_center")


def freq_readout_status_badge(params: SpectrumParams) -> str:
    if params.freq_readout == "f":
        return tr("monitor_status_readout_f")
    return tr("monitor_status_readout_fc")


def freq_readout_mode_abbr(params: SpectrumParams) -> str:
    """Etiqueta corta FC/F para overlays compactos."""
    return "F" if params.freq_readout == "f" else "FC"


def freq_readout_overlay_label(params: SpectrumParams) -> str:
    return freq_readout_toolbar_title(params)
