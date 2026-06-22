"""Controles FC/F y SPAN para toolbar Monitor."""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMenu, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from core.monitor.display_scale import center_freq_step_hz
from core.monitor.monitor_mode_guard import ModeRestriction, span_mode_requires_analyzer_mode, span_requires_analyzer_mode
from core.monitor.monitor_mode_profile import ui_max_span_hz
from core.monitor.monitor_freq_span_logic import (
    display_span_hz,
    patch_center_freq,
    patch_freq_input_mode,
    patch_manual_span,
    patch_selected_freq,
    patch_span_mode,
    ui_span_min_hz,
)
from core.monitor.spectrum_params import SpectrumParams
from core.rf.channel_input import (
    format_channel_toolbar_title,
    step_channel_frequency,
)
from core.rf.channelization_service import ChannelizationService
from gui.monitor.monitor_channel_mode_button import MonitorChannelModeButton
from gui.monitor.monitor_freq_menu import populate_freq_menu
from gui.monitor.monitor_freq_mode_button import MonitorFreqModeButton
from gui.monitor.monitor_freq_readout_labels import freq_readout_toolbar_title
from gui.monitor.monitor_numeric_control import MonitorNumericControl
from i18n.json_translation import tr

SPAN_MODES = ("manual", "full", "zero", "last")
TOOLBAR_FREQ_MIN_WIDTH = 200
TOOLBAR_SPAN_MIN_WIDTH = 120


