"""Controles FC/F y SPAN para toolbar Monitor."""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtWidgets import QMenu, QWidget

from core.monitor.display_scale import center_freq_step_hz
from core.monitor.monitor_mode_guard import ModeRestriction, span_mode_requires_analyzer_mode, span_requires_analyzer_mode
from core.monitor.monitor_mode_profile import ui_max_span_hz
from core.monitor.monitor_freq_span_logic import (
    display_span_hz,
    patch_center_freq,
    patch_manual_span,
    patch_selected_freq,
    patch_span_mode,
    ui_span_min_hz,
)
from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_freq_menu import populate_freq_menu
from gui.monitor.monitor_freq_mode_button import MonitorFreqModeButton
from gui.monitor.monitor_freq_readout_labels import freq_readout_toolbar_title
from gui.monitor.monitor_numeric_control import MonitorNumericControl
from i18n.json_translation import tr

SPAN_MODES = ("manual", "full", "zero", "last")


class MonitorFreqControl(MonitorNumericControl):
    """FC / F en MHz con menú contextual."""

    def __init__(self, *, compact: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            "FC",
            suffix=" MHz",
            decimals=6,
            minimum=0.0,
            maximum=6000.0,
            step=0.1,
            menu_builder=self._build_menu,
            compact=compact,
            parent=parent,
        )
        self._params = SpectrumParams()
        self._patch_callback: Optional[Callable[[SpectrumParams], None]] = None
        self._apply_tooltips()
        self._mode_btn = MonitorFreqModeButton(self)
        self._mode_btn.mode_changed.connect(self._on_mode_changed)
        self.insert_value_row_widget(self._mode_btn, before_menu=True)

    def _on_mode_changed(self, mode: str) -> None:
        from core.monitor.monitor_freq_span_logic import patch_freq_readout

        self._emit_patch(patch_freq_readout(self._params, mode))

    def bind_patch(self, callback: Callable[[SpectrumParams], None]) -> None:
        self._patch_callback = callback

    def recargar_textos(self) -> None:
        self.set_params(self._params)
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        if self._params.freq_readout == "f":
            tip = tr("monitor_tip_fc_f")
        else:
            tip = tr("monitor_tip_fc")
        self.set_tooltips(tip, tr("monitor_tip_fc_menu"))

    def set_params(self, params: SpectrumParams, *, force: bool = False) -> None:
        self._params = params.copy()
        if self.is_user_editing() and not force:
            return
        self.set_title(freq_readout_toolbar_title(params))
        self.set_readout_mode(params.freq_readout)
        if hasattr(self, "_mode_btn"):
            self._mode_btn.set_mode(params.freq_readout)
        step_mhz = max(
            (params.freq_step_hz or center_freq_step_hz(params.center_freq_hz)) / 1_000_000.0,
            0.000001,
        )
        self.set_step(step_mhz)
        self.set_read_only(False)
        mhz = (
            params.selected_freq_hz / 1_000_000.0
            if params.freq_readout == "f"
            else params.center_freq_hz / 1_000_000.0
        )
        self.set_value(mhz, force=force)
        self._apply_tooltips()

    def _emit_patch(self, updated: SpectrumParams) -> None:
        self._params = updated
        self.set_params(updated, force=True)
        if self._patch_callback:
            self._patch_callback(updated)

    def _on_spin_committed(self, value: float) -> None:
        if self._block_emit:
            return
        hz = max(0.0, value * 1_000_000.0)
        if self._params.freq_readout == "f":
            updated = patch_selected_freq(self._params, hz)
        else:
            updated = patch_center_freq(self._params, hz)
        self._emit_patch(updated)

    def _build_menu(self, menu: QMenu) -> None:
        populate_freq_menu(menu, self._params, patch=self._emit_patch, parent=self)

    def show_popup_menu(self, global_pos) -> None:
        menu = QMenu(self)
        self._build_menu(menu)
        menu.exec(global_pos)


class MonitorSpanControl(MonitorNumericControl):
    """SPAN en MHz — lapso manual / completo / cero / último."""

    def __init__(self, *, compact: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            tr("monitor_lcd_span"),
            suffix=" MHz",
            decimals=3,
            minimum=0.0,
            maximum=20.0,
            step=1.0,
            menu_builder=self._build_menu,
            compact=compact,
            parent=parent,
        )
        self._params = SpectrumParams()
        self._patch_callback: Optional[Callable[[SpectrumParams], None]] = None
        self._mode_warning_callback: Optional[Callable[[ModeRestriction], None]] = None
        self._apply_tooltips()

    def bind_patch(self, callback: Callable[[SpectrumParams], None]) -> None:
        self._patch_callback = callback

    def bind_mode_warning(self, callback: Callable[[ModeRestriction], None]) -> None:
        self._mode_warning_callback = callback

    def recargar_textos(self) -> None:
        from core.monitor.iq_sdr_profile import uses_iq_sdr_profile

        self.set_title(
            tr("monitor_lcd_bandwidth")
            if uses_iq_sdr_profile(self._params)
            else tr("monitor_lcd_span")
        )
        self.set_params(self._params)
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        self.set_tooltips(tr("monitor_tip_span"), tr("monitor_tip_span_menu"))

    def set_params(self, params: SpectrumParams, *, force: bool = False) -> None:
        self._params = params.copy()
        if self.is_user_editing() and not force:
            return
        from core.monitor.iq_sdr_profile import uses_iq_sdr_profile

        if uses_iq_sdr_profile(params):
            self.set_title(tr("monitor_lcd_bandwidth"))
            self.set_tooltips(tr("monitor_tip_span_iq_sr"), tr("monitor_tip_span_menu"))
        else:
            self.set_title(tr("monitor_lcd_span"))
            self._apply_tooltips()
        min_mhz = max(0.0001, ui_span_min_hz(params) / 1_000_000.0)
        max_mhz = max(min_mhz, ui_max_span_hz(params) / 1_000_000.0)
        self.set_minimum(min_mhz)
        self.set_maximum(max_mhz)
        self.set_read_only(False)
        span_hz = display_span_hz(params)
        self.set_value(max(0.0, span_hz / 1_000_000.0), force=force)

    def _emit_patch(self, updated: SpectrumParams) -> None:
        self._params = updated
        self.set_params(updated, force=True)
        if self._patch_callback:
            self._patch_callback(updated)

    def _warn_mode_restriction(self, restriction: ModeRestriction | None) -> None:
        if restriction is not None and self._mode_warning_callback is not None:
            self._mode_warning_callback(restriction)

    def _on_spin_committed(self, value: float) -> None:
        if self._block_emit:
            return
        requested_hz = value * 1_000_000.0
        self._warn_mode_restriction(span_requires_analyzer_mode(self._params, requested_hz))
        updated = patch_manual_span(self._params, requested_hz)
        self._emit_patch(updated)

    def _set_span_mode(self, mode: str) -> None:
        self._warn_mode_restriction(span_mode_requires_analyzer_mode(self._params, mode))
        self._emit_patch(patch_span_mode(self._params, mode))

    def _build_menu(self, menu: QMenu) -> None:
        for mode in SPAN_MODES:
            act = menu.addAction(tr(f"monitor_span_mode_{mode}"))
            act.setCheckable(True)
            act.setChecked(self._params.span_mode == mode)
            act.triggered.connect(lambda _c=False, m=mode: self._set_span_mode(m))

    def show_popup_menu(self, global_pos) -> None:
        menu = QMenu(self)
        self._build_menu(menu)
        menu.exec(global_pos)
