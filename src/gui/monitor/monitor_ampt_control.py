"""Control AMPT (toolbar) y menú compartido con slider del gráfico."""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QInputDialog, QMenu, QWidget

from core.monitor.amplitude_units import (
    AMPLITUDE_UNITS,
    amplitude_axis_label,
    dbm_to_display,
    display_to_dbm,
)
from core.monitor.display_scale import REF_SCALE_PRESETS
from core.monitor.monitor_format import parse_locale_float
from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_numeric_control import MonitorNumericControl
from i18n.json_translation import tr


def populate_ampt_menu(
    menu: QMenu,
    params: SpectrumParams,
    *,
    patch: Callable[[SpectrumParams], None],
    parent: QWidget,
) -> None:
    """Menú … AMPT: AUTO, ref, rango, unidades, offset."""

    def apply(updated: SpectrumParams) -> None:
        patch(updated)

    act_auto = menu.addAction(tr("monitor_ampt_auto"))
    act_auto.setCheckable(True)
    act_auto.setChecked(params.ref_scale_auto)
    act_auto.triggered.connect(
        lambda: apply(
            _copy(params, ref_scale_auto=True, ampt_mode="ref_level")
        )
    )

    act_ref = menu.addAction(tr("monitor_tb_ampt_ref_level"))
    act_ref.setCheckable(True)
    act_ref.setChecked(params.ampt_mode == "ref_level" and not params.ref_scale_auto)
    act_ref.triggered.connect(
        lambda: apply(
            _copy(params, ref_scale_auto=False, ampt_mode="ref_level")
        )
    )

    range_menu = menu.addMenu(tr("monitor_tb_ampt_ref_range"))
    for range_db, db_div in REF_SCALE_PRESETS:
        label = tr("monitor_ref_range_preset").format(
            range=f"{range_db:.0f}",
            db_div=f"{db_div:.0f}",
        )
        act = range_menu.addAction(label)
        act.setCheckable(True)
        act.setChecked(
            not params.ref_scale_auto
            and params.ampt_mode == "ref_range"
            and abs(params.ref_range_db - range_db) < 0.5
        )

        def _set_range(_c=False, r=range_db, d=db_div) -> None:
            updated = _copy(params, ref_scale_auto=False, ampt_mode="ref_range")
            updated.ref_range_db = r
            updated.vertical_divisions = max(1, int(round(r / max(d, 0.1))))
            apply(updated)

        act.triggered.connect(_set_range)

    menu.addSeparator()

    unit_menu = menu.addMenu(tr("monitor_tb_ampt_unit"))
    for unit in AMPLITUDE_UNITS:
        act = unit_menu.addAction(amplitude_axis_label(unit))
        act.setCheckable(True)
        act.setChecked(params.amplitude_unit == unit)
        act.triggered.connect(lambda _c=False, u=unit: apply(_copy(params, amplitude_unit=u)))

    menu.addSeparator()

    def _edit_offset() -> None:
        text, ok = QInputDialog.getText(
            parent,
            tr("monitor_tb_ampt_ref_offset"),
            tr("monitor_ref_offset_prompt"),
            text=f"{params.ref_offset_db:.1f}",
        )
        if not ok:
            return
        try:
            offset = parse_locale_float(text)
        except ValueError:
            return
        apply(_copy(params, ref_offset_db=offset))

    menu.addAction(tr("monitor_tb_ampt_ref_offset"), _edit_offset)


def _copy(params: SpectrumParams, **kwargs) -> SpectrumParams:
    updated = params.copy()
    for key, value in kwargs.items():
        setattr(updated, key, value)
    return updated


class MonitorAmptControl(MonitorNumericControl):
    """AMPT en toolbar: lectura ref / AUTO + menú …."""

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            tr("monitor_tb_ampt"),
            suffix=" dBm",
            decimals=1,
            minimum=-150.0,
            maximum=50.0,
            step=1.0,
            menu_builder=self._build_menu,
            parent=parent,
        )
        self._params = SpectrumParams()
        self._patch_callback: Optional[Callable[[SpectrumParams], None]] = None
        self._apply_tooltips()

    def bind_patch(self, callback: Callable[[SpectrumParams], None]) -> None:
        self._patch_callback = callback

    def set_params(self, params: SpectrumParams) -> None:
        self._params = params.copy()
        unit = params.amplitude_unit
        suffix = f" {amplitude_axis_label(unit)}"
        self._spin.setSuffix(suffix)
        if params.ref_scale_auto:
            self.set_read_only(True)
            editor = self._spin.lineEdit()
            if editor is not None:
                editor.setText(tr("monitor_ampt_auto"))
            self.set_value_mode("auto")
        else:
            self.set_read_only(False)
            display = dbm_to_display(
                params.ref_level_dbm, unit, ref_offset_db=params.ref_offset_db
            )
            self.set_value(display)
            self.set_value_mode("manual")

    def recargar_textos(self) -> None:
        self.set_title(tr("monitor_tb_ampt"))
        self._apply_tooltips()
        self.set_params(self._params)

    def _apply_tooltips(self) -> None:
        mode = tr("monitor_scale_mode_auto") if self._params.ref_scale_auto else tr("monitor_scale_mode_manual")
        self.set_tooltips(
            tr("monitor_tip_ampt_mode").format(mode=mode),
            tr("monitor_tip_ampt_menu"),
        )

    def show_popup_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        self._build_menu(menu)
        menu.exec(global_pos)

    def _build_menu(self, menu: QMenu) -> None:
        if self._patch_callback is None:
            return
        populate_ampt_menu(
            menu,
            self._params,
            patch=self._emit_patch,
            parent=self,
        )

    def _emit_patch(self, updated: SpectrumParams) -> None:
        self._params = updated
        self.set_params(updated)
        if self._patch_callback:
            self._patch_callback(updated)

    def _on_spin_committed(self, value: float) -> None:
        if self._block_emit or self._params.ref_scale_auto:
            return
        unit = self._params.amplitude_unit
        updated = self._params.copy()
        updated.ref_scale_auto = False
        updated.ampt_mode = "ref_level"
        updated.ref_level_dbm = display_to_dbm(
            value, unit, ref_offset_db=updated.ref_offset_db
        )
        self._emit_patch(updated)
