"""Sliders Min/Max de contraste del espectrograma (estilo SDR++)."""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QWidget

from core.monitor.spectrum_params import SpectrumParams
from core.monitor.waterfall_colormap import (
    WATERFALL_COLORMAPS,
    WATERFALL_DB_CEIL,
    WATERFALL_DB_FLOOR,
    db_to_slider_value,
    slider_value_to_db,
)
from gui.monitor.monitor_spectrum_overlays import _SLIDER_QSS, _make_slider, _menu_button
from gui.monitor.monitor_plot_layout import WATERFALL_SLIDER_PANEL_WIDTH, freq_plot_rect
from gui.monitor.monitor_vertical_slider_column import build_vertical_slider_column, pair_column_width
from i18n.json_translation import tr


def populate_waterfall_menu(
    menu: QMenu,
    params: SpectrumParams,
    *,
    patch: Callable[[SpectrumParams], None],
) -> None:
    act_link = menu.addAction(tr("monitor_wf_link_spectrum"))
    act_link.setCheckable(True)
    act_link.setChecked(params.waterfall_auto_levels)
    act_link.triggered.connect(
        lambda checked: patch(_copy_wf(params, link_spectrum=bool(checked)))
    )

    act_hist = menu.addAction(tr("monitor_wf_auto_contrast"))
    act_hist.setCheckable(True)
    act_hist.setChecked(params.waterfall_contrast_auto)
    act_hist.triggered.connect(
        lambda checked: patch(_copy_wf(params, contrast_auto=bool(checked)))
    )

    menu.addSeparator()
    cmap_menu = menu.addMenu(tr("monitor_wf_colormap"))
    for name in WATERFALL_COLORMAPS:
        act = cmap_menu.addAction(tr(f"monitor_wf_cmap_{name}"))
        act.setCheckable(True)
        act.setChecked(params.waterfall_colormap == name)
        act.triggered.connect(
            lambda _c=False, cmap=name: patch(_copy_wf(params, colormap=cmap))
        )


def _copy_wf(
    params: SpectrumParams,
    *,
    link_spectrum: bool | None = None,
    contrast_auto: bool | None = None,
    colormap: str | None = None,
) -> SpectrumParams:
    updated = params.copy()
    if link_spectrum is not None:
        updated.waterfall_auto_levels = link_spectrum
        if link_spectrum:
            updated.waterfall_contrast_auto = False
            updated.waterfall_max_db = updated.ref_level_dbm
            updated.waterfall_min_db = updated.ref_level_dbm - updated.ref_range_db
    if contrast_auto is not None:
        updated.waterfall_contrast_auto = contrast_auto
        if contrast_auto:
            updated.waterfall_auto_levels = False
    if colormap is not None:
        updated.waterfall_colormap = colormap
    return updated


