"""Controles resolución / suavizado / barrido — toolbar Monitor."""
from __future__ import annotations

import math
from typing import Callable, Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMenu, QWidget

from core.monitor.monitor_bw_profile import (
    fft_resolution_auto,
    resolution_menu_tip_key,
    resolution_tip_key,
    resolution_title_key,
    smoothing_menu_tip_key,
    smoothing_tip_key,
    smoothing_title_key,
    trace_smoothing_bins,
    uses_iq_resolution,
)
from core.monitor.monitor_bw_sweep_logic import (
    effective_sweep_time_ms,
    patch_rbw_hz,
    patch_smooth_bins,
    patch_sweep_time_ms,
)
from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_bw_menus import (
    populate_sweep_menu,
    populate_vbw_menu,
)
from gui.monitor.monitor_bw_spin_utils import safe_spin_restore, safe_spin_update
from gui.monitor.monitor_numeric_control import MonitorNumericControl
from i18n.json_translation import tr


class _MonitorBwControlBase(MonitorNumericControl):
    def __init__(
        self,
        title: str,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            title,
            suffix="",
            decimals=3,
            minimum=0.0,
            maximum=1000.0,
            step=1.0,
            menu_builder=self._build_menu,
            compact=True,
            parent=parent,
        )
        self._params = SpectrumParams()
        self._patch_callback: Optional[Callable[[SpectrumParams], None]] = None

    def bind_patch(self, callback: Callable[[SpectrumParams], None]) -> None:
        self._patch_callback = callback

    def _emit_patch(self, updated: SpectrumParams) -> None:
        snapshot = updated.copy()

        def _apply() -> None:
            self._params = snapshot.copy()
            self.set_params(self._params, force=True)
            if self._patch_callback:
                self._patch_callback(self._params)

        QTimer.singleShot(0, _apply)

    def _prepare_spin_refresh(self, *, force: bool = False) -> None:
        safe_spin_update(self, force=force)

    def _finish_spin_refresh(self) -> None:
        safe_spin_restore(self)

    def _spin_value_to_hz(self, value: float) -> float:
        suffix = self._spin.suffix().strip().lower()
        for noise in ("auto", "automático", "off"):
            suffix = suffix.replace(noise, "")
        suffix = suffix.strip()
        if suffix.startswith("mhz") or (suffix.startswith("m") and "hz" not in suffix[1:3]):
            return value * 1_000_000.0
        if suffix.startswith("khz") or suffix.startswith("k"):
            return value * 1_000.0
        return value

    def _apply_auto_bw_display(
        self,
        hz: float,
        auto_short_key: str,
        *,
        force: bool = False,
    ) -> None:
        self.set_read_only(True, force=force)
        self._apply_bw_spin(hz, force=force)
        unit = self._spin.suffix().strip()
        self._spin.setSuffix(f" {unit} {tr(auto_short_key)}")

    def _apply_auto_ms_display(
        self,
        ms: float,
        auto_short_key: str,
        *,
        force: bool = False,
    ) -> None:
        self.set_read_only(True, force=force)
        self.set_maximum(999_999.0, force=force)
        self.set_minimum(0.001, force=force)
        self._spin.setSuffix(f" ms {tr(auto_short_key)}")
        self.set_value(ms, force=force)

    def _apply_bw_spin(self, hz: float, *, force: bool = False) -> None:
        hz = max(1.0, float(hz))
        if not math.isfinite(hz):
            return
        if hz >= 1_000_000:
            self.set_maximum(9_999.0, force=force)
            self.set_minimum(0.001, force=force)
            self._spin.setSuffix(" MHz")
            self.set_value(hz / 1_000_000.0, force=force)
        elif hz >= 1_000:
            self.set_maximum(999_999.0, force=force)
            self.set_minimum(0.001, force=force)
            self._spin.setSuffix(" kHz")
            self.set_value(hz / 1_000.0, force=force)
        else:
            self.set_maximum(999_999.0, force=force)
            self.set_minimum(0.001, force=force)
            self._spin.setSuffix(" Hz")
            self.set_value(hz, force=force)

    def _build_menu(self, menu: QMenu) -> None:
        pass


