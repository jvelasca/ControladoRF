"""Slider vertical con pasos discretos y marcas (RF, resolución vertical)."""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QSlider, QWidget

from gui.monitor.monitor_slider_readout import MonitorSliderReadout
from gui.monitor.monitor_vertical_slider_column import COLUMN_WIDTH, build_vertical_slider_column


class MonitorDiscreteVerticalSlider(QFrame):
    """Columna vertical: rótulo + slider indexado + lectura clicable."""

    step_changed = pyqtSignal(int)
    readout_clicked = pyqtSignal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        label: str,
        slider_object_name: str,
        step_count: int,
        inverted: bool = False,
        tick_interval: int = 1,
        readout_text: str = "",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorOverlayFrame")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._syncing = False
        self._step_count = max(1, int(step_count))
        self.setMinimumWidth(COLUMN_WIDTH)

        self._label = QLabel(label, self)
        self._label.setObjectName("MonitorOverlayVLabel")

        self._slider = QSlider(Qt.Orientation.Vertical, self)
        self._slider.setObjectName(slider_object_name)
        self._slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._slider.setTracking(True)
        self._slider.setMinimumHeight(100)
        self._slider.setRange(0, max(0, self._step_count - 1))
        self._slider.setSingleStep(1)
        self._slider.setPageStep(max(1, tick_interval))
        self._slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
        self._slider.setTickInterval(max(1, tick_interval))
        if inverted:
            self._slider.setInvertedAppearance(True)
        self._slider.valueChanged.connect(self._emit_step)

        self._readout = MonitorSliderReadout(readout_text, parent=self)
        self._readout.clicked.connect(self.readout_clicked.emit)
        build_vertical_slider_column(
            self, label=self._label, slider=self._slider, readout=self._readout
        )

    def set_step_index(self, index: int) -> None:
        self._syncing = True
        cap = int(self._slider.maximum())
        self._slider.blockSignals(True)
        self._slider.setValue(max(0, min(cap, int(index))))
        self._slider.blockSignals(False)
        self._syncing = False

    def step_index(self) -> int:
        return int(self._slider.value())

    def set_label(self, text: str) -> None:
        self._label.setText(text)

    def set_readout_text(self, text: str) -> None:
        self._readout.setText(text)

    def set_tooltips(self, tip: str, readout_tip: str = "") -> None:
        self._label.setToolTip(tip)
        self._slider.setToolTip(tip)
        self._readout.setToolTip(readout_tip or tip)

    def set_max_step_index(self, max_index: int) -> None:
        """Limita el índice superior sin mover el otro control (solo techo del slider)."""
        cap = max(0, min(self._step_count - 1, int(max_index)))
        self._slider.setMaximum(cap)

    def set_slider_property(self, name: str, value: str) -> None:
        self._slider.setProperty(name, value)
        self._slider.style().unpolish(self._slider)
        self._slider.style().polish(self._slider)

    def connect_step_handler(self, handler: Callable[[int], None]) -> None:
        self.step_changed.connect(handler)

    def _emit_step(self, value: int) -> None:
        if self._syncing:
            return
        self.step_changed.emit(int(value))
