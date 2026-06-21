"""Panel lateral: LNA/VGA fijos (2 columnas); P/AMPT/VRANGE al expandir."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QMenu, QToolButton, QVBoxLayout, QWidget

from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_rf_overlays import MonitorLnaSlider, MonitorPreampSlider, MonitorVgaSlider
from gui.monitor.monitor_spectrum_overlays import (
    MonitorAmptSlider,
    MonitorVRangeSlider,
    _SLIDER_QSS,
)
from gui.monitor.monitor_vertical_slider_column import pair_column_width
from i18n.json_translation import tr

_ESSENTIAL_COLUMNS = 2
_EXPANDED_EXTRA_COLUMNS = 3
_COLUMN_GAP = 4
_DOCK_MODES = ("auto", "collapsed", "expanded")
_AUTO_SEC_PRESETS = (1.0, 2.0, 3.0, 5.0, 10.0)


class MonitorSpectrumDockPanel(QFrame):
    """Dock RF: LNA + VGA fijos; P + AMPT + VRANGE expandibles."""

    width_changed = pyqtSignal(int)
    dock_settings_changed = pyqtSignal(str, float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorSpectrumDockPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_SLIDER_QSS)
        self._mode = "auto"
        self._auto_collapse_sec = 2.0
        self._expanded = False
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.timeout.connect(self._on_auto_collapse_timeout)

        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(2)

        self._mode_indicator = QToolButton(self)
        self._mode_indicator.setObjectName("MonitorDockPinBtn")
        self._mode_indicator.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._mode_indicator.clicked.connect(self._toggle_pin)

        self._menu_btn = QToolButton(self)
        self._menu_btn.setObjectName("MonitorOverlayMenuBtn")
        self._menu_btn.setText("…")
        self._menu_btn.setFixedSize(18, 16)
        self._menu_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._menu_btn.clicked.connect(self._show_mode_menu)

        self._tab_btn = QToolButton(self)
        self._tab_btn.setObjectName("MonitorDockTabBtn")
        self._tab_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._tab_btn.clicked.connect(self._toggle_expanded)

        top_row.addStretch(1)
        top_row.addWidget(self._mode_indicator, 0, Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(self._menu_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(self._tab_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        sliders_row = QHBoxLayout()
        sliders_row.setContentsMargins(0, 0, 0, 0)
        sliders_row.setSpacing(_COLUMN_GAP)
        self.rf_preamp = MonitorPreampSlider(self)
        self.rf_lna = MonitorLnaSlider(self)
        self.rf_vga = MonitorVgaSlider(self)
        self.ampt = MonitorAmptSlider(self)
        self.vrange = MonitorVRangeSlider(self)
        for col in (self.rf_lna, self.rf_vga, self.rf_preamp, self.ampt, self.vrange):
            sliders_row.addWidget(col)

        root.addLayout(top_row)
        root.addLayout(sliders_row, stretch=1)

        self.apply_dock_settings("auto", 2.0)

    @property
    def collapsed_width(self) -> int:
        return pair_column_width(columns=_ESSENTIAL_COLUMNS, gap=_COLUMN_GAP, padding=4)

    @property
    def expanded_width(self) -> int:
        return pair_column_width(
            columns=_ESSENTIAL_COLUMNS + _EXPANDED_EXTRA_COLUMNS,
            gap=_COLUMN_GAP,
            padding=4,
        )

    def current_width(self) -> int:
        return self.expanded_width if self._expanded else self.collapsed_width

    def apply_dock_settings(self, mode: str, auto_collapse_sec: float) -> None:
        normalized = mode if mode in _DOCK_MODES else "auto"
        self._mode = normalized
        self._auto_collapse_sec = max(0.5, float(auto_collapse_sec))
        self._collapse_timer.stop()
        if self._mode == "expanded":
            self._expanded = True
        elif self._mode == "collapsed":
            self._expanded = False
        self._sync_chrome()

    def set_params(self, params: SpectrumParams) -> None:
        if params.dock_collapse_mode != self._mode or abs(
            params.dock_auto_collapse_sec - self._auto_collapse_sec
        ) > 0.01:
            self.apply_dock_settings(params.dock_collapse_mode, params.dock_auto_collapse_sec)
        self.rf_preamp.set_params(params)
        self.rf_lna.set_params(params)
        self.rf_vga.set_params(params)
        self.ampt.set_params(params)
        self.vrange.set_params(params)

    def recargar_textos(self) -> None:
        self.rf_preamp.recargar_textos()
        self.rf_lna.recargar_textos()
        self.rf_vga.recargar_textos()
        self.ampt.recargar_textos()
        self.vrange.recargar_textos()
        self._sync_chrome()

    def enterEvent(self, event) -> None:
        self._collapse_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self._mode == "auto" and self._expanded:
            self._collapse_timer.start(int(self._auto_collapse_sec * 1000))
        elif self._mode == "collapsed" and self._expanded:
            self._collapse_timer.start(200)
        super().leaveEvent(event)

    def _on_auto_collapse_timeout(self) -> None:
        if self._mode == "expanded":
            return
        if self._expanded:
            self._expanded = False
            self._sync_chrome()

    def _toggle_expanded(self) -> None:
        if self._mode == "expanded":
            return
        self._expanded = not self._expanded
        self._collapse_timer.stop()
        self._sync_chrome()

    def _set_mode(self, mode: str, *, auto_sec: float | None = None) -> None:
        if mode not in _DOCK_MODES:
            return
        sec = self._auto_collapse_sec if auto_sec is None else float(auto_sec)
        self.apply_dock_settings(mode, sec)
        self.dock_settings_changed.emit(self._mode, self._auto_collapse_sec)

    def _toggle_pin(self) -> None:
        if self._mode == "expanded":
            self._set_mode("auto")
        else:
            self._set_mode("expanded")

    def _show_mode_menu(self) -> None:
        menu = QMenu(self)

        act_collapsed = menu.addAction(tr("monitor_dock_mode_collapsed"))
        act_collapsed.setCheckable(True)
        act_collapsed.setChecked(self._mode == "collapsed")
        act_collapsed.triggered.connect(lambda: self._set_mode("collapsed"))

        act_expanded = menu.addAction(tr("monitor_dock_mode_expanded"))
        act_expanded.setCheckable(True)
        act_expanded.setChecked(self._mode == "expanded")
        act_expanded.triggered.connect(lambda: self._set_mode("expanded"))

        auto_menu = menu.addMenu(tr("monitor_dock_mode_auto"))
        for sec in _AUTO_SEC_PRESETS:
            label = tr("monitor_dock_auto_sec").format(sec=f"{sec:.0f}")
            act = auto_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(self._mode == "auto" and abs(self._auto_collapse_sec - sec) < 0.01)

            def _pick_auto(_c=False, s=sec) -> None:
                self._set_mode("auto", auto_sec=s)

            act.triggered.connect(_pick_auto)

        menu.exec(self._menu_btn.mapToGlobal(self._menu_btn.rect().bottomLeft()))

    def _sync_chrome(self) -> None:
        self.rf_preamp.setVisible(self._expanded)
        self.ampt.setVisible(self._expanded)
        self.vrange.setVisible(self._expanded)
        self._menu_btn.setVisible(self._expanded)
        self._mode_indicator.setVisible(self._expanded)
        self._tab_btn.setText("◀" if self._expanded else "▶")
        pinned = self._mode == "expanded"
        self._mode_indicator.setText("📌" if pinned else "📍")
        self._mode_indicator.setProperty("pinned", "true" if pinned else "false")
        self._mode_indicator.style().unpolish(self._mode_indicator)
        self._mode_indicator.style().polish(self._mode_indicator)
        if pinned:
            pin_tip = tr("monitor_dock_pin_pinned")
        elif self._mode == "auto":
            pin_tip = tr("monitor_dock_pin_auto").format(sec=f"{self._auto_collapse_sec:.0f}")
        else:
            pin_tip = tr("monitor_dock_pin_collapsed")
        self._mode_indicator.setToolTip(pin_tip)
        self._tab_btn.setToolTip(
            tr("monitor_dock_collapse") if self._expanded else tr("monitor_dock_expand")
        )
        self._menu_btn.setToolTip(tr("monitor_dock_mode_menu"))
        self.setFixedWidth(self.current_width())
        self.width_changed.emit(self.current_width())
