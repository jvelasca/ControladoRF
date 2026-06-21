"""Slider horizontal con relleno de color y valor integrado (panel RADIO)."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QSizePolicy, QWidget

_FILLED_SLIDER_QSS = """
#MonitorFilledValueSliderHost {
    background-color: transparent;
    min-height: 26px;
}
#MonitorFilledValueSliderGroove {
    min-height: 22px;
}
#MonitorFilledValueSliderGroove::groove:horizontal {
    background: #1a2430;
    border: 1px solid #2a3848;
    height: 22px;
    border-radius: 4px;
}
#MonitorFilledValueSliderGroove::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1e5038, stop:1 #4caf78);
    border-radius: 3px;
}
#MonitorFilledValueSliderGroove::add-page:horizontal {
    background: transparent;
}
#MonitorFilledValueSliderGroove::handle:horizontal {
    background: #eef6ff;
    width: 4px;
    height: 20px;
    margin: -1px 0;
    border-radius: 2px;
}
#MonitorFilledValueSliderGroove[SquelchSlider="true"]::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #604020, stop:1 #ffb347);
}
#MonitorFilledValueSliderGroove[VolumeSlider="true"]::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1a4060, stop:1 #47a8ff);
}
#MonitorFilledValueSliderText {
    color: #eef6ff;
    font-size: 9px;
    font-weight: 700;
    background: transparent;
}
"""


class MonitorFilledValueSlider(QWidget):
    """Slider con sub-page coloreada y texto del valor superpuesto."""

    valueChanged = pyqtSignal(float)

    def __init__(
        self,
        *,
        minimum: float,
        maximum: float,
        step: float = 1.0,
        suffix: str = "",
        decimals: int = 0,
        slider_kind: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._minimum = float(minimum)
        self._maximum = float(maximum)
        self._step = max(float(step), 1e-9)
        self._suffix = suffix
        self._decimals = max(0, int(decimals))
        self._scale = int(round(1.0 / self._step)) if self._step < 1.0 else 1
        self._indicator_value: float | None = None
        self._syncing = False

        self.setObjectName("MonitorFilledValueSliderHost")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self.setMinimumHeight(26)
        self.setStyleSheet(_FILLED_SLIDER_QSS)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        self._slider.setObjectName("MonitorFilledValueSliderGroove")
        self._slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._slider.setMinimumWidth(0)
        self._slider.setMinimum(int(round(self._minimum * self._scale)))
        self._slider.setMaximum(int(round(self._maximum * self._scale)))
        if slider_kind:
            self._slider.setProperty(slider_kind, True)
            self._slider.style().polish(self._slider)
        layout.addWidget(self._slider, 1)

        self._label = QLabel(self._slider)
        self._label.setObjectName("MonitorFilledValueSliderText")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        font = QFont("Consolas", 9)
        font.setBold(True)
        self._label.setFont(font)
        self._slider.installEventFilter(self)

        self._slider.valueChanged.connect(self._on_slider_changed)
        self._slider.sliderMoved.connect(self._on_slider_changed)
        self._refresh_label()
        self._sync_label_geometry()

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 26)

    def sizeHint(self) -> QSize:
        return QSize(120, 26)

    def eventFilter(self, watched, event) -> bool:
        if watched is self._slider and event.type() == QEvent.Type.Resize:
            self._sync_label_geometry()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_label_geometry()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_label_geometry()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._indicator_value is None or self._slider.isSliderDown():
            return
        plot = self._slider.geometry()
        if plot.width() <= 0:
            return
        ratio = (self._indicator_value - self._minimum) / max(self._maximum - self._minimum, 1e-9)
        ratio = max(0.0, min(1.0, ratio))
        x = plot.left() + int(round(ratio * plot.width()))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QPen(QColor(255, 90, 90), 2))
        painter.drawLine(x, plot.top() + 1, x, plot.bottom() - 1)
        painter.end()

    def is_interacting(self) -> bool:
        return self._slider.isSliderDown()

    def set_indicator_value(self, value: float | None) -> None:
        new = None if value is None else float(value)
        if new is not None and self._indicator_value is not None:
            if abs(new - self._indicator_value) < 0.08:
                return
        if new == self._indicator_value:
            return
        self._indicator_value = new
        self.update()

    def value(self) -> float:
        return float(self._slider.value()) / self._scale

    def set_value(self, value: float) -> None:
        if self.is_interacting():
            return
        scaled = int(round(max(self._minimum, min(self._maximum, float(value))) * self._scale))
        if scaled == self._slider.value():
            self._refresh_label()
            return
        self._syncing = True
        self._slider.setValue(scaled)
        self._syncing = False
        self._refresh_label()

    def block_signals(self, block: bool) -> None:
        self._slider.blockSignals(block)

    def _sync_label_geometry(self) -> None:
        self._label.setGeometry(self._slider.rect())

    def _on_slider_changed(self, _value: int) -> None:
        self._refresh_label()
        if self._syncing:
            return
        self.valueChanged.emit(self.value())

    def _refresh_label(self) -> None:
        value = self.value()
        if self._decimals > 0:
            text = f"{value:.{self._decimals}f}{self._suffix}"
        else:
            text = f"{int(round(value))}{self._suffix}"
        self._label.setText(text)
