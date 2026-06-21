"""Menú contextual compartido de frecuencias (toolbar, overlay, franja estado)."""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtWidgets import QInputDialog, QMenu, QWidget

from core.monitor.display_scale import center_freq_step_hz
from core.monitor.monitor_freq_span_logic import (
    STEP_PRESETS_HZ,
    active_freq_hz,
    patch_freq_offset,
    patch_freq_pan_mode,
    patch_freq_readout,
    patch_freq_start,
    patch_freq_step,
    patch_freq_stop,
    patch_freq_input_mode,
    patch_selected_freq,
    patch_center_freq,
)
from core.monitor.spectrum_params import SpectrumParams
from i18n.json_translation import tr


def populate_freq_menu(
    menu: QMenu,
    params: SpectrumParams,
    *,
    patch: Callable[[SpectrumParams], None],
    parent: Optional[QWidget] = None,
) -> None:
    """Menú … frecuencia — mismo contenido en toolbar, overlay y badge FC/F."""

    def apply(updated: SpectrumParams) -> None:
        patch(updated)

    for mode, key in (("fc", "monitor_freq_menu_show_fc"), ("f", "monitor_freq_menu_show_f")):
        act = menu.addAction(tr(key))
        act.setCheckable(True)
        act.setChecked(params.freq_readout == mode)
        act.triggered.connect(lambda _c=False, m=mode: apply(patch_freq_readout(params, m)))

    menu.addSeparator()
    step_menu = menu.addMenu(tr("monitor_freq_menu_step"))
    for hz in STEP_PRESETS_HZ:
        label = f"{hz / 1000:.1f} kHz" if hz < 1_000_000 else f"{hz / 1_000_000:.1f} MHz"
        act = step_menu.addAction(label)
        act.setCheckable(True)
        act.setChecked(abs((params.freq_step_hz or 0) - hz) < 1.0)
        act.triggered.connect(lambda _c=False, s=hz: apply(patch_freq_step(params, s)))

    pan_menu = menu.addMenu(tr("monitor_freq_menu_pan_mode"))
    for mode_id, key in (("center_fixed", "center_fixed"), ("pan_spectrum", "pan_spectrum")):
        act = pan_menu.addAction(tr(f"monitor_freq_pan_{key}"))
        act.setCheckable(True)
        act.setChecked(params.freq_pan_mode == mode_id)
        act.triggered.connect(lambda _c=False, m=mode_id: apply(patch_freq_pan_mode(params, m)))

    menu.addSeparator()
    menu.addAction(
        tr("monitor_marker_config_title"),
        lambda: _open_marker_config_dialog(params, patch, parent),
    )
    menu.addSeparator()
    menu.addAction(tr("monitor_freq_menu_edit_mhz"), lambda: _edit_mhz_dialog(params, patch, parent))
    menu.addAction(
        tr("monitor_freq_menu_set_start"),
        lambda: apply(patch_freq_start(params, active_freq_hz(params))),
    )
    menu.addAction(
        tr("monitor_freq_menu_set_stop"),
        lambda: apply(patch_freq_stop(params, active_freq_hz(params))),
    )
    menu.addAction(tr("monitor_freq_menu_offset"), lambda: _edit_offset_dialog(params, patch, parent))

    input_menu = menu.addMenu(tr("monitor_freq_menu_input_mode"))
    for mode_id, key in (("frequency", "monitor_freq_menu_input_freq"), ("channel", "monitor_freq_menu_input_channel")):
        act = input_menu.addAction(tr(key))
        act.setCheckable(True)
        act.setChecked(params.freq_input_mode == mode_id)
        act.triggered.connect(lambda _c=False, m=mode_id: apply(patch_freq_input_mode(params, m)))


def _open_marker_config_dialog(
    params: SpectrumParams,
    patch: Callable[[SpectrumParams], None],
    parent: Optional[QWidget],
) -> None:
    from gui.monitor.monitor_marker_config_dialog import edit_marker_display_dialog

    updated = edit_marker_display_dialog(params, parent=parent)
    if updated is not None:
        patch(updated)


def _edit_mhz_dialog(
    params: SpectrumParams,
    patch: Callable[[SpectrumParams], None],
    parent: Optional[QWidget],
) -> None:
    mhz = active_freq_hz(params) / 1_000_000.0
    value, ok = QInputDialog.getDouble(
        parent,
        tr("monitor_freq_menu_edit_mhz"),
        tr("monitor_freq_mhz_prompt"),
        mhz,
        0.0,
        6000.0,
        6,
    )
    if not ok:
        return
    hz = value * 1_000_000.0
    if params.freq_readout == "f":
        patch(patch_selected_freq(params, hz))
    else:
        patch(patch_center_freq(params, hz))


def _edit_offset_dialog(
    params: SpectrumParams,
    patch: Callable[[SpectrumParams], None],
    parent: Optional[QWidget],
) -> None:
    current_khz = params.freq_offset_hz / 1000.0
    value, ok = QInputDialog.getDouble(
        parent,
        tr("monitor_freq_menu_offset"),
        tr("monitor_freq_offset_prompt"),
        current_khz,
        -100000.0,
        100000.0,
        3,
    )
    if ok:
        patch(patch_freq_offset(params, value * 1000.0))