class MonitorFreqControl(MonitorNumericControl):
    """FC / F en MHz con menú contextual; en modo canal el identificador va en la etiqueta."""

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
        self._channelization_service: Optional[ChannelizationService] = None

        spin_idx = self._value_row.indexOf(self._spin)
        self._ch_arrows = QWidget(self)
        self._ch_arrows.setObjectName("MonitorChannelArrows")
        self._ch_arrows.setFixedWidth(18)
        arrows_layout = QVBoxLayout(self._ch_arrows)
        arrows_layout.setContentsMargins(0, 0, 0, 0)
        arrows_layout.setSpacing(0)
        self._ch_step_up = QToolButton(self._ch_arrows)
        self._ch_step_up.setObjectName("MonitorChannelStepUp")
        self._ch_step_up.setText("▲")
        self._ch_step_up.setFixedSize(18, 11)
        self._ch_step_up.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._ch_step_up.clicked.connect(lambda: self._step_frequency(1))
        self._ch_step_down = QToolButton(self._ch_arrows)
        self._ch_step_down.setObjectName("MonitorChannelStepDown")
        self._ch_step_down.setText("▼")
        self._ch_step_down.setFixedSize(18, 11)
        self._ch_step_down.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._ch_step_down.clicked.connect(lambda: self._step_frequency(-1))
        arrows_layout.addWidget(self._ch_step_up)
        arrows_layout.addWidget(self._ch_step_down)
        self._value_row.insertWidget(
            spin_idx + 1,
            self._ch_arrows,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )
        self._spin.setButtonSymbols(self._spin.ButtonSymbols.NoButtons)
        self.setMinimumWidth(TOOLBAR_FREQ_MIN_WIDTH if not compact else 188)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self._apply_tooltips()
        self._mode_btn = MonitorFreqModeButton(self)
        self._mode_btn.mode_changed.connect(self._on_mode_changed)
        self.insert_value_row_widget(self._mode_btn, before_menu=True)
        self._ch_btn = MonitorChannelModeButton(self)
        self._ch_btn.channel_mode_changed.connect(self._on_channel_mode_changed)
        self.insert_value_row_widget(self._ch_btn, before_menu=True)

    def set_channelization_service(self, service: Optional[ChannelizationService]) -> None:
        self._channelization_service = service
        enabled = service is not None
        self._ch_btn.setEnabled(enabled)
        self.set_params(self._params, force=True)

    def _uses_channel_input(self) -> bool:
        return (
            self._params.freq_input_mode == "channel"
            and self._channelization_service is not None
        )

    def _active_freq_hz(self) -> float:
        if self._params.freq_readout == "f":
            return float(self._params.selected_freq_hz)
        return float(self._params.center_freq_hz)

    def _freq_title(self, params: SpectrumParams) -> str:
        if (
            params.freq_input_mode == "channel"
            and self._channelization_service is not None
        ):
            return format_channel_toolbar_title(
                self._channelization_service, self._active_freq_hz()
            )
        return freq_readout_toolbar_title(params)

    def _on_mode_changed(self, mode: str) -> None:
        from core.monitor.monitor_freq_span_logic import patch_freq_readout

        self._emit_patch(patch_freq_readout(self._params, mode))

    def _on_channel_mode_changed(self, active: bool) -> None:
        mode = "channel" if active else "frequency"
        updated = patch_freq_input_mode(self._params, mode)
        if self._channelization_service is not None:
            state = self._channelization_service.get_state()
            state.input_mode = mode
            state.show_spectrum_allocations = active
            self._channelization_service.save_state(state)
        self._emit_patch(updated)

    def _step_frequency(self, direction: int) -> None:
        if direction == 0:
            return
        if self._uses_channel_input() and self._channelization_service:
            hz = step_channel_frequency(
                self._channelization_service,
                self._active_freq_hz(),
                direction,
            )
        else:
            step_hz = float(
                self._params.freq_step_hz
                or center_freq_step_hz(self._active_freq_hz())
            )
            hz = self._active_freq_hz() + float(direction) * step_hz
        self._apply_freq_hz(hz)

    def _sync_step_button_tooltips(self) -> None:
        if self._uses_channel_input():
            self._ch_step_up.setToolTip(tr("monitor_tip_channel_step_up"))
            self._ch_step_down.setToolTip(tr("monitor_tip_channel_step_down"))
        else:
            self._ch_step_up.setToolTip(tr("monitor_tip_freq_step_up"))
            self._ch_step_down.setToolTip(tr("monitor_tip_freq_step_down"))

    def bind_patch(self, callback: Callable[[SpectrumParams], None]) -> None:
        self._patch_callback = callback

    def recargar_textos(self) -> None:
        self.set_params(self._params)
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        if self._uses_channel_input():
            self.set_tooltips(tr("monitor_tip_channel_input"), tr("monitor_tip_fc_menu"))
            return
        if self._params.freq_readout == "f":
            tip = tr("monitor_tip_fc_f")
        else:
            tip = tr("monitor_tip_fc")
        self.set_tooltips(tip, tr("monitor_tip_fc_menu"))

    def set_params(self, params: SpectrumParams, *, force: bool = False) -> None:
        self._params = params.copy()
        if self.is_user_editing() and not force:
            return
        self._sync_step_button_tooltips()
        self.set_title(self._freq_title(params))
        self.set_readout_mode(params.freq_readout)
        if hasattr(self, "_mode_btn"):
            self._mode_btn.set_mode(params.freq_readout)
        if hasattr(self, "_ch_btn"):
            self._ch_btn.set_channel_mode(params.freq_input_mode == "channel")
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

    def set_read_only(self, read_only: bool, *, force: bool = False) -> None:
        super().set_read_only(read_only, force=force)
        self._spin.setButtonSymbols(self._spin.ButtonSymbols.NoButtons)

    def _sync_global_input_mode(self, mode: str, *, show_allocations: bool | None = None) -> None:
        if not self._channelization_service:
            return
        state = self._channelization_service.get_state()
        changed = False
        if state.input_mode != mode:
            state.input_mode = mode
            changed = True
        if show_allocations is not None and state.show_spectrum_allocations != show_allocations:
            state.show_spectrum_allocations = show_allocations
            changed = True
        if changed:
            self._channelization_service.save_state(state)

    def _emit_patch(self, updated: SpectrumParams) -> None:
        if updated.freq_input_mode != self._params.freq_input_mode:
            show_alloc = updated.freq_input_mode == "channel"
            self._sync_global_input_mode(updated.freq_input_mode, show_allocations=show_alloc)
        self._params = updated
        self.set_params(updated, force=True)
        if self._patch_callback:
            self._patch_callback(updated)

    def _apply_freq_hz(self, hz: float) -> None:
        hz = max(0.0, hz)
        if self._params.freq_readout == "f":
            updated = patch_selected_freq(self._params, hz)
        else:
            updated = patch_center_freq(self._params, hz)
        self._emit_patch(updated)

    def _on_spin_committed(self, value: float) -> None:
        if self._block_emit:
            return
        hz = max(0.0, value * 1_000_000.0)
        self._apply_freq_hz(hz)

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
        self.setMinimumWidth(TOOLBAR_SPAN_MIN_WIDTH if not compact else 108)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
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
        updated = patch_span_mode(self._params, mode)
        self._emit_patch(updated)

    def _build_menu(self, menu: QMenu) -> None:
        from gui.monitor.monitor_span_menu import populate_span_menu

        populate_span_menu(
            menu,
            self._params,
            patch=self._emit_patch,
            parent=self.window(),
            mode_warning=self._warn_mode_restriction,
        )

    def show_popup_menu(self, global_pos) -> None:
        menu = QMenu(self)
        self._build_menu(menu)
        menu.exec(global_pos)