class _WaterfallLevelSlider(QFrame):
    params_changed = pyqtSignal(object)

    def __init__(
        self,
        *,
        label_key: str,
        tip_key: str,
        level_attr: str,
        inverted: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorOverlayFrame")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_SLIDER_QSS)
        self._level_attr = level_attr
        self._tip_key = tip_key
        self._params = SpectrumParams()
        self._syncing = False

        self._label = QLabel(tr(label_key), self)
        self._label.setObjectName("MonitorOverlayVLabel")
        self._slider = _make_slider(Qt.Orientation.Vertical)
        self._slider.setObjectName("MonitorOverlaySliderWaterfall")
        self._slider.setMinimumHeight(80)
        self._slider.setRange(0, 10_000)
        self._slider.setInvertedAppearance(inverted)
        self._slider.valueChanged.connect(self._on_slider)
        self._menu_btn = _menu_button(self, self._show_menu)
        build_vertical_slider_column(self, label=self._label, slider=self._slider, menu_btn=self._menu_btn)
        self._apply_tooltips()

    def set_params(
        self,
        params: SpectrumParams,
        *,
        ref_level_dbm: float | None = None,
        ref_range_db: float | None = None,
    ) -> None:
        self._syncing = True
        self._params = params.copy()
        manual = not (params.waterfall_auto_levels or params.waterfall_contrast_auto)
        if params.waterfall_auto_levels and ref_level_dbm is not None and ref_range_db is not None:
            from core.monitor.waterfall_colormap import resolve_waterfall_levels

            bottom, top = resolve_waterfall_levels(
                min_db=params.waterfall_min_db,
                max_db=params.waterfall_max_db,
                link_spectrum=True,
                contrast_auto=False,
                ref_level_dbm=ref_level_dbm,
                ref_range_db=ref_range_db,
            )
            db = top if self._level_attr == "waterfall_max_db" else bottom
        else:
            db = float(getattr(params, self._level_attr))
        self._slider.blockSignals(True)
        self._slider.setValue(db_to_slider_value(db))
        self._slider.blockSignals(False)
        self._slider.setEnabled(True)
        self._slider.setProperty("monitorManualLevels", manual)
        self._slider.style().unpolish(self._slider)
        self._slider.style().polish(self._slider)
        self._syncing = False

    def recargar_textos(self) -> None:
        keys = {
            "waterfall_min_db": "monitor_overlay_wf_min",
            "waterfall_max_db": "monitor_overlay_wf_max",
        }
        self._label.setText(tr(keys.get(self._level_attr, "monitor_overlay_wf_min")))
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        tip = tr(self._tip_key)
        self._label.setToolTip(tip)
        self._slider.setToolTip(tip)
        self._menu_btn.setToolTip(tr("monitor_tip_wf_menu"))

    def _patch(self, updated: SpectrumParams) -> None:
        self._params = updated
        self._syncing = True
        db = float(getattr(updated, self._level_attr))
        self._slider.blockSignals(True)
        self._slider.setValue(db_to_slider_value(db))
        self._slider.blockSignals(False)
        manual = not (updated.waterfall_auto_levels or updated.waterfall_contrast_auto)
        self._slider.setProperty("monitorManualLevels", manual)
        self._slider.style().unpolish(self._slider)
        self._slider.style().polish(self._slider)
        self._syncing = False
        self.params_changed.emit(updated)

    def _on_slider(self, value: int) -> None:
        if self._syncing:
            return
        updated = self._params.copy()
        updated.waterfall_auto_levels = False
        updated.waterfall_contrast_auto = False
        db = slider_value_to_db(value)
        setattr(updated, self._level_attr, db)
        if updated.waterfall_min_db >= updated.waterfall_max_db:
            gap = 10.0
            if self._level_attr == "waterfall_min_db":
                updated.waterfall_max_db = min(
                    WATERFALL_DB_CEIL,
                    updated.waterfall_min_db + gap,
                )
            else:
                updated.waterfall_min_db = max(
                    WATERFALL_DB_FLOOR,
                    updated.waterfall_max_db - gap,
                )
        self._patch(updated)

    def _show_menu(self) -> None:
        menu = QMenu(self)
        populate_waterfall_menu(menu, self._params, patch=self._patch)
        menu.exec(self._menu_btn.mapToGlobal(self._menu_btn.rect().bottomLeft()))


class MonitorWaterfallLevelSliders(QFrame):
    """Par Min / Max a la derecha del espectrograma."""

    params_changed = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorOverlayFrame")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_SLIDER_QSS)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        self._max = _WaterfallLevelSlider(
            label_key="monitor_overlay_wf_max",
            tip_key="monitor_tip_overlay_wf_max",
            level_attr="waterfall_max_db",
            inverted=True,
            parent=self,
        )
        self._min = _WaterfallLevelSlider(
            label_key="monitor_overlay_wf_min",
            tip_key="monitor_tip_overlay_wf_min",
            level_attr="waterfall_min_db",
            inverted=False,
            parent=self,
        )
        self._max.params_changed.connect(lambda p: self._forward(p, source=self._max))
        self._min.params_changed.connect(lambda p: self._forward(p, source=self._min))

        root.addWidget(self._max)
        root.addWidget(self._min)

    def set_params(
        self,
        params: SpectrumParams,
        *,
        ref_level_dbm: float | None = None,
        ref_range_db: float | None = None,
    ) -> None:
        self._max.set_params(params, ref_level_dbm=ref_level_dbm, ref_range_db=ref_range_db)
        self._min.set_params(params, ref_level_dbm=ref_level_dbm, ref_range_db=ref_range_db)

    def recargar_textos(self) -> None:
        self._max.recargar_textos()
        self._min.recargar_textos()

    def reposition(self, width: int, height: int, *, right_gutter: int) -> None:
        from gui.monitor.monitor_vertical_slider_column import COLUMN_WIDTH

        plot = freq_plot_rect(
            QRect(0, 0, width, height),
            right_gutter=right_gutter,
            top=2,
            bottom=2,
        )
        plot_h = max(60, plot.height())
        gap = 4
        slider_x = width - WATERFALL_SLIDER_PANEL_WIDTH
        self._max.setFixedSize(COLUMN_WIDTH, plot_h)
        self._max.move(0, 0)
        self._min.setFixedSize(COLUMN_WIDTH, plot_h)
        self._min.move(COLUMN_WIDTH + gap, 0)
        self.setFixedSize(WATERFALL_SLIDER_PANEL_WIDTH, plot_h)
        self.move(slider_x, plot.top())

    def _forward(self, updated: SpectrumParams, *, source: _WaterfallLevelSlider | None = None) -> None:
        self._max._params = updated.copy()
        self._min._params = updated.copy()
        ref = float(updated.ref_level_dbm)
        rng = float(updated.ref_range_db)
        if source is not self._max:
            self._max.set_params(updated, ref_level_dbm=ref, ref_range_db=rng)
        if source is not self._min:
            self._min.set_params(updated, ref_level_dbm=ref, ref_range_db=rng)
        self.params_changed.emit(updated)