class MonitorFftControl(_MonitorBwControlBase):
    """Tamaño FFT — siempre visible en analizador."""

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(tr("monitor_lcd_fft"), parent=parent)
        self._apply_tooltips()

    def recargar_textos(self) -> None:
        self.set_title(tr("monitor_lcd_fft"))
        self.set_params(self._params)
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        self.set_tooltips(tr("monitor_tip_fft"), tr("monitor_tip_fft_menu"))

    def set_params(self, params: SpectrumParams, *, force: bool = False) -> None:
        from core.monitor.monitor_operating_mode import MonitorOperatingMode

        self._params = params.copy()
        analyzer = params.operating_mode_enum() is MonitorOperatingMode.SPECTRUM
        self.setVisible(analyzer and uses_iq_resolution(params))
        self.set_title(tr("monitor_lcd_fft"))
        if self.is_user_editing() and not force:
            return
        self._prepare_spin_refresh(force=force)
        try:
            if fft_resolution_auto(params):
                self.set_read_only(True, force=force)
                self._spin.setDecimals(0)
                self._spin.setSuffix(f" {tr('monitor_lcd_fft_pts')} {tr('monitor_lcd_auto_suffix')}")
                self.set_value(float(params.fft_size), force=force)
                self.set_value_mode("auto")
            else:
                self.set_read_only(False, force=force)
                self.set_maximum(8192.0, force=force)
                self.set_minimum(256.0, force=force)
                self._spin.setDecimals(0)
                self._spin.setSuffix(f" {tr('monitor_lcd_fft_pts')}")
                self.set_value(float(params.fft_size), force=force)
                self.set_value_mode("manual")
        finally:
            self._finish_spin_refresh()
        self._apply_tooltips()

    def _on_spin_committed(self, value: float) -> None:
        if self._block_emit or fft_resolution_auto(self._params):
            return
        from core.monitor.monitor_bw_sweep_logic import patch_fft_size

        self._emit_patch(patch_fft_size(self._params, int(value)))

    def _build_menu(self, menu: QMenu) -> None:
        from gui.monitor.monitor_bw_menus import populate_fft_menu

        populate_fft_menu(menu, lambda: self._params, self._emit_patch, parent=self.window())


class MonitorRbwControl(_MonitorBwControlBase):
    """RBW efectivo — barrido HackRF; en IQ es SR/FFT (derivado)."""

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(tr("monitor_lcd_rbw"), parent=parent)
        self._apply_tooltips()

    def recargar_textos(self) -> None:
        self.set_title(tr(resolution_title_key(self._params)))
        self.set_params(self._params)
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        self.set_tooltips(
            tr(resolution_tip_key(self._params)),
            tr(resolution_menu_tip_key(self._params)),
        )

    def _rbw_is_auto(self, params: SpectrumParams) -> bool:
        if params.capture_mode == "iq":
            return bool(params.fft_auto)
        return bool(params.rbw_auto)

    def _refresh_rbw_readout(self, params: SpectrumParams, *, force: bool = False) -> None:
        if self._rbw_is_auto(params):
            self._spin.setDecimals(3)
            rbw = params.effective_rbw_hz()
            self._apply_auto_bw_display(rbw, "monitor_lcd_rbw_auto_short", force=force)
            self.set_value_mode("auto")
        else:
            self._spin.setDecimals(3)
            self.set_read_only(False, force=force)
            self._apply_bw_spin(params.effective_rbw_hz(), force=force)
            self.set_value_mode("manual")

    def set_params(self, params: SpectrumParams, *, force: bool = False) -> None:
        from core.monitor.monitor_operating_mode import MonitorOperatingMode

        self._params = params.copy()
        analyzer = params.operating_mode_enum() is MonitorOperatingMode.SPECTRUM
        self.setVisible(analyzer)
        self.setEnabled(True)
        self.set_title(tr(resolution_title_key(params)))
        if self.is_user_editing() and not force:
            return
        self._prepare_spin_refresh(force=force)
        try:
            self._refresh_rbw_readout(params, force=force)
        finally:
            self._finish_spin_refresh()
        self._apply_tooltips()

    def _on_spin_committed(self, value: float) -> None:
        if self._block_emit:
            return
        if self._params.capture_mode not in ("sweep", "iq"):
            return
        hz = self._spin_value_to_hz(value)
        self._emit_patch(patch_rbw_hz(self._params, hz))

    def _build_menu(self, menu: QMenu) -> None:
        from gui.monitor.monitor_bw_menus import populate_rbw_menu

        populate_rbw_menu(menu, lambda: self._params, self._emit_patch, parent=self.window())


