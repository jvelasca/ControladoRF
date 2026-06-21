"""Menú contextual compartido de entrada RF (toolbar, sliders, franja estado)."""
from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QMenu, QWidget

from core.monitor.monitor_freq_span_logic import patch_hackrf_amp, patch_hackrf_lna, patch_hackrf_vga
from core.monitor.spectrum_params import SpectrumParams
from i18n.json_translation import tr


def populate_rf_menu(
    menu: QMenu,
    params: SpectrumParams,
    *,
    patch: Callable[[SpectrumParams], None],
    parent: QWidget,
) -> None:
    def apply(updated: SpectrumParams) -> None:
        patch(updated)

    preamp = menu.addAction(tr("monitor_status_dialog_rf_preamp"))
    preamp.setCheckable(True)
    preamp.setChecked(params.rf_amp_enable)
    preamp.triggered.connect(
        lambda checked: apply(patch_hackrf_amp(params, enabled=bool(checked)))
    )

    lna_menu = menu.addMenu(tr("monitor_status_dialog_rf_lna"))
    for gain in (0, 8, 16, 24, 32, 40):
        act = lna_menu.addAction(f"{gain} dB")
        act.setCheckable(True)
        act.setChecked(int(params.lna_gain_db) == gain)
        act.triggered.connect(
            lambda _c=False, g=gain: apply(patch_hackrf_lna(params, g))
        )

    vga_menu = menu.addMenu(tr("monitor_status_dialog_rf_vga"))
    for gain in range(0, 64, 2):
        act = vga_menu.addAction(f"{gain} dB")
        act.setCheckable(True)
        act.setChecked(int(params.vga_gain_db) == gain)
        act.triggered.connect(
            lambda _c=False, g=gain: apply(patch_hackrf_vga(params, g))
        )

    _ = parent
