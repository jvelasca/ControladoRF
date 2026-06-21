"""Sliders de espectro: escala log de frecuencia/SPAN con vista de ventana integrada."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen, QWheelEvent
from PyQt6.QtWidgets import QWidget

from core.monitor.display_scale import (
    FREQ_SLIDER_MAX_HZ,
    FREQ_SLIDER_MIN_HZ,
    SPAN_STEPS_HZ,
    freq_to_slider_value,
    span_to_slider_value,
)
from core.monitor.display_colors import SpanSliderColors, span_slider_colors
from core.monitor.spectrum_params import SpectrumParams

_LOG_TICKS_MHZ = (1, 2, 5, 10, 20, 50, 100, 200, 400, 800, 1600, 3200, 6000)


class MonitorLogFreqSlider(QWidget):
    """Slider logarítmico con marcas tipo dial; flechas ← → con foco."""

    valueChanged = pyqtSignal(int)
    sliderPressed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorLogFreqSlider")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(22)
        self._min_v = 0
        self._max_v = 10_000
        self._value = 5000
        self._dragging = False
        self._readout_mode = "fc"

    def setRange(self, minimum: int, maximum: int) -> None:
        self._min_v = int(minimum)
        self._max_v = int(maximum)
        self._value = max(self._min_v, min(self._max_v, self._value))
        self.update()

    def setValue(self, value: int) -> None:
        v = max(self._min_v, min(self._max_v, int(value)))
        if v != self._value:
            self._value = v
            self.update()

    def value(self) -> int:
        return self._value

    def set_readout_mode(self, mode: str) -> None:
        self._readout_mode = "f" if mode == "f" else "fc"
        self.setProperty("readoutMode", self._readout_mode)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _ratio_from_value(self, value: int) -> float:
        return max(0.0, min(1.0, (value - self._min_v) / max(self._max_v - self._min_v, 1)))

    def _value_from_x(self, x: float) -> int:
        w = max(self.width(), 1)
        ratio = max(0.0, min(1.0, x / w))
        return int(round(self._min_v + ratio * (self._max_v - self._min_v)))

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        rect = self.rect().adjusted(2, 2, -2, -2)
        p.fillRect(rect, QColor(26, 36, 48))
        accent = QColor(255, 170, 70) if self._readout_mode == "f" else QColor(100, 190, 255)
        if self._readout_mode != "f":
            for mhz in _LOG_TICKS_MHZ:
                hz = mhz * 1_000_000.0
                if hz < FREQ_SLIDER_MIN_HZ or hz > FREQ_SLIDER_MAX_HZ:
                    continue
                sv = freq_to_slider_value(hz)
                ratio = self._ratio_from_value(sv)
                x = rect.left() + int(ratio * rect.width())
                major = mhz in (100, 400, 1600)
                h = 10 if major else 5
                p.setPen(QPen(QColor(90, 110, 130) if not major else QColor(120, 145, 170), 1))
                p.drawLine(x, rect.bottom() - h, x, rect.bottom())
        ratio = self._ratio_from_value(self._value)
        hx = rect.left() + int(ratio * rect.width())
        p.setBrush(accent)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(hx - 5, rect.top() + 1, 10, rect.height() - 2, 3, 3)
        p.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.sliderPressed.emit()
            self.setFocus()
            self._dragging = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self._value = self._value_from_x(event.position().x())
            self.valueChanged.emit(self._value)
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        step = max(1, (self._max_v - self._min_v) // 400)
        if event.key() == Qt.Key.Key_Left:
            self.setValue(self._value - step)
            self.valueChanged.emit(self._value)
        elif event.key() == Qt.Key.Key_Right:
            self.setValue(self._value + step)
            self.valueChanged.emit(self._value)
        else:
            super().keyPressEvent(event)


class MonitorLogSpanSlider(QWidget):
    """Slider log SPAN + sombra azul de la ventana visible sobre el rango del equipo."""

    valueChanged = pyqtSignal(int)
    span_wheel = pyqtSignal(int)
    sliderPressed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorLogSpanSlider")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(22)
        self._min_v = 0
        self._max_v = 10_000
        self._value = 5000
        self._min_span_hz = 100_000.0
        self._max_span_hz = 20_000_000.0
        self._dragging = False
        self._center_ratio = 0.5
        self._width_ratio = 0.1
        self._colors = span_slider_colors(SpectrumParams())

    def set_span_range(self, min_hz: float, max_hz: float) -> None:
        self._min_span_hz = max(1.0, float(min_hz))
        self._max_span_hz = max(self._min_span_hz, float(max_hz))
        self.update()

    def set_viewport(
        self,
        *,
        fmin_hz: float,
        range_hz: float,
        center_ratio: float,
        width_ratio: float,
    ) -> None:
        del fmin_hz, range_hz
        self._width_ratio = max(0.001, min(1.0, float(width_ratio)))
        half = self._width_ratio / 2.0
        if self._width_ratio >= 1.0 - 1e-9:
            self._center_ratio = 0.5
            self._width_ratio = 1.0
        else:
            self._center_ratio = max(half, min(1.0 - half, float(center_ratio)))
        self.update()

    def set_display_colors(self, colors: SpanSliderColors) -> None:
        self._colors = colors
        self.update()

    def setRange(self, minimum: int, maximum: int) -> None:
        self._min_v = int(minimum)
        self._max_v = int(maximum)
        self._value = max(self._min_v, min(self._max_v, self._value))
        self.update()

    def setValue(self, value: int) -> None:
        v = max(self._min_v, min(self._max_v, int(value)))
        if v != self._value:
            self._value = v
            self.update()

    def value(self) -> int:
        return self._value

    def _track_rect(self) -> QRect:
        return self.rect().adjusted(2, 2, -2, -2)

    def _ratio_from_value(self, value: int) -> float:
        return max(0.0, min(1.0, (value - self._min_v) / max(self._max_v - self._min_v, 1)))

    def _value_from_x(self, x: float) -> int:
        rect = self._track_rect()
        track_w = max(float(rect.width()), 1.0)
        ratio = max(0.0, min(1.0, (x - rect.left()) / track_w))
        return int(round(self._min_v + ratio * (self._max_v - self._min_v)))

    def _viewport_rect(self, track: QRect) -> QRect:
        track_w = max(float(track.width()), 1.0)
        handle_w = max(3.0, track_w * self._width_ratio)
        left_ratio = self._center_ratio - self._width_ratio / 2.0
        left_ratio = max(0.0, min(1.0 - self._width_ratio, left_ratio))
        left = track.left() + int(left_ratio * track_w)
        return QRect(left, track.top(), max(3, int(handle_w)), track.height())

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        track = self._track_rect()
        colors = self._colors
        p.fillRect(track, colors.track)

        viewport = self._viewport_rect(track)
        for hz in SPAN_STEPS_HZ:
            if hz < self._min_span_hz - 1.0 or hz > self._max_span_hz + 1.0:
                continue
            sv = span_to_slider_value(
                hz,
                max_span_hz=self._max_span_hz,
                min_span_hz=self._min_span_hz,
            )
            ratio = self._ratio_from_value(sv)
            x = track.left() + int(ratio * track.width())
            if viewport.left() <= x <= viewport.right():
                continue
            major = hz in (1_000_000.0, 5_000_000.0, 20_000_000.0)
            h = 10 if major else 5
            p.setPen(QPen(QColor(62, 82, 98) if not major else QColor(88, 112, 128), 1))
            p.drawLine(x, track.bottom() - h, x, track.bottom())

        p.fillRect(viewport, colors.viewport_shadow)
        hi = viewport.adjusted(1, 1, -1, -int(viewport.height() * 0.5))
        p.fillRect(hi, colors.viewport_shadow_hi)

        ratio = self._ratio_from_value(self._value)
        hx = track.left() + int(ratio * track.width())
        p.setBrush(colors.handle)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(hx - 5, track.top() + 1, 10, track.height() - 2, 3, 3)
        p.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.sliderPressed.emit()
            self.setFocus()
            self._dragging = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self._value = self._value_from_x(event.position().x())
            self.valueChanged.emit(self._value)
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return
        direction = 1 if delta > 0 else -1
        self.span_wheel.emit(direction)
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        step = max(1, (self._max_v - self._min_v) // 400)
        if event.key() == Qt.Key.Key_Left:
            self.setValue(self._value - step)
            self.valueChanged.emit(self._value)
        elif event.key() == Qt.Key.Key_Right:
            self.setValue(self._value + step)
            self.valueChanged.emit(self._value)
        elif event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Plus):
            self.span_wheel.emit(1)
        elif event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Minus):
            self.span_wheel.emit(-1)
        else:
            super().keyPressEvent(event)