class MonitorVbwControl(_MonitorBwControlBase):
    """Suavizado de traza (independiente de la resolución)."""

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(tr("monitor_lcd_smooth"), parent=parent)
        self._apply_tooltips()

    def recargar_textos(self) -> None:
        self.set_title(tr(smoothing_title_key(self._params)))
        self.set_params(self._params)
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        self.set_tooltips(
            tr(smoothing_tip_key(self._params)),
            tr(smoothing_menu_tip_key(self._params)),
        )

    def set_params(self, params: SpectrumParams, *, force: bool = False) -> None:
        self._params = params.copy()
        self.set_title(tr(smoothing_title_key(params)))
        if self.is_user_editing() and not force:
            return
        self._prepare_spin_refresh(force=force)
        try:
            self._spin.setDecimals(0)
            if params.trace_smooth_auto:
                self.set_read_only(True, force=force)
                self.set_maximum(1.0, force=force)
                self.set_minimum(0.0, force=force)
                self._spin.setPrefix("")
                self._spin.setSuffix("")
                self._spin.setSpecialValueText(tr("monitor_lcd_smooth_off"))
                self.set_value(0.0, force=force)
                self.set_value_mode("auto")
            else:
                self._spin.setPrefix("")
                self._spin.setSpecialValueText("")
                bins = trace_smoothing_bins(params)
                self.set_read_only(False, force=force)
                self.set_maximum(999.0, force=force)
                self.set_minimum(1.0, force=force)
                self._spin.setSuffix(f" {tr('monitor_lcd_smooth_bins')}")
                self.set_value(float(max(1, bins)), force=force)
                self.set_value_mode("manual")
        finally:
            self._finish_spin_refresh()
        self._apply_tooltips()

    def _on_spin_committed(self, value: float) -> None:
        if self._block_emit or self._params.trace_smooth_auto:
            return
        self._emit_patch(patch_smooth_bins(self._params, max(1, int(round(value)))))

    def _build_menu(self, menu: QMenu) -> None:
        populate_vbw_menu(menu, lambda: self._params, self._emit_patch)


class MonitorSweepControl(_MonitorBwControlBase):
    _PLACEHOLDER_MIN_WIDTH = 72

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(tr("monitor_lcd_swt"), parent=parent)
        self.setMinimumWidth(self._PLACEHOLDER_MIN_WIDTH)
        self._apply_tooltips()

    def recargar_textos(self) -> None:
        self.set_title(tr("monitor_lcd_swt"))
        self.set_params(self._params)
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        if self._params.capture_mode == "sweep":
            self.set_tooltips(tr("monitor_tip_sweep"), tr("monitor_tip_sweep_menu"))
        else:
            self.set_tooltips(tr("monitor_tip_sweep_iq"), tr("monitor_tip_sweep_menu"))

    def set_params(self, params: SpectrumParams, *, force: bool = False) -> None:
        from core.monitor.monitor_operating_mode import MonitorOperatingMode

        analyzer = params.operating_mode_enum() is MonitorOperatingMode.SPECTRUM
        sweep = params.capture_mode == "sweep"
        self.setVisible(analyzer)
        self._params = params.copy()
        if not analyzer:
            return
        if self.is_user_editing() and not force:
            return
        self._prepare_spin_refresh(force=force)
        try:
            if not sweep:
                self.setEnabled(False)
                self.set_read_only(True, force=force)
                self._spin.setDecimals(0)
                self._spin.setPrefix("")
                self._spin.setSuffix("")
                self.set_maximum(1.0, force=force)
                self.set_minimum(0.0, force=force)
                self._spin.setSpecialValueText(tr("monitor_lcd_swt_na"))
                self.set_value(0.0, force=force)
                self.set_value_mode("normal")
                return
            self.setEnabled(True)
            self._spin.setSpecialValueText("")
            ms = effective_sweep_time_ms(params)
            if params.sweep_auto:
                self._apply_auto_ms_display(ms, "monitor_lcd_auto_suffix", force=force)
                self.set_value_mode("auto")
            else:
                self.set_read_only(False, force=force)
                self.set_maximum(999_999.0, force=force)
                self._spin.setSuffix(" ms")
                self.set_value(ms, force=force)
                self.set_value_mode("manual")
        finally:
            self._finish_spin_refresh()
        self._apply_tooltips()

    def _on_spin_committed(self, value: float) -> None:
        if self._block_emit or self._params.sweep_auto or self._params.capture_mode != "sweep":
            return
        self._emit_patch(patch_sweep_time_ms(self._params, value))

    def _build_menu(self, menu: QMenu) -> None:
        populate_sweep_menu(menu, lambda: self._params, self._emit_patch)
